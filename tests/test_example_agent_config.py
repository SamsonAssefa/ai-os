import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
EXAMPLE = os.path.join(ROOT, "examples", "agent.py")


class ExampleAgentConfigurationTests(unittest.TestCase):
    def run_with(self, **settings):
        env = {key: value for key, value in os.environ.items() if not key.startswith(("MODEL_", "OPENAI_", "AIOS_AGENT_"))}
        env.update({"AIOS_AGENT_TOKEN": "agent-secret", "AIOS_AGENT_ID": "agent-1"})
        env.update(settings)
        return subprocess.run([sys.executable, EXAMPLE], env=env, text=True, capture_output=True, timeout=5)

    def test_refuses_to_send_provider_key_to_remote_http_endpoint(self):
        result = self.run_with(
            MODEL_API_KEY="provider-secret",
            MODEL_BASE_URL="http://example.com/v1",
            MODEL_INPUT_USD_PER_MILLION_TOKENS="1",
            MODEL_OUTPUT_USD_PER_MILLION_TOKENS="1",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Use HTTPS for a remote model endpoint", result.stderr)
        self.assertNotIn("provider-secret", result.stderr)

    def test_requires_explicit_pricing_for_provider_agnostic_cost_reporting(self):
        result = self.run_with(MODEL_API_KEY="provider-secret", MODEL_BASE_URL="https://example.com/v1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MODEL_INPUT_USD_PER_MILLION_TOKENS", result.stderr)
        self.assertNotIn("provider-secret", result.stderr)


if __name__ == "__main__":
    unittest.main()
