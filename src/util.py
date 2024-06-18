
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
 
