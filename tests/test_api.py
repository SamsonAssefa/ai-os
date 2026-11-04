import json
import os
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(__file__))
TEST_DB = os.path.join(os.path.dirname(__file__), "test.sqlite3")

class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = 18765
        test_env = {**os.environ, "PORT": str(cls.port), "AIOS_HOST": "127.0.0.1", "AIOS_DB_PATH": TEST_DB}
        test_env.pop("AIOS_ADMIN_TOKEN", None)
        test_env.pop("AIOS_AGENT_TOKEN", None)
        cls.proc = subprocess.Popen(
            [sys.executable, "server.py"], cwd=ROOT,
            env=test_env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        cls.base = f"http://127.0.0.1:{cls.port}/api/v1"
        for _ in range(50):
            if cls.proc.poll() is not None:
                raise RuntimeError("AI OS test server could not start")
            try:
                urllib.request.urlopen(cls.base + "/health", timeout=1)
                break
            except Exception:
                time.sleep(.1)
        else:
            raise RuntimeError("AI OS test server did not become ready")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "proc", None) and cls.proc.poll() is None:
            cls.proc.terminate()
            cls.proc.wait(timeout=3)
        for suffix in ("", "-shm", "-wal"):
            try:
                os.remove(TEST_DB + suffix)
            except FileNotFoundError:
                pass

    def request(self, path, method="GET", payload=None, role="admin", token=None):
        data = json.dumps(payload or {}).encode() if method != "GET" else None
        headers = {"Content-Type": "application/json", "X-AI-OS-Role": role}
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            return urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as exc:
            return exc

    def proposal_and_task(self, title="Pilot", budget=2):
        obj = json.load(self.request("/objectives", "POST", {"title": title, "budget_usd": budget}))
        self.assertEqual(obj["status"], "proposed")
        self.assertEqual(self.request(f"/objectives/{obj['id']}/approve", "PATCH", {}).code, 200)
        return obj

    def test_objective_approval_required_before_queue(self):
        obj = json.load(self.request("/objectives", "POST", {"title": "Pilot", "budget_usd": 2}))
        self.assertEqual(self.request("/tasks", "POST", {"title": "Do work", "objective_id": obj["id"]}).code, 409)
        self.assertEqual(self.request(f"/objectives/{obj['id']}/approve", "PATCH", {}).code, 200)
        self.assertEqual(self.request("/tasks", "POST", {"title": "Do work", "objective_id": obj["id"], "description": "Specific instructions"}).code, 201)

    def test_agent_claims_and_reports_within_reservation(self):
        agent = json.load(self.request("/agents", "POST", {"name": "Test agent"}))
        obj = self.proposal_and_task("Budgeted", 1)
        task = json.load(self.request("/tasks", "POST", {"title": "Run", "objective_id": obj["id"], "description": "Use this context"}))
        claimed = json.load(self.request(f"/tasks/{task['id']}/claim", "POST", {"agent_id": agent["id"]}, "agent"))
        self.assertEqual(claimed["description"], "Use this context")
        self.assertEqual(claimed["objective_title"], "Budgeted")
        self.assertEqual(self.request(f"/tasks/{task['id']}", "PATCH", {"agent_id": agent["id"], "status": "completed", "result": "done", "spent_usd": 1.01}, "agent").code, 422)
        self.assertEqual(self.request(f"/tasks/{task['id']}", "PATCH", {"agent_id": agent["id"], "status": "completed", "result": "done", "spent_usd": .25}, "agent").code, 200)

    def test_assignment_and_bound_key_identity(self):
        a1 = json.load(self.request("/agents", "POST", {"name": "Assigned agent"}))
        a2 = json.load(self.request("/agents", "POST", {"name": "Other agent"}))
        key1 = json.load(self.request("/api-keys", "POST", {"name": "bound agent 1", "role": "agent", "agent_id": a1["id"]}))
        key2 = json.load(self.request("/api-keys", "POST", {"name": "bound agent 2", "role": "agent", "agent_id": a2["id"]}))
        obj = self.proposal_and_task("Assigned", 1)
        task = json.load(self.request("/tasks", "POST", {"title": "Private route", "objective_id": obj["id"], "assigned_agent_id": a2["id"]}))
        self.assertEqual(self.request(f"/tasks/{task['id']}/claim", "POST", {}, "agent", key1["token"]).code, 403)
        claimed = self.request(f"/tasks/{task['id']}/claim", "POST", {}, "agent", key2["token"])
        self.assertEqual(claimed.code, 200)
        self.assertEqual(json.load(claimed)["claimed_by"], a2["id"])

    def test_workspace_keys_are_isolated_and_cannot_create_full_db_backup(self):
        created = json.load(self.request("/workspaces", "POST", {"name": "isolated"}))
        owner = created["owner_key"]["token"]
        proposal = json.load(self.request("/objectives", "POST", {"title": "Private", "budget_usd": 1}, token=owner))
        self.assertEqual(len(json.load(self.request("/objectives", token=owner))), 1)
        local_objectives = json.load(self.request("/objectives"))
        self.assertNotIn("Private", [item["title"] for item in local_objectives])
        self.assertEqual(self.request("/backups", "POST", {}, token=owner).code, 403)
        self.assertEqual(self.request("/api-keys", "POST", {"name": "admin", "role": "admin"}, token=owner).code, 403)
        other = json.load(self.request("/workspaces", "POST", {"name": "other"}))
        self.assertEqual(self.request("/api-keys", "POST", {"name": "cross workspace", "role": "member", "workspace_id": other["id"]}, token=owner).code, 403)
        pending = json.load(self.request("/plugins", "POST", {"id": "owner-addon", "name": "Owner addon", "version": "1.0.0", "api_version": "v1", "requested_permissions": [], "description": "Pending metadata"}, token=owner))
        self.assertEqual(self.request("/plugins/owner-addon", "PATCH", {"status": "approved"}, token=owner).code, 403)
        self.assertEqual(self.request("/objectives/does-not-exist/approve", "PATCH", {}, token=owner).code, 404)
        self.assertEqual(proposal["status"], "proposed")

    def test_agent_can_propose_but_cannot_queue_or_register(self):
        agent = json.load(self.request("/agents", "POST", {"name": "Proposal agent"}))
        key = json.load(self.request("/api-keys", "POST", {"name": "proposal key", "role": "agent", "agent_id": agent["id"]}))["token"]
        proposal = json.load(self.request("/objectives", "POST", {"title": "AI suggestion", "budget_usd": 1}, token=key))
        self.assertEqual(proposal["status"], "proposed")
        self.assertEqual(self.request("/agents", "POST", {"name": "No"}, role="agent", token=key).code, 403)
        self.assertEqual(self.request("/tasks", "POST", {"title": "No", "objective_id": proposal["id"]}, role="agent", token=key).code, 403)
        self.assertEqual(self.request(f"/objectives/{proposal['id']}/approve", "PATCH", {}, role="agent", token=key).code, 403)

    def test_deadline_and_dependency_controls(self):
        agent = json.load(self.request("/agents", "POST", {"name": "Deadline agent"}))
        obj = self.proposal_and_task("Dependencies", 1)
        first = json.load(self.request("/tasks", "POST", {"title": "First", "objective_id": obj["id"], "reserve_usd": .5}))
        later = json.load(self.request("/tasks", "POST", {"title": "Later", "objective_id": obj["id"], "depends_on": [first["id"]], "reserve_usd": .5}))
        visible = json.load(self.request("/tasks", role="agent"))
        self.assertIn(first["id"], [t["id"] for t in visible])
        self.assertNotIn(later["id"], [t["id"] for t in visible])
        claimed = json.load(self.request(f"/tasks/{first['id']}/claim", "POST", {"agent_id": agent["id"]}, "agent"))
        self.assertEqual(self.request(f"/tasks/{first['id']}", "PATCH", {"agent_id": agent["id"], "status": "completed", "spent_usd": .1}, "agent").code, 200)
        visible = json.load(self.request("/tasks", role="agent"))
        self.assertIn(later["id"], [t["id"] for t in visible])
        expired = json.load(self.request("/tasks", "POST", {"title": "Expired", "objective_id": obj["id"], "deadline_at": "2000-01-01T00:00:00"}))
        self.assertEqual(self.request(f"/tasks/{expired['id']}/claim", "POST", {"agent_id": agent["id"]}, "agent").code, 410)

    def test_mcp_and_a2a_proposals_stay_approval_gated(self):
        mcp = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/mcp",
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "propose_objective", "arguments": {"title": "MCP proposal", "budget_usd": 1}}}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        mcp_result = json.load(urllib.request.urlopen(mcp, timeout=3))
        self.assertEqual(json.loads(mcp_result["result"]["content"][0]["text"])["status"], "proposed")
        a2a = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/a2a",
            data=json.dumps({"id": "req-1", "method": "message/send", "params": {"message": {"parts": [{"type": "text", "text": "A2A proposal"}]}, "budget_usd": 1}}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        a2a_result = json.load(urllib.request.urlopen(a2a, timeout=3))
        self.assertEqual(a2a_result["result"]["status"]["state"], "input-required")

    def test_extension_metadata_needs_admin_review_and_runner_stays_opt_in(self):
        submitted = json.load(self.request("/plugins", "POST", {"id": "example-addon", "name": "Example", "version": "1.0.0", "api_version": "v1", "requested_permissions": ["read:tasks"], "description": "Test catalog item"}))
        self.assertEqual(submitted["status"], "pending_review")
        reviewed = json.load(self.request("/plugins/example-addon", "PATCH", {"status": "approved"}))
        self.assertEqual(reviewed["status"], "approved")
        self.assertFalse(reviewed["sandbox_eligible"])
        self.assertEqual(self.request("/tasks/demo/execute", "POST", {"plugin_id": "example-addon"}).code, 503)

    def test_workspace_export_import_resets_objectives_for_review(self):
        source = json.load(self.request("/workspaces", "POST", {"name": "export source"}))
        source_token = source["owner_key"]["token"]
        proposal = json.load(self.request("/objectives", "POST", {"title": "Portable objective", "budget_usd": 1}, token=source_token))
        exported = json.load(self.request("/export", token=source_token))
        target = json.load(self.request("/workspaces", "POST", {"name": "import target"}))
        imported = json.load(self.request("/import", "POST", exported, token=target["owner_key"]["token"]))
        self.assertEqual(imported["imported"]["objectives"], 1)
        recovered = json.load(self.request("/objectives", token=target["owner_key"]["token"]))
        self.assertEqual(recovered[0]["status"], "proposed")
        self.assertNotEqual(recovered[0]["id"], proposal["id"])
        self.assertEqual(imported["id_mapping"]["objectives"][proposal["id"]], recovered[0]["id"])

    def test_cancel_and_retry_leave_an_event_trail(self):
        obj = self.proposal_and_task("Recovery", 1)
        task = json.load(self.request("/tasks", "POST", {"title": "Recoverable", "objective_id": obj["id"], "max_attempts": 2}))
        self.assertEqual(self.request(f"/tasks/{task['id']}/cancel", "PATCH", {}).code, 200)
        self.assertEqual(self.request(f"/tasks/{task['id']}/retry", "PATCH", {}).code, 409)
        agent = json.load(self.request("/agents", "POST", {"name": "Recovery agent"}))
        retryable = json.load(self.request("/tasks", "POST", {"title": "Fail once", "objective_id": obj["id"], "max_attempts": 2}))
        self.request(f"/tasks/{retryable['id']}/claim", "POST", {"agent_id": agent["id"]}, "agent")
        self.assertEqual(self.request(f"/tasks/{retryable['id']}", "PATCH", {"agent_id": agent["id"], "status": "failed", "spent_usd": 0}, "agent").code, 200)
        self.assertEqual(self.request(f"/tasks/{retryable['id']}/retry", "PATCH", {}).code, 200)
        events = json.load(self.request(f"/tasks/{retryable['id']}/events"))
        self.assertIn("requeued", [event["event"] for event in events])

    def test_health_reports_current_release(self):
        self.assertEqual(json.load(self.request("/health"))["version"], "0.6.0")

    def test_workflow_templates_are_discoverable(self):
        templates = json.load(self.request("/workflow-templates"))
        self.assertIn("research-brief", [item["id"] for item in templates])

    def test_identity_and_metrics_reflect_credential_scope(self):
        root = json.load(self.request("/me"))
        self.assertTrue(root["platform_admin"])
        self.assertTrue(root["can_view_metrics"])
        metrics = json.load(self.request("/metrics"))
        self.assertEqual(metrics["budget_limit_usd"], 5)
        workspace = json.load(self.request("/workspaces", "POST", {"name": "role check"}))
        owner = json.load(self.request("/me", token=workspace["owner_key"]["token"]))
        self.assertEqual(owner["role"], "owner")
        self.assertFalse(owner["platform_admin"])
        agent = json.load(self.request("/agents", "POST", {"name": "Metrics agent"}))
        agent_key = json.load(self.request("/api-keys", "POST", {"name": "metrics agent", "role": "agent", "agent_id": agent["id"]}))
        agent_me = json.load(self.request("/me", role="agent", token=agent_key["token"]))
        self.assertFalse(agent_me["can_manage_tasks"])
        self.assertFalse(agent_me["can_view_metrics"])
        self.assertEqual(self.request("/metrics", token=agent_key["token"]).code, 403)

    def test_budget_cap_and_disabled_runner(self):
        self.assertEqual(self.request("/objectives", "POST", {"title": "Too much", "budget_usd": 5.01}).code, 422)
        self.assertFalse(json.load(self.request("/runner/status"))["enabled"])

if __name__ == "__main__":
    unittest.main()
