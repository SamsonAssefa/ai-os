import io
import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdks", "python"))
from aios_sdk import AIOSAPIError, AIOSClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class ClientTests(unittest.TestCase):
    @patch("aios_sdk.client.urllib.request.urlopen")
    def test_identity_adds_bearer_and_normalizes_site_url(self, open_url):
        open_url.return_value = FakeResponse({"role": "agent"})
        client = AIOSClient("http://localhost:8000/", "secret")
        self.assertEqual(client.identity(), {"role": "agent"})
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "http://localhost:8000/api/v1/me")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")

    @patch("aios_sdk.client.urllib.request.urlopen")
    def test_claim_includes_bound_agent_identity_when_supplied(self, open_url):
        open_url.return_value = FakeResponse({"id": "task-1", "status": "running"})
        client = AIOSClient("http://localhost:8000/api/v1", "secret")
        self.assertEqual(client.claim_task("task-1", agent_id="agent-1")["status"], "running")
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "http://localhost:8000/api/v1/tasks/task-1/claim")
        self.assertEqual(json.loads(request.data), {"agent_id": "agent-1"})

    @patch("aios_sdk.client.urllib.request.urlopen")
    def test_http_errors_preserve_status_and_server_message(self, open_url):
        error = __import__("urllib.error", fromlist=["HTTPError"]).HTTPError(
            "http://localhost", 409, "Conflict", {}, io.BytesIO(b'{"error":"task unavailable"}')
        )
        open_url.side_effect = error
        with self.assertRaises(AIOSAPIError) as raised:
            AIOSClient().claim_task("task-1")
        self.assertEqual(raised.exception.status, 409)
        self.assertEqual(str(raised.exception), "task unavailable")


if __name__ == "__main__":
    unittest.main()
