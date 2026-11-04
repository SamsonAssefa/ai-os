import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import server


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class PlannerTests(unittest.TestCase):
    def test_parses_bounded_plan_and_strips_markdown_fence(self):
        content = '```json\n{"summary":"A short plan","tasks":[{"title":"Research","description":"Find sources"}]}\n```'
        self.assertEqual(server.parse_planner_content(content), {
            "summary": "A short plan",
            "tasks": [{"title": "Research", "description": "Find sources"}],
        })

    def test_rejects_empty_or_unbounded_task_list(self):
        with self.assertRaises(ValueError):
            server.parse_planner_content('{"tasks":[]}')
        tasks = [{"title": f"Step {i}"} for i in range(9)]
        with self.assertRaises(ValueError):
            server.parse_planner_content(json.dumps({"tasks": tasks}))

    @patch("server.urlrequest.urlopen")
    def test_calls_configured_openai_compatible_endpoint(self, open_url):
        open_url.return_value = FakeResponse({"choices": [{"message": {"content": '{"summary":"Plan","tasks":[{"title":"Step one","description":"Draft"}]}'}}]})
        with patch.object(server, "PLANNER_BASE_URL", "http://localhost:11434/v1"), \
             patch.object(server, "PLANNER_MODEL", "local-model"), \
             patch.object(server, "PLANNER_API_KEY", "private-key"):
            plan = server.create_plan("Write a brief", "Use public sources", 1.25)
        self.assertEqual(plan["tasks"][0]["title"], "Step one")
        self.assertTrue(plan["local_provider"])
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "http://localhost:11434/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer private-key")
        request_body = json.loads(request.data)
        self.assertLessEqual(request_body["max_tokens"], 1200)
        self.assertNotIn("private-key", json.dumps(request_body))


if __name__ == "__main__":
    unittest.main()
