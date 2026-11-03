import json, os, subprocess, sys, time, unittest, urllib.request, urllib.error

class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = 18765
        cls.proc = subprocess.Popen([sys.executable, 'server.py'], cwd=os.path.dirname(os.path.dirname(__file__)), env={**os.environ,'PORT':str(cls.port)}, stdout=subprocess.DEVNULL)
        cls.base=f'http://127.0.0.1:{cls.port}/api/v1'
        for _ in range(40):
            try: urllib.request.urlopen(cls.base+'/health'); break
            except Exception: time.sleep(.1)
    @classmethod
    def tearDownClass(cls): cls.proc.terminate(); cls.proc.wait(timeout=3)
    def post(self,path,payload):
        req=urllib.request.Request(self.base+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        try: return urllib.request.urlopen(req)
        except urllib.error.HTTPError as e: return e
    def test_objective_and_task_lifecycle_is_approval_gated(self):
        r=self.post('/objectives',{'title':'Test proposal','budget_usd':2}); self.assertEqual(r.status,201)
        obj=json.load(r); self.assertEqual(obj['status'],'proposed'); self.assertTrue(obj['approval_required'])
        t=self.post('/tasks',{'title':'Inspect docs','objective_id':obj['id']}); self.assertEqual(t.status,201)
        self.assertEqual(json.load(t)['status'],'queued')
    def test_budget_ceiling(self): self.assertEqual(self.post('/objectives',{'title':'Over budget','budget_usd':5.01}).code,422)
    def test_missing_objective_rejected(self): self.assertEqual(self.post('/tasks',{'title':'Orphan','objective_id':'nope'}).code,404)

if __name__=='__main__': unittest.main()
