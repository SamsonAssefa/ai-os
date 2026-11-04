import json, os, subprocess, sys, time, unittest, urllib.request, urllib.error
class ApiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.port=18765; cls.proc=subprocess.Popen([sys.executable,'server.py'],cwd=os.path.dirname(os.path.dirname(__file__)),env={**os.environ,'PORT':str(cls.port),'AIOS_DB_PATH':os.path.join(os.path.dirname(__file__),'test.sqlite3')},stdout=subprocess.DEVNULL)
  cls.base=f'http://127.0.0.1:{cls.port}/api/v1'
  for _ in range(40):
   try: urllib.request.urlopen(cls.base+'/health'); break
   except Exception: time.sleep(.1)
 @classmethod
 def tearDownClass(cls):
  cls.proc.terminate(); cls.proc.wait(timeout=3)
  for suffix in ('','-shm','-wal'):
   try: os.remove(os.path.join(os.path.dirname(__file__),'test.sqlite3'+suffix))
   except FileNotFoundError: pass
 def request(self,path,method='GET',payload=None,role='admin'):
  data=json.dumps(payload or {}).encode() if method!='GET' else None
  req=urllib.request.Request(self.base+path,data=data,method=method,headers={'Content-Type':'application/json','X-AI-OS-Role':role})
  try:return urllib.request.urlopen(req)
  except urllib.error.HTTPError as e:return e
 def test_objective_requires_approval_before_task_queue(self):
  obj=json.load(self.request('/objectives','POST',{'title':'Pilot','budget_usd':2})); self.assertEqual(obj['status'],'proposed')
  self.assertEqual(self.request('/tasks','POST',{'title':'Do work','objective_id':obj['id']}).code,409)
  self.assertEqual(self.request(f"/objectives/{obj['id']}/approve",'PATCH',{},'admin').code,200)
  self.assertEqual(self.request('/tasks','POST',{'title':'Do work','objective_id':obj['id']}).code,201)
 def test_agent_claims_and_reports_within_budget(self):
  agent=json.load(self.request('/agents','POST',{'name':'Test agent'},'admin'))
  obj=json.load(self.request('/objectives','POST',{'title':'Budgeted','budget_usd':1},'admin'))
  self.request(f"/objectives/{obj['id']}/approve",'PATCH',{},'admin')
  task=json.load(self.request('/tasks','POST',{'title':'Run','objective_id':obj['id']},'admin'))
  self.assertEqual(self.request(f"/tasks/{task['id']}/claim",'POST',{'agent_id':agent['id']},'agent').code,200)
  self.assertEqual(self.request(f"/tasks/{task['id']}",'PATCH',{'agent_id':agent['id'],'status':'completed','result':'done','spent_usd':1.01},'agent').code,422)
  self.assertEqual(self.request(f"/tasks/{task['id']}",'PATCH',{'agent_id':agent['id'],'status':'completed','result':'done','spent_usd':.25},'agent').code,200)
 def test_agent_assignment_limits_who_can_claim(self):
  a1=json.load(self.request('/agents','POST',{'name':'Assigned agent'},'admin'))
  a2=json.load(self.request('/agents','POST',{'name':'Other agent'},'admin'))
  obj=json.load(self.request('/objectives','POST',{'title':'Assigned','budget_usd':1},'admin'))
  self.request(f"/objectives/{obj['id']}/approve",'PATCH',{},'admin')
  task=json.load(self.request('/tasks','POST',{'title':'Private route','objective_id':obj['id'],'assigned_agent_id':a1['id']},'admin'))
  self.assertEqual(self.request(f"/tasks/{task['id']}/claim",'POST',{'agent_id':a2['id']},'agent').code,403)
  self.assertEqual(self.request(f"/tasks/{task['id']}/claim",'POST',{'agent_id':a1['id']},'agent').code,200)
 def test_workflow_templates_are_discoverable(self):
  templates=json.load(self.request('/workflow-templates','GET',role='admin'))
  self.assertIn('research-brief',[t['id'] for t in templates])
 def test_budget_cap(self): self.assertEqual(self.request('/objectives','POST',{'title':'Too much','budget_usd':5.01}).code,422)
if __name__=='__main__': unittest.main()
