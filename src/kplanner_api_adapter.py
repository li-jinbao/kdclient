import requests as http_requests
import time  
from datetime import datetime
import logging

log = logging.getLogger(__name__)


class KPlannerAPIAdapter:
    def __init__(
        self,
        service_url=None,
        username=None,
        password=None,
        access_token=None,
        team_code=None,
        log_level=logging.DEBUG,
        verify_ssl=True,
        org_id=-1,
        sleep_before_call = False,
    ):
        self.requests = http_requests
        self.verify_ssl = verify_ssl
        self.service_url = service_url
        self.org_id = org_id
        self.sleep_before_call = sleep_before_call

        if not access_token:
            self.access_token = self.get_access_token(username=username, password=password)
        else:
            self.access_token = access_token

        self.user_profile = self.get_profile()

        if team_code is None:
            self.team_code = "default_team"
        else:
            self.team_code = team_code
        
        log.setLevel(log_level)


    def try_sleep(self):
        if self.sleep_before_call:
            time.sleep(1)

    def get_access_token(self, username=None, password=None):
        url = f"{self.service_url}/auth/login"
        login_info = {"email": username, "password": password}

        response = self.requests.post(
            url, json=login_info, headers={"Content-Type": "application/json"}, 
            # verify=self.verify_ssl
            )  # ,verify=False
        resp_json = response.json()
        self.access_token = resp_json["data"]["token"]

        self.team_id = response.json()["data"]["default_team_id"]
        self.org_id = response.json()["data"]["org_id"]
        self.team = self.get_team(team_id=self.team_id)
        self.team_code = self.team["code"]

        return self.access_token
    
    def switch_team_by_code(self, team_code, config={} ):
        try:
            t = self.get_team_by_code(team_code)
            self.team_code = t["code"]
            self.team_id = t["id"] 
            self.team = t
        except:
            team = self.create_team({ 
                "code":team_code,
                "name":team_code,
                "geo_longitude" : config["geo_longitude"],
                "geo_latitude" :  config["geo_latitude"],
                "planner_service":{"code":"single_area_code_cvrp"},
                "flex_form_data": config["team_config"] ,
            }) 
            t = self.get_team_by_code(team_code)
            self.team = t
            self.team_code = t["code"]
            self.team_id = t["id"] 
        
        self.refresh_env_start_datetime()

    def refresh_env_start_datetime(self):
        solution = self.get_planner_worker_job_dataset(
            team_id=self.team_id
        )
        try:
            self.env_start_datetime = datetime.strptime(
                solution["start_time"], "%Y-%m-%dT%H:%M:%S"
            )
        except Exception as e:
            print(f"wrong env_start_datetime, {str(e)}")

    
        
    def get_profile(self):
        self.try_sleep()
        url = f"{self.service_url}/auth/me"
        response = self.requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
            # verify=self.verify_ssl
        )
        resp_json = response.json()
        self.org_id = resp_json['org_id']

        return resp_json
    def hello(self):
        url = f"{self.service_url}/planner_service/hello"
        response = self.requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
            # verify=self.verify_ssl
        )
        hello_json = response.json() 

        return hello_json

    def insert_all_workers(self, worker_list):
        url = "{}/workers/".format(self.service_url)

        for myobj in worker_list:
            # print(myobj)
            if myobj["team"].get("code", None) is None:
                myobj["team"]["code"] = self.team_code
            # log.debug(url)
            # log.debug(myobj)
            self.try_sleep()

            response = self.requests.post(
                url,
                json=myobj,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer {}".format(self.access_token),
                },
                # verify=self.verify_ssl,
            )

            try:
                # Convert JSON to dict and print
                print("Saved worker: ", response.json()["code"])
            except:
                print("Failed to save worker: ", response.content)


    def insert_all_items(self, item_list):
        url = "{}/items/".format(self.service_url)

        for myobj in item_list:
            print(myobj)

            response = self.requests.post(
                url,
                json=myobj,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer {}".format(self.access_token),
                },
                # verify=self.verify_ssl,
            )

            try:
                # Convert JSON to dict and print
                print("Saved item: ", response.json()["code"])
            except:
                print("Failed to save item: ", response.content)

    def save_batch_worker(self, worker_list):
        url = "{}/workers/save_batch_worker/".format(self.service_url)

        response = self.requests.post(
            url,
            json=worker_list,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )

        try:
            # Convert JSON to dict and print
            print("Saved worker: ", response.json()["code"])
        except:
            print("Failed to save worker: ", response.json())

    def update_worker(self, myobj):
        self.try_sleep()
        url = "{}/workers/{}".format(self.service_url, myobj["code"])

        response = self.requests.put(
            url,
            json=myobj,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )

        try:
            # Convert JSON to dict and print
            print("updated worker: ", response.json()["code"])
        except:
            print("Failed to updated worker: ", response)

    def update_worker_bussiness_hour(self, myobj):
        self.try_sleep()
        url = "{}/workers/{}/update_business_hour".format(self.service_url, myobj["code"])
        response = self.requests.put(
            url,
            json=myobj,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        try:
            # Convert JSON to dict and print
            print("updated worker: ", response.json()["code"])
        except:
            print("Failed to updated worker: ", response)



    def update_worker_info(self, myobj):
        self.try_sleep()
        url = "{}/workers/update_worker_info".format(self.service_url)

        response = self.requests.post(
            url,
            json=myobj,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )

        try:
            # Convert JSON to dict and print
            print("updated update_worker_info done: ", myobj, response.json() )
            return response.json()
        except:
            print("Failed to update_worker_info: ", response)
            return None

    def update_worker_status(self, myobj):
        self.try_sleep()
        url = "{}/planner_service/update_worker_status".format(self.service_url)

        response = self.requests.post(
            url,
            json=myobj,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )

        try:
            # Convert JSON to dict and print
            print("updated worker done: ", myobj["worker_code"], myobj["action_type"], " result: ", response.json()["errorDescription"])
        except:
            print("Failed to updated worker status: ", response)

    def update_all_workers(self, worker_list):
        for myobj in worker_list:
            self.try_sleep()
            self.update_worker(myobj)

    def delete_all_workers(self):
        url = "{}/kpdata/workers/".format(self.service_url)
        response = self.requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        resp_json = response.json()
        # Convert JSON to dict and print
        # print(resp_json)
        if len(resp_json) < 1:
            print("it is already empty!")
            return

        for worker in resp_json:
            print("deleting worker: ", worker)
            url = "{}/kpdata/workers/".format(self.service_url) + str(worker["worker_code"]) + ""
            # print(url)
            response = self.requests.delete(
                url, headers={"Authorization": "Bearer {}".format(self.access_token)}
            )
            print(response.text)

    def get_planner_worker_job_dataset(
            self, team_id = None, active_only = True,
            worker_code_list = "ALL"):
        if team_id is None:
            team_id = self.team_id
        self.try_sleep()
        active_str = "true" if active_only else "false"
        url = "{}/planner_service/get_planner_worker_job_dataset/?team_id={}&active_only={}&worker_code_list={}".format(
            self.service_url, team_id, active_str, worker_code_list)
        response = self.requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        try:
            return response.json()
        except:
            print("Failed to get job solution", response)
            print(f"url={url}")
            return {}

    def get_env_jobs(self, myobj):
        self.try_sleep()
        url = "{}/planner_service/get_env_jobs".format(self.service_url)
        myobj["team_code"] = self.team_code
        
        response = self.requests.post(
            url,
            json=myobj,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
            # verify=self.verify_ssl,
        )
        try: 
            if response.status_code != 200:
                print(f"Failed to save order: ", myobj["order_code"], response.content)
                return None
            return response.json()
        except:
            print(f"Failed to save order: except", myobj["order_code"], response.content)
            return None

    def replan_order(self, myobj):
        self.try_sleep()
        url = "{}/planner_service/replan_order/".format(self.service_url)
        myobj["team_code"] = self.team_code
        
        response = self.requests.post(
            url,
            json=myobj,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
            # verify=self.verify_ssl,
        )
        # Convert JSON to dict and print
        try: 
            if response.status_code != 200:
                print("Failed to save order: ", myobj["order_code"], response.content)
                return None
            return response.json()
        except:
            print("Failed to save order: except", myobj["order_code"], response.content)
            return None

    def replan_job(self, myobj):
        self.try_sleep()
        url = "{}/planner_service/replan_job/".format(self.service_url)
        myobj["team_code"] = self.team_code
        
        response = self.requests.post(
            url,
            json=myobj,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
            # verify=self.verify_ssl,
        ) 
        try: 
            if response.status_code != 200:
                print("Failed to save order: ", myobj["order_code"], response.content)
                return None
            return response.json()
        except:
            print("Failed to save order: except", myobj["order_code"], response.content)
            return None

    def insert_order(self, myobj):
        self.try_sleep()
        url = "{}/orders/".format(self.service_url)
        myobj["team_code"] = self.team_code

        # log.debug(url)
        # log.debug(myobj)
        response = self.requests.post(
            url,
            json=myobj,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
            # verify=self.verify_ssl,
        )
        # Convert JSON to dict and print
        try:
            # a = response.json()["status"]
            # print("Saved job: ", response.json()["data"]["code"])
            if response.status_code != 200:
                print(f"Failed to save order != 200 : ", myobj["code"], response.content)
                return None 
            a = response.json()
            print(a)
            
            return a
        except:
            print(f" Failed to save order: except", myobj["code"], response.content)
            return None

    def insert_all_orders(self, order_list):
        for myobj in (order_list): # tqdm
            self.insert_order(myobj)

    def get_worker(self, worker_code):
        url = "{}/workers/{}".format(
            self.service_url, worker_code
        )
        response = self.requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        resp_json = response.json()

        return resp_json

    def get_job(self, job_code):
        url = "{}/jobs/{}".format(
            self.service_url, job_code
        )
        response = self.requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        resp_json = response.json()

        return resp_json

    def update_job(self, myobj):
        url = "{}/jobs/{}".format(self.service_url, myobj["code"])

        response = self.requests.put(
            url,
            json=myobj,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )

        try:
            # Convert JSON to dict and print
            print("updated job: ", response.json()["code"])
        except:
            print("Failed to updated job: ", response)


    def insert_job(self, myobj):
        url = "{}/jobs/".format(self.service_url)
        # log.debug(url)
        # log.debug(myobj)
        response = self.requests.post(
            url,
            json=myobj,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
            # verify=self.verify_ssl,
        )
        # Convert JSON to dict and print
        try:
            a = response.json()["status"]
            return response.json()
            # print("Saved job: ", response.json()["data"]["code"])
        except:
            print("Failed to save job", response.content)

    def insert_all_jobs(self, jobs_list):
        url = "{}/jobs/".format(self.service_url)
        for myobj in (jobs_list): # tqdm
            self.insert_job(myobj=myobj)

    def insert_all_depot(self, data_list):
        url = "{}/depots/".format(self.service_url)
        for myobj in (data_list): # tqdm

            response = self.requests.post(
                url,
                json=myobj,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer {}".format(self.access_token),
                },
                # verify=self.verify_ssl,
            )
            # print(response)
            # Convert JSON to dict and print
            try:
                print("Saved depot: ", response.json()["data"]["code"])
            except:
                print("Failed to save depot", response)

    def insert_all_location(self, location_list):
        url = "{}/locations/".format(self.service_url)
        for myobj in (location_list): # tqdm
            myobj["team_code"] = self.team_code

            # log.debug(url)
            # log.debug(myobj)
            response = self.requests.post(
                url,
                json=myobj,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer {}".format(self.access_token),
                },
                # verify=self.verify_ssl,
            )
            # print(response)
            # Convert JSON to dict and print
            try:
                rj = response.json()

                print("Saved location: ",  rj["code"])
            except:
                try:
                    print("Failed to save: ", response.json()["detail"])
                except:
                    print("Failed to save location", response)

    def insert_location(self, myobj):
        url = "{}/locations/".format(self.service_url)
        myobj["team_code"] = self.team_code

        # log.debug(url)
        log.debug(myobj)
        response = self.requests.post(
            url,
            json=myobj,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
            # verify=self.verify_ssl,
        )
        # print(response)
        # Convert JSON to dict and print
        try:
            return response.json()
        except:
            try:
                print("Failed to save: ", response.json()["detail"])
            except:
                print("Failed to save location", response)
            return None


    def insert_all_location_group(self, location_group_list):
        url = "{}/location_group/".format(self.service_url)
        print("Saving location group: ")
        for myobj in (location_group_list): # tqdm
            myobj["team_code"] = self.team_code

            # log.debug(url)
            # log.debug(myobj)
            response = self.requests.post(
                url,
                json=myobj,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer {}".format(self.access_token),
                },
                # verify=self.verify_ssl,
            )
            # print(response)
            # Convert JSON to dict and print
            try:
                rj = response.json()

                # print("Saved location group: ", rj["code"])
            except:
                try:
                    print("Failed to save: ", response.json()["code"])
                except:
                    print("Failed to save location", response)
 
    def get_team(self, team_id):
        url = "{}/teams/{}".format(
            self.service_url, team_id
        )
        response = self.requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        resp_json = response.json()

        return resp_json
    def get_team_by_code(self, team_code):
        url = "{}/teams/code/{}".format(
            self.service_url, team_code
        )
        response = self.requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        resp_json = response.json()

        return resp_json
    
    def create_team(self, team):
        self.try_sleep()

        url = "{}/teams".format(self.service_url)
 
        response = self.requests.post(
            url,
            json=team,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
            # verify=self.verify_ssl,
        )
        # Convert JSON to dict and print
        try:
            # print("updated team: ", response.json() )

            return response.json()
        except:
            print("Response: ", response.content)
            print("Failed to create team by param: ", team)
            return response.content


    def update_team(self, team):
        self.try_sleep()

        url = "{}/teams/{}".format(self.service_url, team["id"])
 
        response = self.requests.put(
            url,
            json=team,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
            # verify=self.verify_ssl,
        )
        # Convert JSON to dict and print
        try:
            # print("updated team: ", response.json() )

            return response.json()
        except:
            print("Response: ", response.content)
            print("Failed to update team by param: ", team)
            return response.content



    def set_horizon_start_minutes(self, team_id, start_datetime):
        self.try_sleep()
        url = "{}/planner_service/set_horizon_start_minutes/".format(self.service_url)

        response = self.requests.post(
            url,
            json={"team_id": team_id, "start_datetime": start_datetime},
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
            # verify=self.verify_ssl,
        )
        try:
            # print("reset_planning_window: ", response.json())
            if team_id == self.team_id:
                self.refresh_env_start_datetime()
            return response.json()
        except:
            print("Failed reset_planning_window", response)
            return response

    def reset_planning_window(self, team_code):
        self.try_sleep()
        url = "{}/planner_service/reset_planning_window/".format(self.service_url)

        response = self.requests.post(
            url,
            json={"team_code": team_code},
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
            # verify=self.verify_ssl,
        )
        try:
            print("reset_planning_window: ", response.json())
            if team_code == self.team_code:
                self.refresh_env_start_datetime()
            return response.json()
        except:
            print("Failed reset_planning_window", response)
            return response

    def insert_all_teams(self, obj_list):
        url = "{}/teams/".format(self.service_url)

        for myobj in obj_list:
            # print(myobj)
            response = self.requests.post(
                url,
                json=myobj,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer {}".format(self.access_token),
                },
                verify=False,
            )

            try:
                # Convert JSON to dict and print
                print("Saved team: ", response.json()["code"])
            except:
                print("Failed to save team: ", response.content)

    def get_all_teams(self, ):
        url = "{}/teams/?q=&page=1&itemsPerPage=-1".format(
            self.service_url
        )
        response = self.requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        resp_json = response.json()

        return resp_json

    def run_batch_optimizer(self, param):
        url = "{}/planner_service/run_batch_optimizer/".format(self.service_url)

        response = self.requests.post(
            url,
            json=param,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
            # verify=self.verify_ssl,
        )
        try:
            # print("run_batch_optimizer done: ", response.json())
            return response.json()
        except:
            print("Failed run_batch_optimizer", response.content)
            return response.content

    def get_all_jobs(self,items_per_page=500):
        url = "{}/jobs/?q=&page=1&itemsPerPage={}&sortBy[]=scheduled_start_datetime&descending[]=false".format(
            self.service_url,items_per_page
        )
        response = self.requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        resp_json = response.json()

        return resp_json

    def get_all_location_groups(self,items_per_page=500):
        url = "{}/location_group/?q=&page=1&itemsPerPage={}".format(
            self.service_url,items_per_page
        )
        response = self.requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        resp_json = response.json()

        return resp_json    

    def delete_location_group(self,code=None):
        # _by_requested_primary_worker_code
        if not code:
            return 
        url = f"{self.service_url}/location_group/{code}"
        response = self.requests.delete(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        return response.text

    def delete_location_group_by_worker(self,requested_primary_worker_code=""):
        # _by_requested_primary_worker_code
        if not requested_primary_worker_code:
            return 
        url = f"{self.service_url}/location_group/delete_by_requested_primary_worker_code/{requested_primary_worker_code}"
        response = self.requests.delete(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        return response.text


    
    def get_all_workers(self,worker_code="",itemsPerPage=20):
        url = "{}/workers/?q={}&page=1&itemsPerPage={}&sortBy[]=code&descending[]=true".format(
            self.service_url,worker_code,itemsPerPage
        )
        response = self.requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        resp_json = response.json()

        return resp_json
    def get_all_orders(self,order_code="",itemsPerPage=20):
        
        url = "{}/orders/?q={}&page=1&itemsPerPage={}&sortBy[]=code&descending[]=true".format(
            self.service_url,order_code,itemsPerPage
        )
        response = self.requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        resp_json = response.json()

        return resp_json
    def get_planner_env_config(self,team_id):
        url = f"{self.service_url}/planner_service/get_planner_env_config/?team_id={team_id}" 
        response = self.requests.get(
            url,
            headers={
                # "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        resp_json = response.json()["result"]

        return resp_json
 
    def delete_all_orders(self):
        url = "{}/kpdata/jobs/".format(
            self.service_url
        )  # http://localhost:5000/api/v1/workorder/1"
        response = self.requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        resp_json = response.json()
        # Convert JSON to dict and print
        # print(resp_json)
        if len(resp_json) < 1:
            print("it is already empty!")
            return

        for worker in resp_json:
            print("deleting order: ", worker)
            url = "{}/kpdata/jobs/".format(self.service_url) + str(worker["job_code"]) + ""
            print(url)
            response = self.requests.delete(
                url, headers={"Authorization": "Bearer {}".format(self.access_token)}
            )
            print(response.text)
    def delete_orders(self,order_code):
        url = f"{self.service_url}/orders/{order_code}"
        response = self.requests.delete(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        return response.text
    
    
    def delete_job_and_job_event(self,job_code):
        url = f"{self.service_url}/jobs/delete_job_and_job_event/{job_code}"
        response = self.requests.delete(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        return response.json()

    def delete_worker(self,worker_code):
        url = f"{self.service_url}/workers/{worker_code}"
        response = self.requests.delete(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        return response.text


    def delete_locations(self,location_code):
        url = f"{self.service_url}/locations/{location_code}"
        response = self.requests.delete(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )
        return response.text

 #     # else:
    #     response = requests(
    #         url ,json=data,
    #         headers=headers,
    #         # verify=self.verify_ssl,
    #         )


    def update_job_life_cycle(self,param):
        self.try_sleep()
        url = f"{self.service_url}/jobs/update_job_life_cycle"
        response = self.requests.post(
            url,
            json=param,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
            # verify=self.verify_ssl,
        )
        try:
            return response.json()
        except:
            print("Failed update_job_life_cycle", response.content)
            return response.content

        return response.text


    def get_user(self, user_id):
        self.try_sleep()
        url = f"{self.service_url}/user/{user_id}"
        response = self.requests.get(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
            # verify=self.verify_ssl
        )
        resp_json = response.json()
        
        return resp_json
    
    def update_user(self, user):
        self.try_sleep()
        url = "{}/user/{}".format(self.service_url, user["id"])

        response = self.requests.put(
            url,
            json=user,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer {}".format(self.access_token),
            },
        )

        try:
            # Convert JSON to dict and print
            print("updated user: ", response.json()["email"])
        except:
            print("Failed to updated worker: ", response)
        return response.json()

