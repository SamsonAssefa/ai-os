"""Dependency-free Python client for AI OS."""

import json
import urllib.error
import urllib.parse
import urllib.request


class AIOSAPIError(RuntimeError):
    """An HTTP error returned by the AI OS API."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class AIOSClient:
    """Call an AI OS instance using a workspace or agent API key.

    ``base_url`` may be the API root (``http://localhost:8000/api/v1``) or
    the site root (``http://localhost:8000``). Agent keys should be bound to
    a registered agent; the server then supplies its identity during claims.
    """

    def __init__(self, base_url="http://localhost:8000", api_key=None, timeout=30):
        self.base_url = base_url.rstrip("/")
        if not self.base_url.endswith("/api/v1"):
            self.base_url += "/api/v1"
        self.api_key = api_key
        self.timeout = timeout

    def request(self, path, method="GET", payload=None):
        url = self.base_url + "/" + path.lstrip("/")
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8")).get("error", str(exc))
            except (ValueError, AttributeError):
                detail = str(exc)
            raise AIOSAPIError(exc.code, detail) from exc
        if not body:
            return None
        return json.loads(body.decode("utf-8"))

    def health(self):
        return self.request("health")

    def identity(self):
        return self.request("me")

    def capabilities(self):
        return self.request("capabilities")

    def workflow_templates(self):
        return self.request("workflow-templates")

    def register_agent(self, name, *, kind=None, description="", capabilities=()):
        return self.request("agents", "POST", {
            "name": name,
            "kind": kind,
            "description": description,
            "capabilities": list(capabilities),
        })

    def propose_objective(self, title, *, description="", budget_usd=1.0):
        return self.request("objectives", "POST", {
            "title": title,
            "description": description,
            "budget_usd": budget_usd,
        })

    def list_tasks(self, *, agent_id=None):
        path = "tasks"
        if agent_id:
            path += "?" + urllib.parse.urlencode({"agent_id": agent_id})
        return self.request(path)

    def claim_task(self, task_id, *, agent_id=None):
        payload = {"agent_id": agent_id} if agent_id else {}
        return self.request(f"tasks/{task_id}/claim", "POST", payload)

    def report_task(self, task_id, *, status, result="", spent_usd=0.0):
        return self.request(f"tasks/{task_id}", "PATCH", {
            "status": status,
            "result": result,
            "spent_usd": spent_usd,
        })
