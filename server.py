"""AI OS MVP: approval-gated, budget-aware agent task coordinator."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import datetime, hashlib, json, os, re, secrets, shutil, sqlite3, threading, uuid
from sandbox_runner import execute as run_sandbox, SandboxError

ROOT=os.path.dirname(__file__); DB=os.getenv("AIOS_DB_PATH",os.path.join(ROOT,"aios.sqlite3")); PUBLIC_URL=os.getenv("AIOS_PUBLIC_URL","").rstrip("/")
ADMIN_TOKEN=os.getenv("AIOS_ADMIN_TOKEN",""); AGENT_TOKEN=os.getenv("AIOS_AGENT_TOKEN","")
ALLOWED_ORIGINS=set(x.strip() for x in os.getenv("AIOS_CORS_ORIGINS","http://localhost:8000,http://127.0.0.1:8000").split(",") if x.strip())
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
 CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY,name TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS api_keys(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL,name TEXT NOT NULL,token_hash TEXT NOT NULL UNIQUE,token_prefix TEXT NOT NULL,role TEXT NOT NULL,agent_id TEXT,scopes TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,revoked_at TEXT);
 CREATE TABLE IF NOT EXISTS objectives(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL DEFAULT 'local',title TEXT NOT NULL,description TEXT NOT NULL,budget REAL NOT NULL,status TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,approved_at TEXT);
 CREATE TABLE IF NOT EXISTS agents(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL DEFAULT 'local',name TEXT NOT NULL,kind TEXT,description TEXT,capabilities TEXT,status TEXT DEFAULT 'registered');
 CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL DEFAULT 'local',objective_id TEXT NOT NULL,title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',status TEXT NOT NULL,claimed_by TEXT,assigned_agent_id TEXT,result TEXT,spent REAL DEFAULT 0,reserved REAL DEFAULT 0,attempts INTEGER DEFAULT 0,max_attempts INTEGER DEFAULT 3,deadline_at TEXT,depends_on TEXT DEFAULT '[]',created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(objective_id) REFERENCES objectives(id));
 CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id TEXT NOT NULL DEFAULT 'local',action TEXT NOT NULL,entity_id TEXT NOT NULL,actor TEXT NOT NULL,detail TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS task_events(id INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id TEXT NOT NULL,task_id TEXT NOT NULL,event TEXT NOT NULL,payload TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS plugins(id TEXT PRIMARY KEY,workspace_id TEXT NOT NULL DEFAULT 'local',name TEXT NOT NULL,version TEXT NOT NULL,api_version TEXT NOT NULL,requested_permissions TEXT NOT NULL,container_image TEXT,description TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending_review',created_at TEXT DEFAULT CURRENT_TIMESTAMP,reviewed_at TEXT);
 """);
 for table,definitions in {"objectives":{"workspace_id":"TEXT NOT NULL DEFAULT 'local'"},"agents":{"workspace_id":"TEXT NOT NULL DEFAULT 'local'"},"tasks":{"workspace_id":"TEXT NOT NULL DEFAULT 'local'","description":"TEXT NOT NULL DEFAULT ''","assigned_agent_id":"TEXT","reserved":"REAL DEFAULT 0","reservation_target":"REAL DEFAULT 0","attempts":"INTEGER DEFAULT 0","max_attempts":"INTEGER DEFAULT 3","deadline_at":"TEXT","depends_on":"TEXT DEFAULT '[]'"},"audit":{"workspace_id":"TEXT NOT NULL DEFAULT 'local'"},"plugins":{"workspace_id":"TEXT NOT NULL DEFAULT 'local'"}}.items():
  columns={r[1] for r in db.execute(f"PRAGMA table_info({table})")}
  for name,definition in definitions.items():
   if name not in columns: db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
 db.execute("INSERT OR IGNORE INTO workspaces(id,name) VALUES('local','Local workspace')")
 return db

def rowdict(row): return dict(row) if row else None
def audit(db,action,entity,actor,detail="",workspace_id="local"): db.execute("INSERT INTO audit(workspace_id,action,entity_id,actor,detail) VALUES(?,?,?,?,?)",(workspace_id,action,entity,actor,detail))
def parse_datetime(value):
 parsed=datetime.datetime.fromisoformat(value.replace("Z","+00:00"))
 return parsed.replace(tzinfo=datetime.timezone.utc) if parsed.tzinfo is None else parsed.astimezone(datetime.timezone.utc)
def principal_for(headers):
 token=headers.get("Authorization","")
 if ADMIN_TOKEN and secrets.compare_digest(token,"Bearer "+ADMIN_TOKEN): return {"role":"admin","workspace_id":"local","agent_id":None,"scopes":["*"]}
 if AGENT_TOKEN and secrets.compare_digest(token,"Bearer "+AGENT_TOKEN): return {"role":"agent","workspace_id":"local","agent_id":None,"scopes":["tasks:read","tasks:claim","tasks:report"]}
 if token.startswith("Bearer "):
  raw=token[7:]
  with LOCK,connect() as db:
   row=db.execute("SELECT * FROM api_keys WHERE token_hash=? AND revoked_at IS NULL",(hashlib.sha256(raw.encode()).hexdigest(),)).fetchone()
   if row: return {"role":row["role"],"workspace_id":row["workspace_id"],"agent_id":row["agent_id"],"scopes":json.loads(row["scopes"]),"key_id":row["id"]}
 if not ADMIN_TOKEN and not AGENT_TOKEN:
  role="agent" if headers.get("X-AI-OS-Role")=="agent" else "admin"  # local development only
  return {"role":role,"workspace_id":"local","agent_id":None,"scopes":["*"]}
 return None

