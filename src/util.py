from threading import Lock
lock = Lock()
from kplanner_api_adapter import KPlannerAPIAdapter
from datetime import datetime, timedelta



def set_team_flex_form(env, new_config = {}, reset_planning_window = True): 
    team = env.api_adapter.team # env.api_adapter.get_all_teams()["items"][0]
    if "team_geo_longitude" in   new_config:
        team["geo_longitude"] = float(new_config["team_geo_longitude"])
        team["geo_latitude"] = float(new_config["team_geo_latitude"])

    team["flex_form_data"].update(new_config)

    env.api_adapter.update_team(team = team)
    if reset_planning_window:
        env.api_adapter.reset_planning_window(team_code=env.api_adapter.team_code)


def clear_team_data(env,itemsPerPage:int=500):
    # 查询所有order , 
    # 先删除所有 job_event , job , order_event ,order 
    orders = env.api_adapter.get_all_orders(itemsPerPage=itemsPerPage)
    if orders['total'] >0:
        # pickdrop
        for order in orders["items"]:
            delete_order_result = env.api_adapter.delete_orders(order_code=order['code'])
            print( delete_order_result)
    else:
        # drop
        jobs = env.api_adapter.get_all_jobs(items_per_page=itemsPerPage)
        if jobs['total'] >0:
            for job in jobs['items']:
                delete_job_result=env.api_adapter.delete_job_and_job_event(job['code'])
                print(delete_job_result)
                
    print("order job is deleted ")
    
    # 先删除 locatioin_group 
    lg_list = env.api_adapter.get_all_location_groups()
    for lg in lg_list["items"]: 
        location_group_result = env.api_adapter.delete_location_group(code = lg['code'])
        print(location_group_result)

    # 删除所有 worker 
    workers =  env.api_adapter.get_all_workers(itemsPerPage=itemsPerPage)
    if workers['total'] >0:    
        for worker in workers["items"]:
            
            worker_result = env.api_adapter.delete_worker(worker['code'])
            print(worker_result)
            location_result = env.api_adapter.delete_locations(f"wloc_{worker['code']}")
            print(location_result)
    print("clear worker data is ok ")


    print("#"*20)
    print("Done cleaning up team data!")


def getWorkerJob(env, status_list = ["I",]):
    result = env.api_adapter.get_all_jobs()
    woker_dic = {}
    print("SELECT JOBS ")
    for job in result["items"]:
        if job['scheduled_primary_worker_code'] and job["planning_status"] in status_list :
            scheduled_primary_worker_code = job['scheduled_primary_worker_code']
            code = job['code']
            if scheduled_primary_worker_code not in woker_dic:
                woker_dic[scheduled_primary_worker_code] = [code]
            else:
                woker_dic[scheduled_primary_worker_code].append(code)
    print(woker_dic)
    return woker_dic
 



SAMPLE_ORDER_TEMPLATE = {
    "code": "12",
    "external_order_code": "TS12",
    "order_source_code": "SOURCE1",
    "business_code": "delivery",
    "flex_form_data": {},
    "external_business_status": None,
    "status_code": "sync",
    "business_order_status": "inbound_success",
    "reason_code": None,
    "external_order_status": "status1",
    "order_exception_status": None,
    "order_type": "pickdrop",
    "start_time": None,
    "scheduled_primary_worker_code": None,
    "is_deleted": 0,
    "auto_planning": True,
    "auto_commit": True,
}



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


class StepEnv:
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
        
    def mutate_job_state_before_minutes(
        self,
    ):
        deleted_jobs = []
        # return
        with lock:
            for job_code, job in self.jobs_dict.items():
                job_datetime = datetime.strptime(
                    job["scheduled_start_datetime"], "%Y-%m-%dT%H:%M:%S"
                )
                if job_datetime <= self.api_adapter.env_start_datetime + timedelta(
                    minutes=self.till_minutes
                ):
                    # If two jobs are close, or in same position, they will be completed in same loop.
                    env_job = self.api_adapter.get_job(job_code=job["code"])
                    print(
                        f"Job {job['code']}, time {job_datetime} is done at current till minutes {self.till_minutes} !!!"
                    )
                    env_job["planning_status"] = "F"
                    # env_job["auto_planning"] = True
                    env_job["scheduled_start_datetime"] = job[
                        "scheduled_start_datetime"
                    ]
                    env_job = self.api_adapter.update_job(env_job)
                    deleted_jobs.append(job_code)

            for job_code in deleted_jobs:
                del self.jobs_dict[job_code]
            # self.mutate_complete_db_job(db_job, job.prev_travel, job.scheduled_start_minutes)
    def mutate_worker_state_before_minutes(self, new_till_minutes):
        for w_i, worker in self.worker_log_df.iterrows():
            worker_start_minutes = worker.start_seconds / 60
            if worker_start_minutes > new_till_minutes:
                return
            if w_i < self.worker_log_iloc:
                continue

            shift_start_datetime = datetime.strftime(
                self.api_adapter.env_start_datetime + timedelta(seconds=worker.start_seconds),
                "%Y-%m-%dT%H:%M:%S",
            )
            worker_end_minutes = worker.end_seconds / 60
            if worker_end_minutes < new_till_minutes:
                # 过了时间，让worker下线
                if (
                    int(self.config.get("slot_by_shift_start", 0)) == 1
                    and worker.worker_code in self.workers_dict
                ):
                    update_dict = {
                        "worker_code": worker.worker_code,
                        "action_type": "end_shift",
                        "shift_start_datetime": shift_start_datetime,
                        "shift_duration_minutes": 8 * 60,
                        "start_longitude": worker.start_x,
                        "start_latitude": worker.start_y,
                        "end_longitude": worker.end_x,
                        "end_latitude": worker.end_y,
                    }
                    self.api_adapter.update_worker_status(update_dict)
                    # It is ok to ignore "The requested shift does not exist". It might be purged after end minutes
                    del self.workers_dict[worker.worker_code]
                    continue

            if "update_location_only" in worker:
                if worker["update_location_only"] == "Y":
                    update_dict = {
                        "worker_code": worker.worker_code,
                        "action_type": "update_location",
                        "shift_start_datetime": shift_start_datetime,
                        "shift_duration_minutes": 8 * 60,
                        "start_longitude": worker.start_x,
                        "start_latitude": worker.start_y,
                        "end_longitude": worker.end_x,
                        "end_latitude": worker.end_y,
                    }
                    self.api_adapter.update_worker_status(update_dict)
                    self.workers_dict[worker.worker_code] = update_dict
                    print(
                        "worker {} is updated with new location {}, {}".format(
                            worker["worker_code"],
                            worker.start_x,
                            worker.start_y,
                        )
                    )

                    continue

            if int(self.config.get("slot_by_shift_start", 0)) == 1:
                print(f"Activating shift for worker {worker.worker_code}")
                self.worker_log_iloc += 1
                # # 这里负责上线，
                update_dict = {
                    "worker_code": worker.worker_code,
                    "action_type": "begin_shift",
                    "shift_start_datetime": shift_start_datetime,
                    "shift_duration_minutes": 8 * 60,
                    "start_longitude": worker.start_x,
                    "start_latitude": worker.start_y,
                    "end_longitude": worker.end_x,
                    "end_latitude": worker.end_y,
                }
                self.api_adapter.update_worker_status(update_dict)
                self.workers_dict[worker.worker_code] = update_dict

day_seq2day_str = {
    0: 'sunday',
    1: 'monday',
    2: 'tuesday',
    3: 'wednesday',
    4: 'thursday',
    5: 'friday',
    6: 'saturday',
}
