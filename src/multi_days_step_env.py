
import random
from datetime import datetime, timedelta

import pandas as pd
import logging
import uuid
import copy


log = logging.getLogger("single_step_env") 
import random


order_seconds = []
TOLERANCE_MINUTES = 1200
REALTIME_START_HORIZON_MINUTES = 10 * 60  #  129000 / 60#  + 100 - (9 * 60)
from util import StepEnv, SAMPLE_JOB_TEMPLATE, SAMPLE_ORDER_TEMPLATE, lock, day_seq2day_str




log = logging.getLogger("multi_days_step_env")


import random

from threading import Lock

lock = Lock()
order_seconds = []
TOLERANCE_MINUTES = 1200
REALTIME_START_HORIZON_MINUTES = 10 * 60  #  129000 / 60#  + 100 - (9 * 60)

class MultiDaysStepEnv(StepEnv):

    def load_worker_job_logs(self):
        nbr_sampled_workers = int(self.config.get("nbr_sampled_workers", 16))
        nbr_sampled_jobs = int(self.config.get("nbr_sampled_jobs", 160))

        self.worker_log_df = (
            pd.read_csv(
                "{}/worker.csv".format(self.config["simulation_log_dir"]),
                header=0,
                sep=",",
                encoding="utf_8",
            )  # .sample(n=nbr_sampled_workers, random_state=nbr_sampled_workers)
            .sort_values(by=["seq"])
            .reset_index()
        )
        self.worker_log_dict = self.worker_log_df.to_dict(orient="records")
        self.worker_log_iloc = 0

        self.job_log_df = (
            pd.read_csv(
                "{}/visit.csv".format(self.config["simulation_log_dir"]),
                header=0,
                sep=",",
                encoding="utf_8",
            )  # .sample(n=nbr_sampled_jobs, random_state=nbr_sampled_jobs)
            .sort_values(by=["seq"])
            .reset_index()
        )

        self.job_log_dict = self.job_log_df.to_dict(orient="records")
        self.job_log_iloc = -1

        try:
            self.team_df = pd.read_csv(
                    "{}/team.csv".format(self.config["simulation_log_dir"]),
                    header=0,
                    sep=",",
                    encoding="utf_8",
                )
            self.team_config_dict = self.team_df.to_dict(orient="records")[0]
        except:
            self.team_config_dict = {}
        print(
            f"Loaded {self.worker_log_df.count().max()} worker logs, {self.job_log_df.count().max()} job logs from {self.config['simulation_log_dir']}/job_log.csv..."
        )

    def _move_to_next_unplanned_job(self):
        self.current_step += 1
        self.job_log_iloc += 1
        if self.job_log_iloc >= len(self.job_log_dict):
            log.warning("reached len(self.job_log_dict), returning DONE=TRUE")
            return None
        return  self.job_log_dict[self.job_log_iloc]


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

    def generate_all_workers(self, use_fixed_location=True, nbr_workers=16):
        """example code for worker creation:"""

        # _business_hour["sunday"] = [
        #         {"open": '0130', "close": '2525',"id": str(uuid.uuid1()), "isOpen": True}
        #         ]

        list_to_insert = []
        location_group_list = []

        for w_i, worker in enumerate(self.worker_log_dict):
            if w_i > nbr_workers:
                break
            _business_hour = {}
            for bh in worker["business_hour"].split(";"):
                b = bh.split(":")
                day_str = day_seq2day_str[int(b[0])]
                _business_hour[day_str] = [
                    {
                        "open": b[1],
                        "close": b[2],
                        "id": str(uuid.uuid1()),
                        "isOpen": True if (int(b[2]) - int(b[1]) > 10) or (int(b[2]) - int(b[1]) < 0) else False,
                    },
                ]

            myobj = {
                "code": "{}${}".format(self.api_adapter.team_code, worker["code"]),
                "name": worker["code"],
                "location": {
                    "code": f"wloc_{worker['code']}",
                    "geo_longitude": worker["geo_longitude"],
                    "geo_latitude": worker["geo_latitude"],
                },
                "auth_username": None,
                "team": {
                    "code": self.api_adapter.team_code,
                },
                "flex_form_data": {
                    "skills": worker["skills"],
                    "end_longitude": worker.get("geo_longitude", 0),
                    "end_latitude": worker.get("geo_latitude", 0),
                    "regist_default_account": False,
                },
                "business_hour": _business_hour,
                "auto_planning": True,
                "is_shift_started": False,
                "shift_duration_minutes": 480,
                "is_active": True,
            }
            list_to_insert.append(myobj)

        self.api_adapter.insert_all_workers(list_to_insert)

    def create_job_from_log(
        self,
        logged_job,
        auto_planning=False,
        add_noise=False,
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
        drop_job["name"] = logged_job.get("job_name", order_code)
        drop_job["team"] = team
        drop_job["team_id"] = team_id
        drop_job["requested_primary_worker_code"] = None
        drop_job["planning_status"] = "U"
        drop_job["location_code"] = None

        drop_job["geo_longitude"] = logged_job["geo_longitude"] + (random_noise * 0.001)
        drop_job["geo_latitude"] = logged_job["geo_latitude"] + (random_noise * 0.001)
        drop_job["tolerance_start_minutes"] = logged_job["tolerance_start_minutes"]
        drop_job["tolerance_end_minutes"] = logged_job["tolerance_end_minutes"]


        drop_job["requested_start_datetime"] = logged_job["requested_start_datetime"]
        drop_job["requested_duration_minutes"] = logged_job["requested_duration_minutes"]
        drop_job["flex_form_data"] = {
            k: logged_job[k]
            for k in logged_job.keys()
            if (k[:7] != "Unnamed" and not pd.isna(logged_job[k]))
        }


        drop_job["flex_form_data"]["service_window"]  = logged_job["service_window"]
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
                self.env_start_datetime + timedelta(seconds=logged_job["end_seconds"]),
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
