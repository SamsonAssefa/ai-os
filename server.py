"""AI OS MVP: approval-gated, budget-aware agent task coordinator."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import json, os, secrets, sqlite3, threading, uuid

ROOT=os.path.dirname(__file__); DB=os.getenv("AIOS_DB_PATH",os.path.join(ROOT,"aios.sqlite3")); PUBLIC_URL=os.getenv("AIOS_PUBLIC_URL","").rstrip("/")
ADMIN_TOKEN=os.getenv("AIOS_ADMIN_TOKEN",""); AGENT_TOKEN=os.getenv("AIOS_AGENT_TOKEN","")
MAX_BUDGET=float(os.getenv("AIOS_MAX_BUDGET_USD","5.00")); LOCK=threading.RLock()
WORKFLOW_TEMPLATES=[
 {"id":"research-brief","name":"Research brief","description":"Collect reliable sources and synthesize key findings.","title":"Prepare a research brief","objective":"Produce a cited summary with key findings, open questions, and source links.","budget_usd":2.0,"suggested_tasks":["Gather authoritative sources","Synthesize findings and cite sources"]},
 {"id":"code-review","name":"Code review","description":"Review a proposed change and return prioritized findings.","title":"Review a code change","objective":"Inspect the change for correctness, security, and missing tests. Return findings with file and line references.","budget_usd":1.0,"suggested_tasks":["Inspect the change and identify risks","Check test coverage and report actionable findings"]},
 {"id":"content-draft","name":"Content draft","description":"Create a reviewable first draft from a brief.","title":"Draft content for review","objective":"Write a clearly structured first draft that follows the supplied brief and flags facts that need verification.","budget_usd":1.0,"suggested_tasks":["Draft the requested content","Review the draft against the brief"]},
]
CAPABILITIES=[
 {"id":"research","name":"Research","description":"Collect sources and return a concise, cited brief.","permission":"read-only"},
 {"id":"code-review","name":"Code review","description":"Inspect a proposed change and report risks and test gaps.","permission":"read-only"},
 {"id":"content","name":"Content drafting","description":"Create drafts for a human to review.","permission":"draft-only"},
 {"id":"workflow","name":"Workflow planning","description":"Break an objective into proposed, reviewable tasks.","permission":"approval-required"},]

def connect():
 db=sqlite3.connect(DB,timeout=10); db.row_factory=sqlite3.Row; db.execute("PRAGMA journal_mode=WAL")
 db.executescript("""
 CREATE TABLE IF NOT EXISTS objectives(id TEXT PRIMARY KEY,title TEXT NOT NULL,description TEXT NOT NULL,budget REAL NOT NULL,status TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,approved_at TEXT);
 CREATE TABLE IF NOT EXISTS agents(id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT,description TEXT,capabilities TEXT,status TEXT DEFAULT 'registered');
 CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,objective_id TEXT NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL,claimed_by TEXT,assigned_agent_id TEXT,result TEXT,spent REAL DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(objective_id) REFERENCES objectives(id));
 CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,action TEXT NOT NULL,entity_id TEXT NOT NULL,actor TEXT NOT NULL,detail TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
 """);
 columns={r[1] for r in db.execute("PRAGMA table_info(tasks)")}
 if "assigned_agent_id" not in columns: db.execute("ALTER TABLE tasks ADD COLUMN assigned_agent_id TEXT")
 return db

def rowdict(row): return dict(row) if row else None
def audit(db,action,entity,actor,detail=""): db.execute("INSERT INTO audit(action,entity_id,actor,detail) VALUES(?,?,?,?)",(action,entity,actor,detail))
def role_for(headers):
 token=headers.get("Authorization","")
 if not ADMIN_TOKEN and not AGENT_TOKEN: return "agent" if headers.get("X-AI-OS-Role")=="agent" else "admin"  # local development only
 if ADMIN_TOKEN and secrets.compare_digest(token,"Bearer "+ADMIN_TOKEN): return "admin"
 if AGENT_TOKEN and secrets.compare_digest(token,"Bearer "+AGENT_TOKEN): return "agent"
 return ""

class Handler(BaseHTTPRequestHandler):
 def reply(self,status,data):
  raw=json.dumps(data).encode(); self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(raw))); self.send_header("Access-Control-Allow-Origin","*"); self.end_headers(); self.wfile.write(raw)
 def reply_text(self,status,body,content_type):
  raw=body.encode(); self.send_response(status); self.send_header("Content-Type",content_type); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
 def do_OPTIONS(self):
  self.send_response(204); self.send_header("Access-Control-Allow-Origin","*"); self.send_header("Access-Control-Allow-Headers","Authorization,Content-Type"); self.send_header("Access-Control-Allow-Methods","GET,POST,PATCH,OPTIONS"); self.end_headers()
 def body(self):
  try: return json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))))
  except Exception: return None
 def do_GET(self):
  path=urlparse(self.path).path
  if path=="/api/v1/health": return self.reply(200,{"status":"ok","version":"0.3.0","auth_required":bool(ADMIN_TOKEN or AGENT_TOKEN)})
  if path in ("/robots.txt","/llms.txt","/sitemap.xml","/.well-known/ai-plugin.json"):
   if path=="/robots.txt":
    body="User-agent: *\nAllow: /\nDisallow: /api/\n"
    if PUBLIC_URL: body+=f"Sitemap: {PUBLIC_URL}/sitemap.xml\n"
    return self.reply_text(200,body,"text/plain; charset=utf-8")
   if path=="/llms.txt":
    try:
     with open(os.path.join(ROOT,"llms.txt"),encoding="utf-8") as f: return self.reply_text(200,f.read(),"text/plain; charset=utf-8")
    except OSError: return self.reply(404,{"error":"not found"})
   if path=="/sitemap.xml":
    urls=[]
    if PUBLIC_URL:
     urls=[PUBLIC_URL+suffix for suffix in ("/","/docs/USER_GUIDE.md","/docs/API.md","/plugins/README.md","/openapi.yaml","/llms.txt")]
    xml='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f"<url><loc>{u}</loc></url>" for u in urls)+'</urlset>'
    return self.reply_text(200,xml,"application/xml; charset=utf-8")
   info={"schema_version":"v1","name_for_human":"AI OS","name_for_model":"ai_os","description_for_human":"Open-source workspace for connecting AI agents and coordinating human-approved tasks.","description_for_model":"Register agents, propose objectives, queue approved tasks, and report task results through the AI OS API. Read the user guide and API reference before integrating.","api":{"type":"openapi","url":(PUBLIC_URL+"/openapi.yaml") if PUBLIC_URL else "https://raw.githubusercontent.com/SamsonAssefa/ai-os/main/openapi.yaml","is_user_authenticated":True},"logo_url":"","contact_email":"","legal_info_url":"https://github.com/SamsonAssefa/ai-os/blob/main/LICENSE"}
   return self.reply(200,info)
  static={"/":"index.html","/docs/API.md":"docs/API.md","/plugins/README.md":"plugins/README.md","/docs/USER_GUIDE.md":"docs/USER_GUIDE.md","/docs/AI_DISCOVERY.md":"docs/AI_DISCOVERY.md","/llms.txt":"llms.txt","/openapi.yaml":"openapi.yaml"}
  if path in static:
   try:
    with open(os.path.join(ROOT,static[path]),"rb") as f: raw=f.read()
    self.send_response(200); self.send_header("Content-Type","text/html; charset=utf-8" if path=="/" else "text/plain; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw); return
   except OSError: return self.reply(404,{"error":"not found"})
  role=role_for(self.headers)
  if not role: return self.reply(401,{"error":"unauthorized"})
  if path=="/api/v1/capabilities": return self.reply(200,CAPABILITIES)
  if path=="/api/v1/workflow-templates": return self.reply(200,WORKFLOW_TEMPLATES)
  with LOCK,connect() as db:
   if path=="/api/v1/objectives": return self.reply(200,[dict(x) for x in db.execute("SELECT * FROM objectives ORDER BY created_at DESC")])
   if path=="/api/v1/agents":
    agents=[dict(x) for x in db.execute("SELECT * FROM agents ORDER BY name")]
    for a in agents: a["capabilities"]=json.loads(a["capabilities"])
    return self.reply(200,agents)
   if path=="/api/v1/tasks":
    if role=="admin": rows=db.execute("SELECT * FROM tasks ORDER BY created_at DESC")
    else:
     agent_id=parse_qs(urlparse(self.path).query).get("agent_id",[""])[0]
     rows=db.execute("SELECT t.* FROM tasks t JOIN objectives o ON o.id=t.objective_id WHERE o.status='approved' AND t.status='queued' AND (t.assigned_agent_id IS NULL OR t.assigned_agent_id=?) ORDER BY t.created_at",(agent_id,))
    return self.reply(200,[dict(x) for x in rows])
   if path=="/api/v1/audit" and role=="admin": return self.reply(200,[dict(x) for x in db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 200")])
  return self.reply(403,{"error":"admin permission required"})
 def do_POST(self):
  role=role_for(self.headers)
  if not role: return self.reply(401,{"error":"unauthorized"})
  body=self.body()
  if body is None: return self.reply(400,{"error":"invalid JSON"})
  path=urlparse(self.path).path
  if path=="/api/v1/agents":
   name=str(body.get("name","")).strip()
   if not name or len(name)>100: return self.reply(422,{"error":"name required (1-100 characters)"})
   item={"id":str(uuid.uuid4()),"name":name,"kind":str(body.get("kind","custom"))[:40],"description":str(body.get("description",""))[:500],"capabilities":body.get("capabilities",[]),"status":"registered"}
   with LOCK,connect() as db: db.execute("INSERT INTO agents(id,name,kind,description,capabilities) VALUES(?,?,?,?,?)",(item["id"],item["name"],item["kind"],item["description"],json.dumps(item["capabilities"]))); audit(db,"agent.registered",item["id"],role)
   return self.reply(201,item)
  if path=="/api/v1/objectives":
   if role!="admin": return self.reply(403,{"error":"only a human admin can propose objectives"})
   title=str(body.get("title","")).strip(); budget=body.get("budget_usd",0)
   if not title or len(title)>240: return self.reply(422,{"error":"title required (1-240 characters)"})
   if not isinstance(budget,(int,float)) or budget<0 or budget>MAX_BUDGET: return self.reply(422,{"error":f"budget must be between 0 and {MAX_BUDGET:.2f} USD"})
   item={"id":str(uuid.uuid4()),"title":title,"description":str(body.get("description",""))[:4000],"budget":float(budget),"status":"proposed","approval_required":True}
   with LOCK,connect() as db: db.execute("INSERT INTO objectives(id,title,description,budget,status) VALUES(?,?,?,?,?)",(item["id"],item["title"],item["description"],item["budget"],item["status"])); audit(db,"objective.proposed",item["id"],role)
   return self.reply(201,item)
  if path=="/api/v1/tasks":
   if role!="admin": return self.reply(403,{"error":"only a human admin can create tasks"})
   title=str(body.get("title","")).strip(); oid=body.get("objective_id"); assigned=body.get("assigned_agent_id")
   if not title: return self.reply(422,{"error":"title required"})
   with LOCK,connect() as db:
    obj=db.execute("SELECT status FROM objectives WHERE id=?",(oid,)).fetchone()
    if not obj: return self.reply(404,{"error":"objective not found"})
    if obj["status"]!="approved": return self.reply(409,{"error":"objective must be human-approved before tasks can be queued"})
    if assigned and not db.execute("SELECT 1 FROM agents WHERE id=?",(assigned,)).fetchone(): return self.reply(404,{"error":"assigned agent not found"})
    item={"id":str(uuid.uuid4()),"objective_id":oid,"title":title,"status":"queued","spent":0,"assigned_agent_id":assigned}
    db.execute("INSERT INTO tasks(id,objective_id,title,status,assigned_agent_id) VALUES(?,?,?,'queued',?)",(item["id"],oid,title,assigned)); audit(db,"task.queued",item["id"],role,json.dumps({"assigned_agent_id":assigned}))
   return self.reply(201,item)
  parts=path.strip("/").split("/")
  if len(parts)==5 and parts[:3]==["api","v1","tasks"] and parts[4]=="claim":
   if role!="agent": return self.reply(403,{"error":"agent credential required"})
   tid=parts[3]; agent_id=str(body.get("agent_id",""))
   with LOCK,connect() as db:
    agent=db.execute("SELECT id FROM agents WHERE id=?",(agent_id,)).fetchone(); task=db.execute("SELECT t.*,o.status AS objective_status,o.budget AS budget FROM tasks t JOIN objectives o ON o.id=t.objective_id WHERE t.id=?",(tid,)).fetchone()
    if not agent:return self.reply(404,{"error":"agent not found"})
    if not task:return self.reply(404,{"error":"task not found"})
    if task["objective_status"]!="approved":return self.reply(409,{"error":"objective is not approved"})
    if task["status"]!="queued":return self.reply(409,{"error":"task is not available"})
    if task["assigned_agent_id"] and task["assigned_agent_id"]!=agent_id:return self.reply(403,{"error":"task is assigned to another agent"})
    db.execute("UPDATE tasks SET status='running',claimed_by=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(agent_id,tid)); audit(db,"task.claimed",tid,agent_id)
    task=dict(task); task.update(status="running",claimed_by=agent_id); return self.reply(200,task)
  return self.reply(404,{"error":"not found"})
 def do_PATCH(self):
  role=role_for(self.headers)
  if not role:return self.reply(401,{"error":"unauthorized"})
  path=urlparse(self.path).path; parts=path.strip("/").split("/"); body=self.body()
  if body is None:return self.reply(400,{"error":"invalid JSON"})
  if len(parts)==5 and parts[:3]==["api","v1","objectives"] and parts[4]=="approve":
   if role!="admin":return self.reply(403,{"error":"human admin approval required"})
   oid=parts[3]
   with LOCK,connect() as db:
    obj=db.execute("SELECT * FROM objectives WHERE id=?",(oid,)).fetchone()
    if not obj:return self.reply(404,{"error":"objective not found"})
    if obj["status"]!="proposed":return self.reply(409,{"error":"objective is not awaiting approval"})
    db.execute("UPDATE objectives SET status='approved',approved_at=CURRENT_TIMESTAMP WHERE id=?",(oid,)); audit(db,"objective.approved",oid,"human-admin")
    return self.reply(200,{**dict(obj),"status":"approved"})
  if len(parts)==4 and parts[:3]==["api","v1","tasks"]:
   if role!="agent":return self.reply(403,{"error":"agent credential required to report results"})
   tid=parts[3]; status=body.get("status"); result=str(body.get("result",""))[:4000]; spent=body.get("spent_usd",0); agent_id=body.get("agent_id")
   if status not in ("completed","failed"):return self.reply(422,{"error":"status must be completed or failed"})
   if not isinstance(spent,(int,float)) or spent<0:return self.reply(422,{"error":"spent_usd must be a non-negative number"})
   with LOCK,connect() as db:
    row=db.execute("SELECT t.*,o.budget,o.status AS objective_status,(SELECT COALESCE(SUM(spent),0) FROM tasks WHERE objective_id=o.id) AS spent_total FROM tasks t JOIN objectives o ON o.id=t.objective_id WHERE t.id=?",(tid,)).fetchone()
    if not row:return self.reply(404,{"error":"task not found"})
    if row["claimed_by"]!=agent_id or not agent_id:return self.reply(403,{"error":"task is claimed by a different agent"})
    if row["objective_status"]!="approved":return self.reply(409,{"error":"objective is not approved"})
    if row["status"]!="running":return self.reply(409,{"error":"task is not running"})
    if row["spent_total"]+spent>row["budget"]:return self.reply(422,{"error":"reported spend would exceed objective budget"})
    db.execute("UPDATE tasks SET status=?,result=?,spent=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(status,result,float(spent),tid)); audit(db,"task."+status,tid,agent_id,json.dumps({"spent_usd":spent}))
    return self.reply(200,{"id":tid,"status":status,"result":result,"spent_usd":spent})
  return self.reply(404,{"error":"not found"})
 def log_message(self,*_):pass
if __name__=="__main__":
 port=int(os.getenv("PORT","8000")); print(f"AI OS listening on http://127.0.0.1:{port}"); ThreadingHTTPServer(("0.0.0.0",port),Handler).serve_forever()
