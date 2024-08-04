import logging

from kplanner_api_adapter import KPlannerAPIAdapter
from single_job_step_env import SingleStepEnv 
from util import set_team_flex_form, getWorkerJob, clear_team_data

from datetime import datetime,timedelta
import os



server_url = os.getenv('server_url')
team_code= os.getenv('team_code')
current_dir = os.getcwd()

api_adapter =  KPlannerAPIAdapter( 
        service_url=server_url,
        username=os.getenv('email'),
        password=os.getenv('password'),
        # access_token=token,
        team_code=team_code,
        log_level=logging.DEBUG,
        verify_ssl=True,
        org_id=-1,
        sleep_before_call = False,
    )

team_config = {
    "fixed_horizon_flag": "1",
    "nbr_minutes_planning_windows_duration": 1440,
    "env_start_datetime": "2024-02-14T00:00:00",
    "horizon_start_datetime": "2024-02-14T02:01:01",

    "tile_server_url": "https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}",
    "enabled_rule_codes": "basic;area_code", # ;tolerance_check;geo_merge;max_pick2drop_merge

    # "enable_accum_items": "1", 
    # "front_routing_type": "polyline",
    # "front_routing_url": "",

    # "load_init_stock": 0, 
    # "log_search_progress": 0, 
    # "max_exec_seconds": 28, 

    # "enable_weight_constraint": 1, 
    # "enable_volume_constraint": 1, 
    # "enable_location_group_constraint": 0, 
    # "enable_time_window_constraint": 1, 
    # "run_pickup_job_dispatching": 1, 
    # "plan_all_to_beginning_no_travel": 0, "travel_minutes_scale_factor": 1, "weight_constraint_code": "weight", 
    # "enable_return2home_constraint": 0, 
    # "meter_search_radius": 60000,
    # "max_job_in_worker_size":15
    # "team_geo_longitude":  ,
    # "team_geo_latitude": ,
}



if __name__ == "__main__" :
    CENTER_LONGLAT = (118.0128, 36.8389)
    config= { 
        "simulation_log_dir": "{}/src/data/data1".format(current_dir) , 
        "geo_longitude" : CENTER_LONGLAT[0],
        "geo_latitude" : CENTER_LONGLAT[1],   
        "CENTER_LONGLAT": CENTER_LONGLAT,
        "planner_service_code": "single_area_code_cvrp",
        "team_config":team_config
    }

    env = SingleStepEnv(config, api_adapter = api_adapter) 
    env.api_adapter.switch_team_by_code(team_code, config = config)

    clear_team_data(env=env) 
    set_team_flex_form( env,team_config, reset_planning_window = True) 
    
    env.generate_all_workers(
            use_fixed_location = False, 
            nbr_workers=115)
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
        job_dict = env._move_to_next_unplanned_job(mutate_state = False)
        if not job_dict:
                print(f"Finished {order_count} steps!")
                break
        if stepi < 2:
                auto_planning = True
        else:
                auto_planning = False
        order_count += 1
        resa = env.create_job_from_log(logged_job=job_dict, auto_planning=auto_planning, add_noise=False)
        if auto_planning:
            assert resa["status"] == 'COMMITTED', "committed"
            if job_dict["mandatory_assign"] != "not_mandatory":
                assert resa["worker_code"] == team_code + "$" + job_dict["mandatory_assign"]

    env.api_adapter.run_batch_optimizer(param = {
            "team_code": env.api_adapter.team_code,
            "area_codes":"A"
        })
    worker_dic = getWorkerJob(env=env, status_list = ["I", "F"])
    print("totally {} jobs planned".format(sum([len(lst) for lst in worker_dic.values ()])))

   
    

    
   











