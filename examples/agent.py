"""Minimal polling worker example. Supply a custom process_task for your model/tool stack."""
import json, os, time, urllib.request, urllib.error
BASE=os.getenv("AIOS_URL","http://localhost:8000/api/v1").rstrip("/")
TOKEN=os.environ["AIOS_AGENT_TOKEN"]
AGENT_ID=os.environ["AIOS_AGENT_ID"]

def api(path, method="GET", body=None):
    data=json.dumps(body).encode() if body is not None else None
    request=urllib.request.Request(BASE+path,data=data,method=method,headers={"Authorization":"Bearer "+TOKEN,"Content-Type":"application/json","X-AI-OS-Role":"agent" if not TOKEN else ""})
    with urllib.request.urlopen(request,timeout=30) as response: return json.load(response)

def process_task(task):
    """Replace with your model or workflow call; return result text and measured USD spend."""
    raise NotImplementedError("Connect your agent implementation in process_task(task)")

def run():
    while True:
        try:
            for task in api("tasks"):
                if task["status"]!="queued": continue
                claimed=api("tasks/"+task["id"]+"/claim","POST",{"agent_id":AGENT_ID})
                try:
                    result,spent=process_task(claimed)
                    api("tasks/"+task["id"],"PATCH",{"agent_id":AGENT_ID,"status":"completed","result":result,"spent_usd":spent})
                except Exception as error:
                    api("tasks/"+task["id"],"PATCH",{"agent_id":AGENT_ID,"status":"failed","result":str(error)[:1000],"spent_usd":0})
        except (urllib.error.URLError,TimeoutError): pass
        time.sleep(3)

if __name__=="__main__": run()
