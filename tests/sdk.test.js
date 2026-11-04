import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { AIOSAPIError, AIOSClient } from "../sdks/javascript/index.js";

test("embedded workspace script parses as JavaScript", () => {
  const html = fs.readFileSync(new URL("../index.html", import.meta.url), "utf8");
  const script = html.match(/<script>([\s\S]*?)<\/script><\/html>/)?.[1];
  assert.ok(script, "workspace script exists");
  assert.doesNotThrow(() => new vm.Script(script));
  assert.match(html, /id="plannerSetupStatus"/);
  assert.match(html, /id="copyPlannerConfig"/);
  assert.doesNotMatch(html, /id="plannerApiKey"/);
});

test("normalizes the API URL, adds bearer auth, and lists tasks", async () => {
  let captured;
  const client = new AIOSClient({
    baseUrl: "http://localhost:8000/",
    apiKey: "secret",
    fetchImpl: async (url, options) => {
      captured = { url, options };
      return { ok: true, status: 200, json: async () => [] };
    },
  });
  assert.deepEqual(await client.listTasks("agent 1"), []);
  assert.equal(captured.url, "http://localhost:8000/api/v1/tasks?agent_id=agent%201");
  assert.equal(captured.options.headers.Authorization, "Bearer secret");
});

test("surfaces structured API errors", async () => {
  const client = new AIOSClient({
    fetchImpl: async () => ({ ok: false, status: 409, json: async () => ({ error: "task unavailable" }) }),
  });
  await assert.rejects(client.claimTask("task-1"), (error) => {
    assert.ok(error instanceof AIOSAPIError);
    assert.equal(error.status, 409);
    assert.equal(error.message, "task unavailable");
    return true;
  });
});

test("claim and report use the expected JSON methods", async () => {
  const calls = [];
  const client = new AIOSClient({ fetchImpl: async (url, options) => {
    calls.push({ url, options });
    return { ok: true, status: 200, json: async () => ({ id: "task-1" }) };
  } });
  await client.claimTask("task-1", "agent-1");
  await client.reportTask("task-1", { status: "completed", spent_usd: 0.1 });
  assert.equal(calls[0].options.method, "POST");
  assert.deepEqual(JSON.parse(calls[0].options.body), { agent_id: "agent-1" });
  assert.equal(calls[1].options.method, "PATCH");
});
