# Agent client libraries

AI OS provides small clients for agents that use either Python or JavaScript. Both use the same versioned JSON API, need no third-party packages, and leave model/provider choice to the worker.

## Python

Add `sdks/python` to `PYTHONPATH`, then:

```python
import os
from aios_sdk import AIOSClient

aios = AIOSClient(os.getenv("AIOS_URL", "http://localhost:8000"), os.environ["AIOS_AGENT_TOKEN"])
for task in aios.list_tasks():
    try:
        claimed = aios.claim_task(task["id"])
    except Exception:
        continue  # Another worker may have claimed it first.
    result = "Return the agent's completed result here."
    aios.report_task(claimed["id"], status="completed", result=result, spent_usd=0)
```

## JavaScript (Node 18+)

Import `sdks/javascript/index.js` directly or publish the package from this folder:

```js
import { AIOSClient } from "./sdks/javascript/index.js";

const aios = new AIOSClient({
  baseUrl: process.env.AIOS_URL || "http://localhost:8000",
  apiKey: process.env.AIOS_AGENT_TOKEN,
});
for (const task of await aios.listTasks()) {
  try {
    const claimed = await aios.claimTask(task.id);
    await aios.reportTask(claimed.id, {
      status: "completed", result: "Return the agent's completed result here.", spent_usd: 0,
    });
  } catch (error) {
    if (error.status !== 404 && error.status !== 409) throw error;
  }
}
```

Create an agent-bound key in **Connect & build** and store it in the worker's secret environment. Do not embed keys in browser code, source control, task descriptions, or model prompts. Both clients surface API failures as `AIOSAPIError` with an HTTP `status`. Agent keys only see eligible work, and the server enforces objective approvals and spending reservations. A worker must still use a real model/provider and report its actual cost; AI OS does not verify provider billing.