class Handler(BaseHTTPRequestHandler):
 def reply(self,status,data):
  raw=json.dumps(data).encode(); self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.send_header("X-Content-Type-Options","nosniff")
  origin=self.headers.get("Origin","")
  if origin in ALLOWED_ORIGINS:self.send_header("Access-Control-Allow-Origin",origin); self.send_header("Vary","Origin")
  self.end_headers(); self.wfile.write(raw)
 def reply_text(self,status,body,content_type):
  raw=body.encode(); self.send_response(status); self.send_header("Content-Type",content_type); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
 def do_OPTIONS(self):
  self.send_response(204); origin=self.headers.get("Origin","")
  if origin in ALLOWED_ORIGINS:self.send_header("Access-Control-Allow-Origin",origin); self.send_header("Vary","Origin")
  self.send_header("Access-Control-Allow-Headers","Authorization,Content-Type"); self.send_header("Access-Control-Allow-Methods","GET,POST,PATCH,DELETE,OPTIONS"); self.end_headers()
 def body(self):
  try: return json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))))
  except Exception: return None
 def mint_key(self,db,workspace_id,name,role,agent_id=None):
  raw="aios_"+secrets.token_urlsafe(32); key_id=str(uuid.uuid4()); scopes={"owner":["*"],"admin":["*"],"member":["objectives:read","objectives:propose","tasks:read","tasks:queue"],"viewer":["objectives:read","tasks:read","audit:read"],"agent":["objectives:read","objectives:propose","tasks:read","tasks:claim","tasks:report"]}[role]
  db.execute("INSERT INTO api_keys(id,workspace_id,name,token_hash,token_prefix,role,agent_id,scopes) VALUES(?,?,?,?,?,?,?,?)",(key_id,workspace_id,name,hashlib.sha256(raw.encode()).hexdigest(),raw[:12],role,agent_id,json.dumps(scopes)))
  return {"id":key_id,"token":raw,"role":role,"workspace_id":workspace_id,"agent_id":agent_id,"scopes":scopes}
 def do_GET(self):
  path=urlparse(self.path).path
  if path=="/api/v1/health": return self.reply(200,{"status":"ok","version":"0.4.0","auth_required":bool(ADMIN_TOKEN or AGENT_TOKEN)})
  if path in ("/.well-known/agent-card.json","/agent-card.json"):
   endpoint=(PUBLIC_URL+"/a2a") if PUBLIC_URL else "http://localhost:8000/a2a"
   return self.reply(200,{"name":"AI OS","description":"Human-supervised workspace for interoperable AI agents.","url":endpoint,"version":"0.4.0","capabilities":{"streaming":False,"pushNotifications":False,"stateTransitionHistory":True},"skills":[{"id":"coordinate-approved-work","name":"Coordinate approved work","description":"Discover workflows and claim tasks only after human approval.","tags":["tasks","coordination","human-approval"]}],"securitySchemes":{"bearerAuth":{"type":"http","scheme":"bearer"}},"security":[{"bearerAuth":[]}]})
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
  principal=principal_for(self.headers)
  if not principal: return self.reply(401,{"error":"unauthorized"})
  role=principal["role"]; workspace_id=principal["workspace_id"]; platform_admin=role=="admin" and not principal.get("key_id")
  if path=="/api/v1/capabilities": return self.reply(200,CAPABILITIES)
  if path=="/api/v1/workflow-templates": return self.reply(200,WORKFLOW_TEMPLATES)
  with LOCK,connect() as db:
   if path=="/api/v1/objectives":
    rows=db.execute("SELECT * FROM objectives WHERE workspace_id=? ORDER BY created_at DESC",(workspace_id,)) if role!="agent" else db.execute("SELECT DISTINCT o.* FROM objectives o JOIN tasks t ON t.objective_id=o.id AND t.workspace_id=o.workspace_id WHERE o.workspace_id=? AND o.status='approved' AND t.status='queued' AND (t.assigned_agent_id IS NULL OR t.assigned_agent_id=?) ORDER BY o.created_at DESC",(workspace_id,principal["agent_id"] or ""))
    return self.reply(200,[dict(x) for x in rows])
   if path=="/api/v1/agents":
    agents=[dict(x) for x in db.execute("SELECT * FROM agents WHERE workspace_id=? ORDER BY name",(workspace_id,))] if role!="agent" else ([dict(x) for x in db.execute("SELECT * FROM agents WHERE workspace_id=? AND id=?",(workspace_id,principal["agent_id"]))] if principal["agent_id"] else [])
    for a in agents: a["capabilities"]=json.loads(a["capabilities"])
    return self.reply(200,agents)
   if path=="/api/v1/tasks":
    if role in ("admin","owner","member","viewer"): rows=db.execute("SELECT t.*,o.title AS objective_title,o.description AS objective_description FROM tasks t JOIN objectives o ON o.id=t.objective_id AND o.workspace_id=t.workspace_id WHERE t.workspace_id=? ORDER BY t.created_at DESC",(workspace_id,))
    else:
     agent_id=principal["agent_id"] or parse_qs(urlparse(self.path).query).get("agent_id",[""])[0]
     rows=db.execute("SELECT t.*,o.title AS objective_title,o.description AS objective_description FROM tasks t JOIN objectives o ON o.id=t.objective_id AND o.workspace_id=t.workspace_id WHERE t.workspace_id=? AND o.status='approved' AND t.status='queued' AND (t.assigned_agent_id IS NULL OR t.assigned_agent_id=?) AND NOT EXISTS (SELECT 1 FROM json_each(t.depends_on) d LEFT JOIN tasks dep ON dep.id=d.value AND dep.workspace_id=t.workspace_id WHERE dep.status IS NULL OR dep.status!='completed') ORDER BY t.created_at",(workspace_id,agent_id))
    return self.reply(200,[dict(x) for x in rows])
   parts=path.strip("/").split("/")
   if len(parts)==4 and parts[:3]==["api","v1","tasks"]:
    task=db.execute("SELECT * FROM tasks WHERE id=? AND workspace_id=?",(parts[3],workspace_id)).fetchone()
    if not task:return self.reply(404,{"error":"task not found"})
    if role=="agent" and (not principal["agent_id"] or task["claimed_by"]!=principal["agent_id"]): return self.reply(403,{"error":"task must be claimed by this bound agent before it can be read"})
    return self.reply(200,dict(task))
   if len(parts)==5 and parts[:3]==["api","v1","tasks"] and parts[4]=="events" and role in ("admin","owner","agent"):
    if role=="agent" and (not principal["agent_id"] or not db.execute("SELECT 1 FROM tasks WHERE id=? AND workspace_id=? AND claimed_by=?",(parts[3],workspace_id,principal["agent_id"])).fetchone()):return self.reply(404,{"error":"task events not found"})
    return self.reply(200,[dict(x) for x in db.execute("SELECT * FROM task_events WHERE workspace_id=? AND task_id=? ORDER BY id",(workspace_id,parts[3]))])
   if path=="/api/v1/audit" and role in ("admin","owner","viewer"): return self.reply(200,[dict(x) for x in db.execute("SELECT * FROM audit WHERE workspace_id=? ORDER BY id DESC LIMIT 200",(workspace_id,))])
   if path=="/api/v1/metrics" and role in ("admin","owner"):
    return self.reply(200,{"workspace_id":workspace_id,"agents":db.execute("SELECT COUNT(*) FROM agents WHERE workspace_id=?",(workspace_id,)).fetchone()[0],"objectives":db.execute("SELECT COUNT(*) FROM objectives WHERE workspace_id=?",(workspace_id,)).fetchone()[0],"tasks_by_status":{r[0]:r[1] for r in db.execute("SELECT status,COUNT(*) FROM tasks WHERE workspace_id=? GROUP BY status",(workspace_id,))},"spent_usd":db.execute("SELECT COALESCE(SUM(spent),0) FROM tasks WHERE workspace_id=?",(workspace_id,)).fetchone()[0],"reserved_usd":db.execute("SELECT COALESCE(SUM(reserved),0) FROM tasks WHERE workspace_id=?",(workspace_id,)).fetchone()[0]})
   if path=="/api/v1/runner/status" and role in ("admin","owner"):
    return self.reply(200,{"enabled":os.getenv("AIOS_ENABLE_SANDBOX")=="1","docker_available":bool(shutil.which("docker")),"network":"disabled inside plugin containers","image_policy":"sha256 digest required","credentials_mounted":False})
   if path=="/api/v1/workspaces" and role in ("admin","owner"):
    rows=db.execute("SELECT id,name,created_at FROM workspaces ORDER BY created_at") if platform_admin else db.execute("SELECT id,name,created_at FROM workspaces WHERE id=?",(workspace_id,))
    return self.reply(200,[dict(x) for x in rows])
   if path=="/api/v1/backups" and platform_admin:
    backup_dir=os.getenv("AIOS_BACKUP_DIR",os.path.join(ROOT,"backups")); names=[]
    try:
     for name in sorted(os.listdir(backup_dir)):
      if re.fullmatch(r"aios-[0-9]{8}-[0-9]{6}\.sqlite3",name): names.append({"name":name,"size_bytes":os.path.getsize(os.path.join(backup_dir,name))})
    except FileNotFoundError: pass
    return self.reply(200,names)
   if path=="/api/v1/api-keys" and role in ("admin","owner"):
    return self.reply(200,[{k:v for k,v in dict(x).items() if k!="token_hash"} for x in db.execute("SELECT * FROM api_keys WHERE workspace_id=? ORDER BY created_at DESC",(workspace_id,))])
   if path=="/api/v1/plugins":
    rows=db.execute("SELECT * FROM plugins ORDER BY created_at DESC") if platform_admin else db.execute("SELECT * FROM plugins WHERE workspace_id=? OR status='approved' ORDER BY created_at DESC",(workspace_id,)) if role in ("owner","admin") else db.execute("SELECT * FROM plugins WHERE status='approved' ORDER BY name")
    result=[]
    for row in rows:
     item=dict(row); item["requested_permissions"]=json.loads(item["requested_permissions"]); item["can_review"]=platform_admin and item["status"]=="pending_review"; result.append(item)
    return self.reply(200,result)
   if path=="/api/v1/export" and role in ("admin","owner"):
    tables={}
    for table in ("agents","objectives","tasks","audit"):
     tables[table]=[dict(x) for x in db.execute(f"SELECT * FROM {table} WHERE workspace_id=?",(workspace_id,))]
    return self.reply(200,{"format":"ai-os-workspace-export","version":1,"workspace":{"id":workspace_id,"name":db.execute("SELECT name FROM workspaces WHERE id=?",(workspace_id,)).fetchone()[0]},"tables":tables})
  return self.reply(403,{"error":"admin permission required"})
 def do_POST(self):
  principal=principal_for(self.headers)
  if not principal: return self.reply(401,{"error":"unauthorized"})
  role=principal["role"]; workspace_id=principal["workspace_id"]; platform_admin=role=="admin" and not principal.get("key_id")
  body=self.body()
  if body is None: return self.reply(400,{"error":"invalid JSON"})
  path=urlparse(self.path).path
  if path=="/mcp":
   request_id=body.get("id"); method=body.get("method"); params=body.get("params",{})
   def mcp_result(result): return self.reply(200,{"jsonrpc":"2.0","id":request_id,"result":result})
   def mcp_error(code,message): return self.reply(200,{"jsonrpc":"2.0","id":request_id,"error":{"code":code,"message":message}})
   if method=="initialize": return mcp_result({"protocolVersion":"2025-11-25","capabilities":{"tools":{"listChanged":False}},"serverInfo":{"name":"AI OS","version":"0.4.0"}})
   if method=="notifications/initialized": return self.reply(202,{})
   if method=="tools/list":
    return mcp_result({"tools":[{"name":"list_workflow_templates","description":"List safe workflow templates.","inputSchema":{"type":"object","properties":{}}},{"name":"list_tasks","description":"List tasks available in this workspace.","inputSchema":{"type":"object","properties":{}}},{"name":"propose_objective","description":"Create a proposed objective that still requires human approval.","inputSchema":{"type":"object","required":["title"],"properties":{"title":{"type":"string"},"description":{"type":"string"},"budget_usd":{"type":"number"}}}}]})
   if method!="tools/call": return mcp_error(-32601,"Method not found")
   tool=params.get("name"); args=params.get("arguments",{})
   if tool=="list_workflow_templates": return mcp_result({"content":[{"type":"text","text":json.dumps(WORKFLOW_TEMPLATES)}]})
   if tool=="list_tasks":
    with LOCK,connect() as db:
     rows=db.execute("SELECT t.id,t.title,t.description,t.status,t.assigned_agent_id,t.deadline_at,o.title AS objective_title,o.description AS objective_description FROM tasks t JOIN objectives o ON o.id=t.objective_id AND o.workspace_id=t.workspace_id WHERE t.workspace_id=? ORDER BY t.created_at DESC LIMIT 100",(workspace_id,)) if role in ("admin","owner","member","viewer") else db.execute("SELECT t.id,t.title,t.description,t.status,t.assigned_agent_id,t.deadline_at,o.title AS objective_title,o.description AS objective_description FROM tasks t JOIN objectives o ON o.id=t.objective_id AND o.workspace_id=t.workspace_id WHERE t.workspace_id=? AND o.status='approved' AND t.status='queued' AND (t.assigned_agent_id IS NULL OR t.assigned_agent_id=?) AND NOT EXISTS (SELECT 1 FROM json_each(t.depends_on) d LEFT JOIN tasks dep ON dep.id=d.value AND dep.workspace_id=t.workspace_id WHERE dep.status IS NULL OR dep.status!='completed') ORDER BY t.created_at LIMIT 100",(workspace_id,principal["agent_id"] or ""))
     data=[dict(x) for x in rows]
    return mcp_result({"content":[{"type":"text","text":json.dumps(data)}]})
   if tool=="propose_objective":
    if role not in ("admin","owner","member","agent"):return mcp_error(-32003,"Authenticated workspace credential required")
    title=str(args.get("title","" )).strip(); budget=args.get("budget_usd",0)
    if not title or len(title)>240 or not isinstance(budget,(int,float)) or budget<0 or budget>MAX_BUDGET:return mcp_error(-32602,"Invalid title or budget")
    oid=str(uuid.uuid4())
    with LOCK,connect() as db: db.execute("INSERT INTO objectives(id,workspace_id,title,description,budget,status) VALUES(?,?,?,?,?,'proposed')",(oid,workspace_id,title,str(args.get("description",""))[:4000],float(budget))); audit(db,"objective.proposed",oid,role,"source=mcp",workspace_id)
    return mcp_result({"content":[{"type":"text","text":json.dumps({"id":oid,"status":"proposed","approval_required":True})}]})
   return mcp_error(-32602,"Unknown tool")
  if path=="/a2a":
   request_id=body.get("id"); method=body.get("method"); params=body.get("params",{})
   if method not in ("message/send","SendMessage"):return self.reply(400,{"error":"supported A2A method: message/send"})
   if role not in ("admin","owner","member","agent"):return self.reply(403,{"error":"authenticated workspace credential required to propose an objective"})
   message=params.get("message",{}); parts=message.get("parts",[]); prompt="\n".join(str(p.get("text","")) for p in parts if p.get("type","text")=="text").strip()
   if not prompt:return self.reply(422,{"error":"message must include a text part"})
   title=prompt[:240]; budget=params.get("budget_usd",0)
   if not isinstance(budget,(int,float)) or budget<0 or budget>MAX_BUDGET:return self.reply(422,{"error":f"budget_usd must be between 0 and {MAX_BUDGET:.2f}"})
   oid=str(uuid.uuid4())
   with LOCK,connect() as db: db.execute("INSERT INTO objectives(id,workspace_id,title,description,budget,status) VALUES(?,?,?,?,?,'proposed')",(oid,workspace_id,title,prompt,float(budget))); audit(db,"objective.proposed",oid,role,"source=a2a; awaiting human approval",workspace_id)
   return self.reply(200,{"id":request_id,"result":{"id":oid,"status":{"state":"input-required"},"artifacts":[{"name":"approval","parts":[{"type":"text","text":"Objective is proposed and awaits human approval."}]}]}})
  if path=="/api/v1/plugins":
   if role not in ("admin","owner"):return self.reply(403,{"error":"workspace owner permission required to submit an extension"})
   pid=str(body.get("id","" )).strip().lower(); name=str(body.get("name","" )).strip()[:100]; version=str(body.get("version","")); api_version=str(body.get("api_version","")); permissions=body.get("requested_permissions",[]); image=body.get("container_image"); description=str(body.get("description",""))[:1000]
   if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}",pid) or not name:return self.reply(422,{"error":"extension id and name are required; id must be a lowercase slug"})
   if not re.fullmatch(r"\d+\.\d+\.\d+",version) or api_version!="v1":return self.reply(422,{"error":"version must be semantic x.y.z and api_version must be v1"})
   if not isinstance(permissions,list) or any(p not in ("read:objectives","read:tasks","write:results") for p in permissions):return self.reply(422,{"error":"requested_permissions contains unsupported permissions"})
   if image and not re.fullmatch(r"[A-Za-z0-9./:_-]+@sha256:[0-9a-f]{64}",image):return self.reply(422,{"error":"container_image must be pinned by a sha256 digest"})
   with LOCK,connect() as db:
    if db.execute("SELECT 1 FROM plugins WHERE id=?",(pid,)).fetchone():return self.reply(409,{"error":"extension id already exists"})
    db.execute("INSERT INTO plugins(id,workspace_id,name,version,api_version,requested_permissions,container_image,description,status) VALUES(?,?,?,?,?,?,?,?,'pending_review')",(pid,workspace_id,name,version,api_version,json.dumps(permissions),image,description)); audit(db,"plugin.submitted",pid,role,workspace_id=workspace_id)
   return self.reply(201,{"id":pid,"status":"pending_review","note":"Submitted extensions are not executable until approved by an owner."})
  if path=="/api/v1/workspaces":
   if role not in ("admin","owner"): return self.reply(403,{"error":"workspace owner permission required"})
   name=str(body.get("name","" )).strip()
   if not name or len(name)>100: return self.reply(422,{"error":"workspace name required (1-100 characters)"})
   wid=str(uuid.uuid4())
   with LOCK,connect() as db:
    db.execute("INSERT INTO workspaces(id,name) VALUES(?,?)",(wid,name)); key=self.mint_key(db,wid,"Workspace owner","owner")
   return self.reply(201,{"id":wid,"name":name,"owner_key":key,"warning":"Save this token now. It is shown only once."})
  if path=="/api/v1/backups":
   if not platform_admin:return self.reply(403,{"error":"bootstrap platform administrator permission required for full database backups"})
   backup_dir=os.getenv("AIOS_BACKUP_DIR",os.path.join(ROOT,"backups")); os.makedirs(backup_dir,mode=0o700,exist_ok=True); os.chmod(backup_dir,0o700)
   name="aios-"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")+".sqlite3"; target=os.path.join(backup_dir,name)
   try:
    with LOCK:
     source=sqlite3.connect(DB,timeout=10); destination=sqlite3.connect(target)
     try: source.backup(destination)
     finally: destination.close(); source.close()
    os.chmod(target,0o600)
   except sqlite3.Error as exc:
    try: os.remove(target)
    except OSError: pass
    return self.reply(500,{"error":"backup failed","detail":str(exc)[:200]})
   audit_db=connect()
   try: audit(audit_db,"backup.created",name,role,workspace_id=workspace_id); audit_db.commit()
   finally: audit_db.close()
   return self.reply(201,{"name":name,"size_bytes":os.path.getsize(target),"path":"backups/"+name,"mode":"0600"})
  if path=="/api/v1/import":
   if role not in ("admin","owner"):return self.reply(403,{"error":"workspace owner permission required"})
   if body.get("format")!="ai-os-workspace-export" or body.get("version")!=1 or not isinstance(body.get("tables"),dict):return self.reply(422,{"error":"unsupported AI OS export format"})
   tables=body["tables"]; agents=tables.get("agents",[]); objectives=tables.get("objectives",[]); tasks=tables.get("tasks",[])
   if any(not isinstance(x,list) for x in (agents,objectives,tasks)) or len(agents)>10000 or len(objectives)>10000 or len(tasks)>50000:return self.reply(422,{"error":"invalid or oversized export tables"})
   if any(not isinstance(x,dict) or not x.get("id") or not x.get("name") for x in agents):return self.reply(422,{"error":"invalid agent record"})
   if any(not isinstance(x,dict) or not x.get("id") or not x.get("title") or not isinstance(x.get("budget"), (int,float)) or x["budget"]<0 or x["budget"]>MAX_BUDGET for x in objectives):return self.reply(422,{"error":"invalid objective record"})
   objective_ids={x["id"] for x in objectives}
   if any(not isinstance(x,dict) or not x.get("id") or x.get("objective_id") not in objective_ids for x in tasks):return self.reply(422,{"error":"imported tasks must reference an included objective"})
   if any(len({x.get("id") for x in group})!=len(group) for group in (agents,objectives,tasks)):return self.reply(422,{"error":"duplicate IDs are not allowed in an import"})
   with LOCK,connect() as db:
    if any(db.execute(f"SELECT COUNT(*) FROM {table} WHERE workspace_id=?",(workspace_id,)).fetchone()[0] for table in ("agents","objectives","tasks")):return self.reply(409,{"error":"import is only allowed into an empty workspace"})
    agent_ids={a["id"]:str(uuid.uuid4()) for a in agents}; objective_id_map={o["id"]:str(uuid.uuid4()) for o in objectives}; task_ids={t["id"]:str(uuid.uuid4()) for t in tasks}
    for a in agents: db.execute("INSERT INTO agents(id,workspace_id,name,kind,description,capabilities,status) VALUES(?,?,?,?,?,?,?)",(agent_ids[a["id"]],workspace_id,str(a["name"])[:100],str(a.get("kind","custom"))[:40],str(a.get("description",""))[:500],json.dumps(a.get("capabilities",[])),"registered"))
    for o in objectives: db.execute("INSERT INTO objectives(id,workspace_id,title,description,budget,status) VALUES(?,?,?,?,?,'proposed')",(objective_id_map[o["id"]],workspace_id,str(o["title"])[:240],str(o.get("description",""))[:4000],float(o["budget"])))
    for t in tasks:
     old=t.get("status"); status=old if old in ("completed","failed","cancelled","expired") else "cancelled"
     spent=t.get("spent",0); spent=float(spent) if isinstance(spent,(int,float)) and spent>=0 else 0
     db.execute("INSERT INTO tasks(id,workspace_id,objective_id,title,description,status,result,spent,reserved,max_attempts,depends_on,assigned_agent_id) VALUES(?,?,?,?,?,?,?,?,0,3,'[]',?)",(task_ids[t["id"]],workspace_id,objective_id_map[t["objective_id"]],str(t.get("title","Imported task"))[:240],str(t.get("description",""))[:4000],status,str(t.get("result",""))[:4000],spent,agent_ids.get(t.get("assigned_agent_id"))))
    audit(db,"workspace.imported",workspace_id,role,json.dumps({"agents":len(agents),"objectives":len(objectives),"tasks":len(tasks)}),workspace_id)
   return self.reply(201,{"workspace_id":workspace_id,"imported":{"agents":len(agents),"objectives":len(objectives),"tasks":len(tasks)},"id_mapping":{"agents":agent_ids,"objectives":objective_id_map,"tasks":task_ids},"safety":"Imported records received new IDs; objectives were reset to proposed; unfinished tasks were canceled and require review."})
  if path=="/api/v1/api-keys":
   if role not in ("admin","owner"): return self.reply(403,{"error":"workspace owner permission required"})
   name=str(body.get("name","Agent key")).strip()[:100]; key_role=body.get("role","agent"); agent_id=body.get("agent_id")
   if key_role not in ("admin","member","viewer","agent"): return self.reply(422,{"error":"role must be admin, member, viewer, or agent"})
   if key_role in ("admin","owner") and not platform_admin: return self.reply(403,{"error":"only a bootstrap administrator can create a workspace administrator"})
   target_workspace=body.get("workspace_id",workspace_id)
   if not platform_admin and target_workspace!=workspace_id: return self.reply(403,{"error":"cannot create a key outside this workspace"})
   with LOCK,connect() as db:
    if not db.execute("SELECT 1 FROM workspaces WHERE id=?",(target_workspace,)).fetchone(): return self.reply(404,{"error":"workspace not found"})
    if key_role=="agent":
     if not agent_id or not db.execute("SELECT 1 FROM agents WHERE id=? AND workspace_id=?",(agent_id,target_workspace)).fetchone(): return self.reply(422,{"error":"agent key must be bound to an agent in the same workspace"})
    else: agent_id=None
    key=self.mint_key(db,target_workspace,name or "API key",key_role,agent_id); audit(db,"api_key.created",key["id"],role,json.dumps({"role":key_role,"agent_id":agent_id}),target_workspace)
   return self.reply(201,{**key,"warning":"Save this token now. It is shown only once."})
  if path=="/api/v1/agents":
   if role not in ("admin","owner","member"):return self.reply(403,{"error":"human workspace member required to register agents"})
   name=str(body.get("name","")).strip()
   if not name or len(name)>100: return self.reply(422,{"error":"name required (1-100 characters)"})
   item={"id":str(uuid.uuid4()),"name":name,"kind":str(body.get("kind","custom"))[:40],"description":str(body.get("description",""))[:500],"capabilities":body.get("capabilities",[]),"status":"registered"}
   with LOCK,connect() as db: db.execute("INSERT INTO agents(id,workspace_id,name,kind,description,capabilities) VALUES(?,?,?,?,?,?)",(item["id"],workspace_id,item["name"],item["kind"],item["description"],json.dumps(item["capabilities"]))); audit(db,"agent.registered",item["id"],role,workspace_id=workspace_id)
   return self.reply(201,item)
  if path=="/api/v1/objectives":
   if role not in ("admin","owner","member","agent"): return self.reply(403,{"error":"authenticated workspace credential required to propose objectives"})
   title=str(body.get("title","")).strip(); budget=body.get("budget_usd",0)
   if not title or len(title)>240: return self.reply(422,{"error":"title required (1-240 characters)"})
   if not isinstance(budget,(int,float)) or budget<0 or budget>MAX_BUDGET: return self.reply(422,{"error":f"budget must be between 0 and {MAX_BUDGET:.2f} USD"})
   item={"id":str(uuid.uuid4()),"title":title,"description":str(body.get("description",""))[:4000],"budget":float(budget),"status":"proposed","approval_required":True}
   with LOCK,connect() as db: db.execute("INSERT INTO objectives(id,workspace_id,title,description,budget,status) VALUES(?,?,?,?,?,?)",(item["id"],workspace_id,item["title"],item["description"],item["budget"],item["status"])); audit(db,"objective.proposed",item["id"],role,workspace_id=workspace_id)
   return self.reply(201,item)
  if path=="/api/v1/tasks":
   if role not in ("admin","owner","member"): return self.reply(403,{"error":"human workspace member required to create tasks"})
   title=str(body.get("title","")).strip(); description=str(body.get("description", ""))[:4000]; oid=body.get("objective_id"); assigned=body.get("assigned_agent_id")
   if not title: return self.reply(422,{"error":"title required"})
   with LOCK,connect() as db:
    obj=db.execute("SELECT status FROM objectives WHERE id=? AND workspace_id=?",(oid,workspace_id)).fetchone()
    if not obj: return self.reply(404,{"error":"objective not found"})
    if obj["status"]!="approved": return self.reply(409,{"error":"objective must be human-approved before tasks can be queued"})
    if assigned and not db.execute("SELECT 1 FROM agents WHERE id=? AND workspace_id=?",(assigned,workspace_id)).fetchone(): return self.reply(404,{"error":"assigned agent not found"})
    max_attempts=body.get("max_attempts",3); deadline=body.get("deadline_at"); depends=body.get("depends_on",[]); reservation=body.get("reserve_usd",0)
    if not isinstance(max_attempts,int) or max_attempts<1 or max_attempts>10:return self.reply(422,{"error":"max_attempts must be from 1 to 10"})
    if not isinstance(reservation,(int,float)) or reservation<0:return self.reply(422,{"error":"reserve_usd must be a non-negative number"})
    if deadline:
     try: deadline=parse_datetime(deadline).isoformat().replace("+00:00","Z")
     except (AttributeError,ValueError): return self.reply(422,{"error":"deadline_at must be an ISO 8601 timestamp"})
    if not isinstance(depends,list) or any(not isinstance(x,str) for x in depends):return self.reply(422,{"error":"depends_on must be a list of task IDs"})
    for dep in depends:
     if dep=="" or not db.execute("SELECT 1 FROM tasks WHERE id=? AND workspace_id=? AND objective_id=?",(dep,workspace_id,oid)).fetchone(): return self.reply(422,{"error":"each dependency must be a task in the same objective and workspace"})
    task_id=str(uuid.uuid4()); item={"id":task_id,"objective_id":oid,"title":title,"description":description,"status":"queued","spent":0,"reserved":0,"reservation_target":float(reservation),"assigned_agent_id":assigned,"max_attempts":max_attempts,"deadline_at":deadline,"depends_on":depends}
    db.execute("INSERT INTO tasks(id,workspace_id,objective_id,title,description,status,assigned_agent_id,reservation_target,max_attempts,deadline_at,depends_on) VALUES(?,?,?,?,?,'queued',?,?,?,?,?)",(task_id,workspace_id,oid,title,description,assigned,float(reservation),max_attempts,deadline,json.dumps(depends))); audit(db,"task.queued",task_id,role,json.dumps({"assigned_agent_id":assigned,"depends_on":depends,"reserve_usd":reservation}),workspace_id)
   return self.reply(201,item)
  parts=path.strip("/").split("/")
  if len(parts)==5 and parts[:3]==["api","v1","tasks"] and parts[4]=="execute":
   if role not in ("admin","owner"):return self.reply(403,{"error":"workspace owner permission required to execute a plugin task"})
   if os.getenv("AIOS_ENABLE_SANDBOX")!="1" or not shutil.which("docker"):return self.reply(503,{"error":"isolated Docker runner is unavailable or disabled"})
   tid=parts[3]; plugin_id=body.get("plugin_id"); payload=body.get("payload",{})
   if not isinstance(payload,dict):return self.reply(422,{"error":"payload must be a JSON object"})
   with LOCK,connect() as db:
    task=db.execute("SELECT t.*,o.status AS objective_status FROM tasks t JOIN objectives o ON o.id=t.objective_id AND o.workspace_id=t.workspace_id WHERE t.id=? AND t.workspace_id=?",(tid,workspace_id)).fetchone()
    plugin=db.execute("SELECT * FROM plugins WHERE id=? AND status='approved'",(plugin_id,)).fetchone()
    if not task:return self.reply(404,{"error":"task not found"})
    if not plugin or not plugin["container_image"]:return self.reply(404,{"error":"approved runnable extension not found"})
    if task["status"]!="queued" or task["objective_status"]!="approved":return self.reply(409,{"error":"task must be queued under a human-approved objective"})
    if task["assigned_agent_id"]:return self.reply(409,{"error":"task is assigned to an agent; plugin execution requires an unassigned task"})
    unmet=[d[0] for d in db.execute("SELECT dep.status FROM json_each(?) j LEFT JOIN tasks dep ON dep.id=j.value AND dep.workspace_id=?",(task["depends_on"] or "[]",workspace_id)) if d[0]!="completed"]
    if unmet:return self.reply(409,{"error":"task dependencies are not complete"})
    if task["attempts"]>=task["max_attempts"]:return self.reply(409,{"error":"task has reached its attempt limit"})
    if task["deadline_at"]:
     try:
      deadline_at=parse_datetime(task["deadline_at"])
      if deadline_at<=datetime.datetime.now(datetime.timezone.utc):return self.reply(409,{"error":"task deadline has passed"})
     except ValueError:return self.reply(409,{"error":"task has an invalid deadline"})
    db.execute("UPDATE tasks SET status='running',claimed_by=?,attempts=attempts+1,updated_at=CURRENT_TIMESTAMP WHERE id=?",("plugin:"+plugin_id,tid)); audit(db,"task.sandbox_started",tid,role,json.dumps({"plugin_id":plugin_id}),workspace_id); db.execute("INSERT INTO task_events(workspace_id,task_id,event,payload) VALUES(?,?,?,?)",(workspace_id,tid,"sandbox_started",json.dumps({"plugin_id":plugin_id})))
   try:
    output=run_sandbox(plugin["container_image"],payload)
    status="completed"; result=output[:4000]
   except SandboxError as exc:
    status="failed"; result=str(exc)[:1000]
   with LOCK,connect() as db:
    db.execute("UPDATE tasks SET status=?,result=?,spent=0,reserved=0,updated_at=CURRENT_TIMESTAMP WHERE id=? AND workspace_id=? AND status='running'",(status,result,tid,workspace_id)); audit(db,"task.sandbox_"+status,tid,"plugin:"+plugin_id,json.dumps({"spent_usd":0}),workspace_id); db.execute("INSERT INTO task_events(workspace_id,task_id,event,payload) VALUES(?,?,?,?)",(workspace_id,tid,"sandbox_"+status,json.dumps({"plugin_id":plugin_id})))
   return self.reply(200,{"id":tid,"status":status,"result":result,"spent_usd":0,"sandbox":{"network":"none","read_only":True,"image_digest_pinned":True}})
  if len(parts)==5 and parts[:3]==["api","v1","tasks"] and parts[4]=="claim":
   if role!="agent": return self.reply(403,{"error":"agent credential required"})
   tid=parts[3]; agent_id=principal["agent_id"] or str(body.get("agent_id",""))
   with LOCK,connect() as db:
    agent=db.execute("SELECT id FROM agents WHERE id=? AND workspace_id=?",(agent_id,workspace_id)).fetchone(); task=db.execute("SELECT t.*,o.status AS objective_status,o.budget AS budget,o.title AS objective_title,o.description AS objective_description FROM tasks t JOIN objectives o ON o.id=t.objective_id AND o.workspace_id=t.workspace_id WHERE t.id=? AND t.workspace_id=?",(tid,workspace_id)).fetchone()
    if not agent:return self.reply(404,{"error":"agent not found"})
    if not task:return self.reply(404,{"error":"task not found"})
    if task["objective_status"]!="approved":return self.reply(409,{"error":"objective is not approved"})
    if task["status"]!="queued":return self.reply(409,{"error":"task is not available"})
    if task["assigned_agent_id"] and task["assigned_agent_id"]!=agent_id:return self.reply(403,{"error":"task is assigned to another agent"})
    if task["deadline_at"] and parse_datetime(task["deadline_at"])<datetime.datetime.now(datetime.timezone.utc):
     db.execute("UPDATE tasks SET status='expired',updated_at=CURRENT_TIMESTAMP WHERE id=?",(tid,)); audit(db,"task.expired",tid,agent_id,workspace_id=workspace_id); return self.reply(410,{"error":"task deadline has passed"})
    unmet=[d[0] for d in db.execute("SELECT dep.status FROM json_each(?) j LEFT JOIN tasks dep ON dep.id=j.value AND dep.workspace_id=?",(task["depends_on"] or "[]",workspace_id)) if d[0]!="completed"]
    if unmet:return self.reply(409,{"error":"task dependencies are not complete"})
    totals=db.execute("SELECT COALESCE(SUM(spent),0),COALESCE(SUM(reserved),0) FROM tasks WHERE objective_id=? AND workspace_id=?",(task["objective_id"],workspace_id)).fetchone(); available=max(0,float(task["budget"])-float(totals[0])-float(totals[1])); reserve=float(task["reservation_target"] or 0) or available
    if reserve>available:return self.reply(409,{"error":"requested reservation exceeds the remaining objective budget"})
    db.execute("UPDATE tasks SET status='running',claimed_by=?,reserved=?,attempts=attempts+1,updated_at=CURRENT_TIMESTAMP WHERE id=?",(agent_id,reserve,tid)); audit(db,"task.claimed",tid,agent_id,json.dumps({"reserved_usd":reserve}),workspace_id); db.execute("INSERT INTO task_events(workspace_id,task_id,event,payload) VALUES(?,?,?,?)",(workspace_id,tid,"claimed",json.dumps({"agent_id":agent_id,"reserved_usd":reserve})))
    task=dict(task); task.update(status="running",claimed_by=agent_id,reserved=reserve,attempts=task["attempts"]+1); return self.reply(200,task)
  return self.reply(404,{"error":"not found"})
 def do_PATCH(self):
  principal=principal_for(self.headers)
  if not principal:return self.reply(401,{"error":"unauthorized"})
  role=principal["role"]; workspace_id=principal["workspace_id"]; platform_admin=role=="admin" and not principal.get("key_id")
  path=urlparse(self.path).path; parts=path.strip("/").split("/"); body=self.body()
  if body is None:return self.reply(400,{"error":"invalid JSON"})
  if len(parts)==5 and parts[:3]==["api","v1","objectives"] and parts[4]=="approve":
   if role not in ("admin","owner"):return self.reply(403,{"error":"human workspace owner approval required"})
   oid=parts[3]
   with LOCK,connect() as db:
    obj=db.execute("SELECT * FROM objectives WHERE id=? AND workspace_id=?",(oid,workspace_id)).fetchone()
    if not obj:return self.reply(404,{"error":"objective not found"})
    if obj["status"]!="proposed":return self.reply(409,{"error":"objective is not awaiting approval"})
    db.execute("UPDATE objectives SET status='approved',approved_at=CURRENT_TIMESTAMP WHERE id=? AND workspace_id=?",(oid,workspace_id)); audit(db,"objective.approved",oid,"human-admin",workspace_id=workspace_id)
    return self.reply(200,{**dict(obj),"status":"approved"})
  if len(parts)==5 and parts[:3]==["api","v1","tasks"] and parts[4] in ("cancel","retry"):
   if role not in ("admin","owner"):return self.reply(403,{"error":"workspace owner permission required"})
   tid=parts[3]; action=parts[4]
   with LOCK,connect() as db:
    row=db.execute("SELECT * FROM tasks WHERE id=? AND workspace_id=?",(tid,workspace_id)).fetchone()
    if not row:return self.reply(404,{"error":"task not found"})
    if action=="cancel":
     if row["status"] not in ("queued","running"):return self.reply(409,{"error":"only queued or running tasks can be cancelled"})
     new_status="cancelled" if row["status"]=="queued" else "cancel_requested"
     db.execute("UPDATE tasks SET status=?,reserved=CASE WHEN ?='queued' THEN 0 ELSE reserved END,updated_at=CURRENT_TIMESTAMP WHERE id=?",(new_status,row["status"],tid)); audit(db,"task."+new_status,tid,role,workspace_id=workspace_id); db.execute("INSERT INTO task_events(workspace_id,task_id,event,payload) VALUES(?,?,?,?)",(workspace_id,tid,new_status,"{}"))
     return self.reply(200,{"id":tid,"status":new_status,"note":"Running work is external; the worker must poll and honor cancellation."})
    if row["status"]!="failed" or row["attempts"]>=row["max_attempts"]:return self.reply(409,{"error":"only failed tasks with attempts remaining can be retried"})
    db.execute("UPDATE tasks SET status='queued',claimed_by=NULL,result=NULL,reserved=0,updated_at=CURRENT_TIMESTAMP WHERE id=?",(tid,)); audit(db,"task.requeued",tid,role,workspace_id=workspace_id); db.execute("INSERT INTO task_events(workspace_id,task_id,event,payload) VALUES(?,?,?,?)",(workspace_id,tid,"requeued","{}"))
    return self.reply(200,{"id":tid,"status":"queued","attempts":row["attempts"],"max_attempts":row["max_attempts"]})
  if len(parts)==4 and parts[:3]==["api","v1","plugins"]:
   if not platform_admin:return self.reply(403,{"error":"bootstrap platform administrator review is required for the shared extension catalog"})
   status=body.get("status")
   if status not in ("approved","rejected"):return self.reply(422,{"error":"status must be approved or rejected"})
   with LOCK,connect() as db:
    row=db.execute("SELECT id,container_image FROM plugins WHERE id=?",(parts[3],)).fetchone()
    if not row:return self.reply(404,{"error":"extension not found"})
    db.execute("UPDATE plugins SET status=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?",(status,parts[3])); audit(db,"plugin."+status,parts[3],role,workspace_id=workspace_id)
   return self.reply(200,{"id":parts[3],"status":status,"sandbox_eligible":bool(row["container_image"]),"note":"Metadata review is one gate; execution also requires the opt-in sandbox and a local digest-pinned image."})
  if len(parts)==4 and parts[:3]==["api","v1","tasks"]:
   if role!="agent":return self.reply(403,{"error":"agent credential required to report results"})
   tid=parts[3]; status=body.get("status"); result=str(body.get("result",""))[:4000]; spent=body.get("spent_usd",0); agent_id=principal["agent_id"] or body.get("agent_id")
   if status not in ("completed","failed","cancelled"):return self.reply(422,{"error":"status must be completed, failed, or cancelled"})
   if not isinstance(spent,(int,float)) or spent<0:return self.reply(422,{"error":"spent_usd must be a non-negative number"})
   with LOCK,connect() as db:
    row=db.execute("SELECT t.*,o.budget,o.status AS objective_status FROM tasks t JOIN objectives o ON o.id=t.objective_id AND o.workspace_id=t.workspace_id WHERE t.id=? AND t.workspace_id=?",(tid,workspace_id)).fetchone()
    if not row:return self.reply(404,{"error":"task not found"})
    if row["claimed_by"]!=agent_id or not agent_id:return self.reply(403,{"error":"task is claimed by a different agent"})
    if row["objective_status"]!="approved":return self.reply(409,{"error":"objective is not approved"})
    if status=="cancelled" and row["status"]!="cancel_requested":return self.reply(409,{"error":"task cancellation was not requested"})
    if status!="cancelled" and row["status"]!="running":return self.reply(409,{"error":"task is not running"})
    if spent>float(row["reserved"] or 0):return self.reply(422,{"error":"reported spend exceeds the task's reserved amount"})
    db.execute("UPDATE tasks SET status=?,result=?,spent=?,reserved=0,updated_at=CURRENT_TIMESTAMP WHERE id=?",(status,result,float(spent),tid)); audit(db,"task."+status,tid,agent_id,json.dumps({"spent_usd":spent}),workspace_id); db.execute("INSERT INTO task_events(workspace_id,task_id,event,payload) VALUES(?,?,?,?)",(workspace_id,tid,status,json.dumps({"agent_id":agent_id,"spent_usd":spent})))
    return self.reply(200,{"id":tid,"status":status,"result":result,"spent_usd":spent})
  return self.reply(404,{"error":"not found"})
 def do_DELETE(self):
  principal=principal_for(self.headers)
  if not principal:return self.reply(401,{"error":"unauthorized"})
  if principal["role"] not in ("admin","owner"):return self.reply(403,{"error":"workspace owner permission required"})
  path=urlparse(self.path).path; parts=path.strip("/").split("/")
  if len(parts)!=4 or parts[:3]!=["api","v1","api-keys"]:return self.reply(404,{"error":"not found"})
  with LOCK,connect() as db:
   row=db.execute("SELECT id FROM api_keys WHERE id=? AND workspace_id=? AND revoked_at IS NULL",(parts[3],principal["workspace_id"])).fetchone()
   if not row:return self.reply(404,{"error":"API key not found"})
   db.execute("UPDATE api_keys SET revoked_at=CURRENT_TIMESTAMP WHERE id=?",(parts[3],)); audit(db,"api_key.revoked",parts[3],principal["role"],workspace_id=principal["workspace_id"])
  return self.reply(200,{"id":parts[3],"revoked":True})
 def log_message(self,*_):pass
if __name__=="__main__":
 host=os.getenv("AIOS_HOST","127.0.0.1"); port=int(os.getenv("PORT","8000"))
 if host not in ("127.0.0.1","localhost","::1") and not ADMIN_TOKEN:
  raise SystemExit("Refusing to listen on a public interface without AIOS_ADMIN_TOKEN")
 print(f"AI OS listening on http://{host}:{port}"); ThreadingHTTPServer((host,port),Handler).serve_forever()
