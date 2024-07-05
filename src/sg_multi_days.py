import logging
import os
from datetime import datetime,timedelta

from kplanner_api_adapter import KPlannerAPIAdapter
from multi_days_step_env import MultiDaysStepEnv 
from util import set_team_flex_form, getWorkerJob, clear_team_data


server_url = os.getenv('server_url')
team_code = os.getenv('team_code')
current_dir = os.getcwd()

api_adapter =  KPlannerAPIAdapter( 
        service_url=server_url,
        username=os.getenv('email'),
        password=os.getenv('password'),

        team_code=team_code,
        log_level=logging.DEBUG,
        verify_ssl=True,
        org_id=-1,
        sleep_before_call = False,
    )

team_config = {
    "fixed_horizon_flag": "1",
    "env_start_datetime": "2023-11-13T00:00:00",
    "horizon_start_datetime": "2023-11-13T08:01:01",
    "nbr_minutes_planning_windows_duration": 1440,

    "enable_skills": "1",
    # "tile_server": "osm",
    # "enabled_rule_codes": "basic;area_code", # ;tolerance_check;geo_merge;max_pick2drop_merge

}


if __name__ == "__main__" :
    CENTER_LONGLAT = (103.8,1.3)
    config= { 
        "simulation_log_dir": "{}/src/data/multi_days".format(current_dir) , 
        "geo_longitude" : CENTER_LONGLAT[0],
        "geo_latitude" : CENTER_LONGLAT[1],   
        "CENTER_LONGLAT": CENTER_LONGLAT,
        "planner_service_code": "single",
        "team_config":team_config
    }

    env = MultiDaysStepEnv(config, api_adapter = api_adapter) 
    env.api_adapter.switch_team_by_code(team_code, config = config)

    clear_team_data(env=env) 
    set_team_flex_form(env,team_config, reset_planning_window = True) 
    
    env.generate_all_workers()
    env.api_adapter.reset_planning_window(team_code=env.api_adapter.team_code)
   
    init_worker_dic = getWorkerJob(env=env)
    assert sum([len(lst) for lst in init_worker_dic.values ()]) == 0, "Start from an empty team"

    nbr_initial_steps = int(env.config.get("nbr_initial_steps", 100))
    order_count = 0
 
    round_1_dt = datetime.strftime(
            env.api_adapter.env_start_datetime + timedelta(minutes=600),
            "%Y-%m-%dT%H:%M:%S")


    res1 = env.api_adapter.get_planner_worker_job_dataset()
    env.api_adapter.set_horizon_start_minutes(
                    team_id=env.api_adapter.team_id,
                    start_datetime=round_1_dt
                )
    for stepi in range(nbr_initial_steps):
        job_dict = env._move_to_next_unplanned_job()
        if not job_dict:
                print(f"Finished {order_count} steps!")
                break
        
        order_count += 1
        resa = env.create_job_from_log(logged_job=job_dict, auto_planning=False, add_noise=False)

    env.api_adapter.run_batch_optimizer(param = {
            "team_code": env.api_adapter.team_code,
            "area_codes":"A"
        })
    worker_dic = getWorkerJob(env=env, status_list = ["I", "F"])
    assert f"{team_code}$W2031" in worker_dic, "get_env_jobs target"  
    W2031_jobs = worker_dic[f"{team_code}$W2031"]
    assert f"{team_code}$31-0" in W2031_jobs, "determined by skills"  
    assert f"{team_code}$80-0"  == W2031_jobs[2], "determined by skills and sequence should be right"  

    print("totally {} jobs planned".format(sum([len(lst) for lst in worker_dic.values ()])))

   
    

    
   











