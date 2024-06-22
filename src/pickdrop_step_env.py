




import random
from datetime import datetime, timedelta

import pandas as pd
import logging
import uuid
import copy


log = logging.getLogger("pickdrop_step_env") 


order_seconds = []
TOLERANCE_MINUTES = 1200
REALTIME_START_HORIZON_MINUTES = 10 * 60  #  129000 / 60#  + 100 - (9 * 60)
from util import StepEnv, SAMPLE_JOB_TEMPLATE, SAMPLE_ORDER_TEMPLATE, lock


class PickDropStepEnv(StepEnv):
    job_generation_max_count = 9999

    def load_worker_job_logs(self):
        nbr_sampled_workers = int(self.config.get("nbr_sampled_workers", 16))
        nbr_sampled_jobs = int(self.config.get("nbr_sampled_jobs", 160))

        self.worker_log_df = (
            pd.read_csv(
                "{}/worker_log.csv".format(self.config["simulation_log_dir"]),
                header=0,
                sep=",",
                encoding="utf_8",
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
            )  # .sample(n=nbr_sampled_jobs, random_state=nbr_sampled_jobs)
            .sort_values(by=["start_seconds"])
            .reset_index()
        )
        self.job_log_dict = self.job_log_df.to_dict(orient="records")

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

        log.info(f"Loaded {self.worker_log_df.count().max()} worker logs, {self.job_log_df.count().max()} job logs ...")

    def _move_to_next_unplanned_job(self):
        self.current_step += 1
        if self.job_log_iloc > self.job_generation_max_count or (
            self.job_log_iloc >= len(self.job_log_dict)
        ):
            log.warning("reached len(self.job_log_dict), returning DONE=TRUE")
            self.job_log_iloc += 1
            return None
        else:
            temp_job_dict = self.job_log_dict[self.job_log_iloc]
            # job_code = temp_job_dict["job_code"]
            _s = temp_job_dict["start_seconds"]
            # new_till_minutes =( ((_s - 39000 ) / 1.1) + 39000)/60
            new_till_minutes = _s / 60
            if new_till_minutes > self.till_minutes:
                self.till_minutes = new_till_minutes
                self.mutate_job_state_before_minutes()
                self.mutate_worker_state_before_minutes(self.till_minutes)

                start_datetime = datetime.strftime(
                    self.api_adapter.env_start_datetime
                    + timedelta(seconds=temp_job_dict["start_seconds"]),
                    "%Y-%m-%dT%H:%M:%S",
                )

                print("set_horizon_start_minutes", start_datetime)
                self.api_adapter.set_horizon_start_minutes(
                    team_id=self.api_adapter.team_id,
                    start_datetime=start_datetime,
                )
            self.job_log_iloc += 1
            return temp_job_dict


    def generate_all_workers(
        self, _business_hour = None
    ):
        """example code for worker creation:"""

        # _business_hour["sunday"] = [
        #         {"open": '0130', "close": '2525',"id": str(uuid.uuid1()), "isOpen": True}
        #         ]
        # _business_hour["sunday"] = [
        #         {"open": '0800', "close": '1225',"id": str(uuid.uuid1()), "isOpen": False}
        #         ]

        list_to_insert = []
        location_group_list = []
        if _business_hour is None:
            _business_hour = {}
            night_business_hour = {}
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
                night_business_hour[day_str] = [
                    {
                        "open": "2130",
                        "close": "4525",
                        "id": str(uuid.uuid1()),
                        "isOpen": True,
                    }, 
                ] 
                _business_hour[day_str] = [
                    {
                        "open": "0003",
                        "close": "2355",
                        "id": str(uuid.uuid1()),
                        "isOpen": True,
                    },
                ]
        for w_i, worker in enumerate(self.worker_log_dict):

            if "create" in worker:
                if worker["create"] == "N":
                    print("worker {} is skipped".format(worker["worker_code"]))
                    continue
            myobj = {
                "code": "{}${}".format(self.api_adapter.team_code, worker["worker_code"]),
                "name": worker["worker_code"],
                "location": {
                    "code": f"wloc_{worker['worker_code']}",
                    "geo_longitude": worker["start_x"],  # +(random.randint(2,9)/1000),
                    "geo_latitude": worker["start_y"],  # +(random.randint(2,9)/1000),
                    # "geo_address_text": "",
                    # "geo_json":{},
                },
                "auth_username": None,
                "team": {
                    "code": self.api_adapter.team_code,
                },
                "flex_form_data": {
                    "area_code": worker["area_code"],
                    "level": 1,
                    "skills": ["skill_1"],
                    "assistant_to": None,
                    "is_assistant": False,
                    "tags": [],
                    "request_worker": "",
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
                "team": {"code": "default_team"},
                "requested_primary_worker": {"code": worker["worker_code"]},
            }
            location_group_list.append(lg)

        self.api_adapter.insert_all_workers(list_to_insert)

        self.api_adapter.insert_all_location_group(location_group_list)

    def create_job_from_log(
        self,
        logged_job,
        auto_planning=True,
        order_flex_form_data=None,
        order_code=None,
        skip_error=True,
    ):
        team_id = self.api_adapter.team_id
        team = {
            "id": team_id,
            "code": self.api_adapter.team_code,
        }
        order_dict = copy.deepcopy(SAMPLE_ORDER_TEMPLATE)

        if not order_code:
            job_seq = logged_job["seq"]
            order_code = f"{self.api_adapter.team_code}${job_seq}"

        order_dict["code"] = order_code
        order_dict["team"] = team
        order_dict["team_id"] = team_id

        order_dict["job_list"] = []
        order_dict["team_id"] = team_id

        lg_code = None
        # if "location_group_code" in logged_job:
        #     if not pd.isnull(logged_job["location_group_code"]):
        #         lg_code = logged_job["location_group_code"]

        order_dict["location_group_code"] = lg_code
        order_dict["accept_order"] = logged_job["accept_order"]
        order_dict["flex_form_data"]["area_code"] = logged_job["area_code"]
        order_dict["mandatory_assign"] = logged_job["mandatory_assign"]

        new_job = copy.deepcopy(SAMPLE_JOB_TEMPLATE)
        new_job["code"] = f"{order_code}-p"
        new_job["order_code"] = order_code
        new_job["team"] = team
        new_job["team_id"] = team_id
        # 参考 ： https://sgprd1.easydispatch.uk/ed/api/v1/docs/#tag/jobs/operation/create_job_jobs__post
        # 每个状态的意义。
        new_job["planning_status"] = "U"

        new_job["location_code"] = None
        new_job["geo_longitude"] = logged_job["start_x"]
        new_job["geo_latitude"] = logged_job["start_y"]
        new_job["requested_primary_worker_code"] = None
        new_job["tolerance_start_minutes"] = 0
        new_job["flex_form_data"]["area_code"] = logged_job["area_code"]
        # -10000 end_seconds 超时时间, 即为 货物送达的可延迟时间
        duration = (logged_job["end_seconds"] - logged_job["start_seconds"]) / 60
        if duration < 15:
            duration = 15
        new_job["tolerance_end_minutes"] = (
            15 + TOLERANCE_MINUTES
        )  # logged_job["start_y"]
        new_job["requested_start_datetime"] = datetime.strftime(
            self.api_adapter.env_start_datetime + timedelta(seconds=logged_job["start_seconds"]),
            "%Y-%m-%dT%H:%M:%S",
        )
        if logged_job.get("pick_job_planning_status", None):
            new_job["planning_status"] = "F"

        order_dict["job_list"].append(new_job)

        drop_job = copy.deepcopy(SAMPLE_JOB_TEMPLATE)
        drop_job["code"] = f"{order_code}-d"
        drop_job["order_code"] = order_code
        drop_job["team"] = team
        drop_job["team_id"] = team_id
        drop_job["requested_primary_worker_code"] = None
        drop_job["planning_status"] = "U"
        drop_job["location_code"] = None
        drop_job["geo_longitude"] = logged_job["end_x"]
        drop_job["geo_latitude"] = logged_job["end_y"]
        drop_job["tolerance_start_minutes"] = 0
        drop_job["tolerance_end_minutes"] = (
            duration + 15 + TOLERANCE_MINUTES
        )  #  30  # logged_job["start_y"]
        drop_job["requested_start_datetime"] = datetime.strftime(
            self.api_adapter.env_start_datetime
            + timedelta(seconds=logged_job["start_seconds"] + (60 * 60)),
            "%Y-%m-%dT%H:%M:%S",
        )
        drop_job["flex_form_data"]["area_code"] = logged_job["area_code"]

        order_dict["job_list"].append(drop_job)

        order_begin_time = datetime.now()

        if logged_job.get("auto_planning", None) == "N":
            target_auto_planning = False
        elif logged_job.get("auto_planning", None) == "Y":
            target_auto_planning = True
        else:
            target_auto_planning = auto_planning

        order_dict["auto_planning"] = target_auto_planning
        for line in order_dict["job_list"]:
            line["auto_planning"] = target_auto_planning

        result = self.api_adapter.insert_order(order_dict)

        order_elapsed = (datetime.now() - order_begin_time).total_seconds()
        with lock:
            order_seconds.append(order_elapsed)

        if result:
            if result["status"] != "COMMITTED":
                print(
                    "Order {} failed with status {}...".format(
                        order_dict["code"], result["status"]
                    )
                )
                order_dict["result"] = result
                self.failed_jobs_dict[order_dict["code"]] = order_dict
            else:
                self.track_jobs(result)

            if order_dict["accept_order"] == "N":
                assert result["status"] == "COMMITTED", "Before setting accept_order to replan, it should have been planned correctly"

                request_dict = {
                    "order_code": order_dict["code"],
                    "allow_same_worker": False,
                }

                result = self.api_adapter.replan_order(request_dict)
                if result is None or result["status"] != "COMMITTED":
                    print("job {} failed after reject order".format(order_dict["code"]))
                    self.failed_jobs_dict[order_dict["code"]] = order_dict
                else:
                    print(
                        "job {} is rescheduled to worker {}".format(
                            order_dict["code"], result["worker_code"]
                        )
                    )
                    self.track_jobs(result)

            if order_dict["mandatory_assign"] != "not_mandatory":
                overwrite_max_orders_limit = True
                if logged_job.get("overwrite_max_orders_limit", None) == "N":
                    overwrite_max_orders_limit = False

                request_dict = {
                    "order_code": order_dict["code"],
                    "allow_same_worker": True,
                    "target_worker": "{}${}".format(self.api_adapter.team_code, order_dict["mandatory_assign"]) ,
                    "overwrite_max_orders_limit": overwrite_max_orders_limit,
                }
                result = self.api_adapter.replan_order(request_dict)
                if result is None or result["status"] != "COMMITTED":
                    print(
                        "job {} failed after manual intervention".format(
                            order_dict["code"]
                        )
                    )
                    self.failed_jobs_dict[order_dict["code"]] = order_dict
                else:
                    print(
                        "job {} is replanned successfully to worker {}".format(
                            order_dict["code"], result["worker_code"]
                        )
                    )
                    self.track_jobs(result)
            if logged_job.get("pick_job_planning_status", None) == "Y":
                assert result["status"] == "COMMITTED", "Before setting pick_job_planning_status to F, it should have been planned correctly"
                param = {
                    "code": new_job["code"],
                    "life_cycle_status": "F",
                    "update_source": "life_cycle",
                    "comment": None,
                }
                self.api_adapter.update_job_life_cycle(param)
            return result

        else:
            print("Order {} failed ...".format(order_dict["code"]))
            self.failed_jobs_dict[order_dict["code"]] = order_dict
            assert skip_error, "Failed when not skip_error"

        return result
