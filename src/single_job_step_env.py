
from threading import Lock
import threading


from kplanner_api_adapter import KPlannerAPIAdapter


import random
from datetime import datetime, timedelta

import pandas as pd
import logging
import uuid
import copy


log = logging.getLogger("single_step_env") 
import random


lock = Lock()
order_seconds = []
TOLERANCE_MINUTES = 1200
REALTIME_START_HORIZON_MINUTES = 10 * 60  #  129000 / 60#  + 100 - (9 * 60)

SAMPLE_JOB_TEMPLATE = {
    "code": "01",
    "requested_primary_worker_code": None,
    "location_code": None,
    "geo_longitude": None,
    "geo_latitude": None,
    "job_type": "visit",
    "planning_status": "U",
    "auto_planning": True,
    "is_active": True,
    "name": None,
    "description": None,
    "flex_form_data": {},
    "requested_start_datetime": None,
    "requested_duration_minutes": 0.5,
    # "requested_primary_worker_code": None,
    "scheduled_start_datetime": None,
    "scheduled_duration_minutes": 0.5,
    "scheduled_primary_worker_code": None,
    "requested_items": None,
    # "auto_planning":True,
}


class SingleStepEnv:
    SKIP_SECONDS = 240 * 60
    def __init__(self, config={}, api_adapter:KPlannerAPIAdapter=None):
        # 
        self.step_tick_minutes = 1
        self.horizon_start_minutes = 0
        self.step_tick_minutes = 1
        self.reposition_before_job_count = 0
        self.is_reposition = False
        self.current_step = 0
        self.job_overdue_dict = {}
        self.job_log_iloc = 0
        self.worker_log_iloc = 0
        self.current_job_code = None
        self.worker_at_location_i = 200_000
        self.till_minutes = 0
        self.workers_dict = {}
        self.jobs_dict = {}
        self.failed_jobs_dict = {}
        self.order_seconds = []
        if api_adapter is not None:
            self.api_adapter = api_adapter
        else:
            self.api_adapter = KPlannerAPIAdapter(
                service_url=config["service_url"],
                username=config["username"],
                password=config["password"],
                team_code=config["team_code"],
            )
        self.config = config
        self.org_id = self.api_adapter.org_id 

        self.load_worker_job_logs()

        self.CENTER_LONGLAT=config["CENTER_LONGLAT"]
        self.DIFF_LONG = self.CENTER_LONGLAT[0] 
        self.DIFF_LAT = self.CENTER_LONGLAT[1] 


            
    def track_jobs(self, result):
        for job in result["scheduled_slots"]:  # [0]["assigned_jobs"]
            if job["code"] in self.jobs_dict:
                if (
                    job["scheduled_start_datetime"]
                    != self.jobs_dict[job["code"]]["scheduled_start_datetime"]
                ):
                    print(
                        "job {} is rescheduled to worker: {}, time: {}".format(
                            job["code"],
                            result["worker_code"],
                            job["scheduled_start_datetime"],
                        )
                    )
            else:
                print(
                    "job {} is initially scheduled to worker: {}, time: {}".format(
                        job["code"],
                        result["worker_code"],
                        job["scheduled_start_datetime"],
                    )
                )
            job["scheduled_worker_code"] = result["worker_code"]
            with lock:
                self.jobs_dict[job["code"]] = job
        


    def load_worker_job_logs(self):
        nbr_sampled_workers = int(self.config.get("nbr_sampled_workers", 16))
        nbr_sampled_jobs = int(self.config.get("nbr_sampled_jobs", 160))

        self.worker_log_df = (
            pd.read_csv(
                "{}/worker_log.csv".format(self.config["simulation_log_dir"]),
                header=0,
                sep=",",
                encoding="utf_8",
                on_bad_lines='skip'
            )  # .sample(n=nbr_sampled_workers, random_state=nbr_sampled_workers)
            .sort_values(by=["start_seconds"])
            .reset_index()
        )
        self.worker_log_dict = self.worker_log_df.to_dict(orient="records")
        self.worker_log_iloc = 0
        self.all_worker_loc_list = self.worker_log_df[["start_x", "start_y"]].values

        self.job_log_df = (
            pd.read_csv(
                "{}/job_log.csv".format(self.config["simulation_log_dir"]),
                header=0,
                sep=",",
                encoding="utf_8",
                on_bad_lines='skip'
            )  # .sample(n=nbr_sampled_jobs, random_state=nbr_sampled_jobs)
            .sort_values(by=["start_seconds"])
            .reset_index()
        )
        self.job_log_df["start_seconds"] = self.job_log_df["start_seconds"] - self.SKIP_SECONDS

        self.job_log_dict = self.job_log_df.to_dict(orient="records")
        self.job2loc_dict = {}
        for ji, j in enumerate(self.job_log_dict):
            self.job2loc_dict[j["seq"]] = [
                j["end_x"], j["end_y"]
            ]
            # if j["start_seconds"] < REALTIME_START_HORIZON_MINUTES * 60:
            #     j["start_seconds"] = (REALTIME_START_HORIZON_MINUTES-1) * 60

        self.job_log_iloc = 0
        self.all_job_loc_list = self.job_log_df[
            [
                "seq",
                "start_x",
                "start_y",
                "end_x",
                "end_y",
                "start_seconds",
                "end_seconds",
            ]
        ].values

        print(
            f"Loaded {self.worker_log_df.count().max()} worker logs, {self.job_log_df.count().max()} job logs from {self.config['simulation_log_dir']}/job_log.csv..."
        )

    def _move_to_next_unplanned_job(self, mutate_state = True):
        self.current_step += 1
        if self.job_log_iloc >= len(self.job_log_dict):
            log.warning("reached len(self.job_log_dict), returning DONE=TRUE")
            self.job_log_iloc += 1
            return None
        if not mutate_state:
            self.job_log_iloc += 1
            return self.job_log_dict[self.job_log_iloc - 1]

        
        temp_job_dict = self.job_log_dict[self.job_log_iloc]
        # job_code = temp_job_dict["job_code"]

        new_till_minutes = temp_job_dict["start_seconds"] / 60
        if (
            new_till_minutes > self.till_minutes
            and new_till_minutes > REALTIME_START_HORIZON_MINUTES
        ):
            self.till_minutes = new_till_minutes
            self.mutate_job_state_before_minutes()
            self.mutate_worker_state_before_minutes(self.till_minutes)
            target_datetime = self.api_adapter.env_start_datetime + timedelta(
                seconds=temp_job_dict["start_seconds"]
            )
            self.api_adapter.set_horizon_start_minutes(
                team_id=self.api_adapter.team_id,
                start_datetime=datetime.strftime(
                    target_datetime, "%Y-%m-%dT%H:%M:%S"
                ),
            )
            print(
                f"set_horizon_start_minutes to {self.till_minutes}, date {target_datetime} "
            )
        self.job_log_iloc += 1
        return temp_job_dict

    def generate_all_items(self, current_log_dir):
        list_to_insert = []
        file_path = f"{current_log_dir}/item_list.csv"
        item_df = pd.read_csv(
            file_path,
            header=0,
            sep=",",
            encoding="utf_8",
        )
        for w_i, prod in item_df.iterrows():
            myobj = {
                "code": prod.product_code,
                "name": prod["product_name"],
                "weight": prod.price,
                "volume": 1,
                "flex_form_data": {
                    k: prod[k]
                    for k in item_df.columns
                    if (k[:7] != "Unnamed" and not pd.isna(prod[k]))
                },
                "is_active": True,
                "org_id": self.api_adapter.org_id,
            }
            list_to_insert.append(myobj)

        self.api_adapter.insert_all_items(list_to_insert)

    def generate_all_workers(self, use_fixed_location=False, nbr_workers=16):
        """example code for worker creation:"""

        # _business_hour["sunday"] = [
        #         {"open": '0130', "close": '2525',"id": str(uuid.uuid1()), "isOpen": True}
        #         ]
        # _business_hour["sunday"] = [
        #         {"open": '0800', "close": '1225',"id": str(uuid.uuid1()), "isOpen": False}
        #         ]

        list_to_insert = []
        location_group_list = []

        for w_i, worker in enumerate(self.worker_log_dict):
            if w_i > nbr_workers:
                break
            _business_hour = {}
            for i, day_str in enumerate(
                [
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                ]
            ):
                # if w_i % 4 == 1:
                #     _business_hour[day_str] = [
                #         {"open": '0003', "close": '2350',"id": str(uuid.uuid1()), "isOpen": True},
                #         ]
                # else:
                _day_start = str(int(worker.get("start_seconds", 120) // 3600)).zfill(2)
                _minutes_start = str(
                    int(worker.get("start_seconds", 120) % 3600) // 60
                ).zfill(2)

                _day_end = str(int(worker.get("end_seconds", 120) // 3600)).zfill(2)
                _minutes_end = str(
                    int(worker.get("end_seconds", 120) % 3600) // 60
                ).zfill(2)

                _business_hour[day_str] = [
                    # {"open": f"{_day_start}{_minutes_start}", "close": f"{_day_end}{_minutes_end}","id": str(uuid.uuid1()), "isOpen": True},
                    # Two shifts for bogota school bus
                    {
                        "open": "0005",
                        "close": "2330",
                        "id": str(uuid.uuid1()),
                        "isOpen": True,
                    },
                ]
            if "create" in worker:
                if worker["create"] == "N":
                    print("worker {} is skipped".format(worker["worker_code"]))
                    continue

            __capacity_weight = worker.get("capacity_weight", 0)
            if __capacity_weight == 0:
                __capacity_weight = worker.get("max_nbr_order", 0)
            _volume_ = worker.get("capacity_volume", 0)

            worker_code = "{}${}".format(self.api_adapter.team_code, worker["worker_code"])
            myobj = {
                "code": worker_code,
                "name": worker["worker_code"],
                "location": {
                    "code": f"wloc_{worker['worker_code']}",
                    "geo_longitude": self.CENTER_LONGLAT[0], 
                    "geo_latitude": self.CENTER_LONGLAT[1],  
                },
                "auth_username": None,
                "team": {
                    "code": self.api_adapter.team_code,
                },
                "flex_form_data": {
                    "area_code": worker["area_code"],
                    "level": 1,
                    "skills": "skill_1",
                    "assistant_to": None,
                    "is_assistant": False,
                    "tags": [],
                    # "accum_items":f"_weight_:{__capacity_weight};_volume_:{_volume_};_volume_:{_volume_}"
                    "capacity_weight": __capacity_weight,
                    "capacity_volume": _volume_,
                    "max_nbr_order": __capacity_weight,  #  worker.get("max_nbr_order",0),
                    "end_longitude": worker.get("end_x", 0) + self.DIFF_LONG,
                    "end_latitude": worker.get("end_y", 0) + self.DIFF_LAT,
                    "regist_default_account": True,
                },
                "business_hour": _business_hour,
                "auto_planning": True,
                "is_shift_started": False,
                "shift_duration_minutes": 480,
                "is_active": True,
            }
            list_to_insert.append(myobj)

            lg = {
                "code": "LG{}".format(worker["worker_code"]),
                "team": {"code": self.api_adapter.team_code},
                "requested_primary_worker": {"code": worker_code},
            }
            location_group_list.append(lg)

        self.api_adapter.insert_all_workers(list_to_insert)

        self.api_adapter.insert_all_location_group(location_group_list)

    def create_job_from_log(
        self,
        logged_job,
        auto_planning=True,
        add_noise=True,
        inplanning=False,
        min_seconds=0,  # to 2nd day
    ):
        random_noise = random.randint(1, 6) if add_noise else 0

        team_id = self.api_adapter.team_id
        team = {
            "id": team_id,
            "code": self.api_adapter.team_code,
        } 
        job_seq = logged_job["seq"]

        order_code = f"{self.api_adapter.team_code}${job_seq}"  # {str(random_noise)}

        drop_job = copy.deepcopy(SAMPLE_JOB_TEMPLATE)
        drop_job["code"] = f"{order_code}-0"
        
        drop_job["order_code"] = order_code
        drop_job["name"] = logged_job.get("job_name", None)
        drop_job["team"] = team
        drop_job["team_id"] = team_id
        mandatory_assign = logged_job["mandatory_assign"]
        if mandatory_assign == 'not_mandatory':
            drop_job["requested_primary_worker_code"] = None
            drop_job["requested_primary_worker"] = None 
        else:
            drop_job["requested_primary_worker_code"] = f"{self.api_adapter.team_code}${mandatory_assign}"
            drop_job["requested_primary_worker"] = {
                "code": f"{self.api_adapter.team_code}${mandatory_assign}",
                "team": {"code":self.api_adapter.team_code}
            }
        drop_job["planning_status"] = "U"
        drop_job["location_code"] = None

        drop_job["geo_longitude"] = logged_job["end_x"] +  self.DIFF_LONG
        drop_job["geo_latitude"] = logged_job["end_y"] +  self.DIFF_LAT
        drop_job["tolerance_start_minutes"] = 0
        drop_job["tolerance_end_minutes"] = 15 + TOLERANCE_MINUTES
        start_seconds = logged_job["start_seconds"]
        if start_seconds < min_seconds:
            start_seconds = min_seconds
        drop_job["requested_start_datetime"] = datetime.strftime(
            self.api_adapter.env_start_datetime + timedelta(seconds=start_seconds),
            "%Y-%m-%dT%H:%M:%S",
        )
        drop_job["flex_form_data"] = {
            k: logged_job[k]
            for k in logged_job.keys()
            if (k[:7] != "Unnamed" and not pd.isna(logged_job[k]))
        }
        drop_job["flex_form_data"]["area_code"] = logged_job["area_code"]
        drop_job["flex_form_data"]["weight"] = logged_job.get("weight", 0)
        drop_job["flex_form_data"]["volume"] = logged_job.get("volume", 0)
        _minutes_start = int(start_seconds // 60)
        _minutes_end = int(logged_job.get("end_seconds", 23 * 60 * 60) // 60)

        drop_job["flex_form_data"][
            "time_window_list"
        ] = f"{_minutes_start},{_minutes_end}"
        drop_job["auto_planning"] = auto_planning

        if inplanning:
            drop_job["planning_status"] = "I"
            drop_job["auto_planning"] = False
            drop_job["scheduled_primary_worker_code"] = logged_job["worker_code"]
            drop_job["scheduled_primary_worker"] = {
                "code": logged_job["worker_code"],
                "team": team,
            }

            drop_job["scheduled_start_datetime"] = datetime.strftime(
                self.api_adapter.env_start_datetime + timedelta(seconds=logged_job["end_seconds"]),
                "%Y-%m-%dT%H:%M:%S",
            )

        requested_items = []

        requested_items_list = logged_job.get("requested_items", "").split(":")
        for ri in requested_items_list:
            if len(ri) < 2:
                continue
            if len(ri.split("_")) == 2:
                name, qty = ri.split(":")
            else:
                name = ri
                qty = 1
            requested_items.append(f"{name}:{qty}")


        order_begin_time = datetime.now()

        result = self.api_adapter.insert_job(myobj=drop_job)
        order_elapsed = (datetime.now() - order_begin_time).total_seconds()
        with lock:
            order_seconds.append(order_elapsed)

        if result:
            if "status" not in result:
                print(
                    "Order {} failed with  result {}...".format(
                        drop_job["code"], result
                    )
                )
                self.failed_jobs_dict[drop_job["code"]] = drop_job
                return result

            if result["status"] != "COMMITTED":
                print(
                    "Order {} created with status {}...".format(
                        drop_job["code"], result["status"]
                    )
                )
                self.failed_jobs_dict[drop_job["code"]] = drop_job
                return result

            self.track_jobs(result)

        else:
            print("Order {} failed ...".format(drop_job["code"]))
            self.failed_jobs_dict[drop_job["code"]] = drop_job

        return result

