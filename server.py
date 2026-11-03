"""AI OS: local control plane for registering agents and safely coordinating work."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import json, os, secrets, threading, uuid

STORE = {"objectives": {}, "tasks": {}, "agents": {}, "audit": []}
LOCK = threading.Lock()
TOKEN = os.getenv("AIOS_API_TOKEN", "")
MAX_BUDGET = float(os.getenv("AIOS_MAX_BUDGET_USD", "5.00"))
CAPABILITIES = [
 {"id":"research", "name":"Research", "description":"Collect sources and return a concise, cited brief.", "permission":"read-only"},
 {"id":"code-review", "name":"Code review", "description":"Inspect a proposed change and report risks and test gaps.", "permission":"read-only"},
 {"id":"content", "name":"Content drafting", "description":"Create drafts for a human to review.", "permission":"draft-only"},
 {"id":"workflow", "name":"Workflow planning", "description":"Break an objective into proposed, reviewable tasks.", "permission":"approval-required"},
]

def audit(action, obj_id): STORE["audit"].append({"action":action,"id":obj_id})

class Handler(BaseHTTPRequestHandler):
 def reply(self, status, data):
  raw=json.dumps(data).encode(); self.send_response(status); self.send_header("Content-Type","application/json")
  self.send_header("Content-Length",str(len(raw))); self.send_header("Access-Control-Allow-Origin","*"); self.end_headers(); self.wfile.write(raw)
 def do_OPTIONS(self):
  self.send_response(204); self.send_header("Access-Control-Allow-Origin","*"); self.send_header("Access-Control-Allow-Headers","Authorization,Content-Type")
  self.send_header("Access-Control-Allow-Methods","GET,POST,PATCH,OPTIONS"); self.end_headers()
 def authorized(self): return not TOKEN or secrets.compare_digest(self.headers.get("Authorization",""),"Bearer "+TOKEN)
 def body(self):
  try: return json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))))
  except Exception: return None
 def do_GET(self):
  path=urlparse(self.path).path
  if path=="/api/v1/health": return self.reply(200,{"status":"ok","version":"0.2.0","auth_required":bool(TOKEN)})
  if not self.authorized(): return self.reply(401,{"error":"unauthorized"})
  static={"/":"index.html","/docs/API.md":"docs/API.md","/plugins/README.md":"plugins/README.md"}
  if path in static:
   filename=static[path]
   try:
    with open(os.path.join(os.path.dirname(__file__),filename),"rb") as f: raw=f.read()
    self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8" if filename.endswith(".html") else "text/plain; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw); return
   except OSError: return self.reply(404,{"error":"not found"})
  with LOCK:
   routes={"/api/v1/objectives":list(STORE["objectives"].values()),"/api/v1/tasks":list(STORE["tasks"].values()),"/api/v1/agents":list(STORE["agents"].values()),"/api/v1/capabilities":CAPABILITIES,"/api/v1/audit":STORE["audit"]}
   if path in routes: return self.reply(200,routes[path])
  return self.reply(404,{"error":"not found"})
 def do_POST(self):
  if not self.authorized(): return self.reply(401,{"error":"unauthorized"})
  body=self.body()
  if body is None: return self.reply(400,{"error":"invalid JSON"})
  path=urlparse(self.path).path
  if path=="/api/v1/agents":
   name=str(body.get("name","")).strip(); kind=str(body.get("kind","custom")).strip()
   if not name or len(name)>100: return self.reply(422,{"error":"name required (1-100 characters)"})
   item={"id":str(uuid.uuid4()),"name":name,"kind":kind[:40],"description":str(body.get("description",""))[:500],"capabilities":body.get("capabilities",[]),"status":"registered"}
   with LOCK: STORE["agents"][item["id"]]=item; audit("agent.registered",item["id"])
   return self.reply(201,item)
  if path=="/api/v1/objectives":
   title=str(body.get("title","")).strip(); budget=body.get("budget_usd",0)
   if not title or len(title)>240: return self.reply(422,{"error":"title required (1-240 characters)"})
   if not isinstance(budget,(float,int)) or budget<0 or budget>MAX_BUDGET: return self.reply(422,{"error":f"budget must be between 0 and {MAX_BUDGET:.2f} USD"})
   item={"id":str(uuid.uuid4()),"title":title,"description":str(body.get("description",""))[:4000],"budget_usd":float(budget),"status":"proposed","approval_required":True}
   with LOCK: STORE["objectives"][item["id"]]=item; audit("objective.proposed",item["id"])
   return self.reply(201,item)
  if path=="/api/v1/tasks":
   oid=body.get("objective_id"); title=str(body.get("title","")).strip()
   if not title: return self.reply(422,{"error":"title required"})
   with LOCK:
    if oid not in STORE["objectives"]: return self.reply(404,{"error":"objective not found"})
    item={"id":str(uuid.uuid4()),"objective_id":oid,"title":title,"status":"queued","result":None}
    STORE["tasks"][item["id"]]=item; audit("task.queued",item["id"])
   return self.reply(201,item)
  return self.reply(404,{"error":"not found"})
 def do_PATCH(self):
  if not self.authorized(): return self.reply(401,{"error":"unauthorized"})
  path=urlparse(self.path).path; parts=path.strip("/").split("/"); body=self.body()
  if body is None: return self.reply(400,{"error":"invalid JSON"})
  if len(parts)!=4 or parts[:2]!=["api","v1"]: return self.reply(404,{"error":"not found"})
  collection,item_id=parts[2],parts[3]
  with LOCK:
   if collection=="tasks" and item_id in STORE["tasks"]:
    status=body.get("status"); result=str(body.get("result",""))[:4000]
    if status not in ("running","completed","failed"): return self.reply(422,{"error":"status must be running, completed, or failed"})
    task=STORE["tasks"][item_id]; task.update(status=status,result=result); audit("task."+status,item_id); return self.reply(200,task)
   if collection=="agents" and item_id in STORE["agents"]:
    STORE["agents"][item_id]["status"]="active" if body.get("status")=="active" else "registered"; return self.reply(200,STORE["agents"][item_id])
  return self.reply(404,{"error":"item not found"})
 def log_message(self,*_): pass

if __name__=="__main__":
 port=int(os.getenv("PORT","8000")); print(f"AI OS listening on http://127.0.0.1:{port}"); ThreadingHTTPServer(("0.0.0.0",port),Handler).serve_forever()
