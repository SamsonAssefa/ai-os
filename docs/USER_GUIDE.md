# AI OS User Manual

This guide helps you start AI OS, connect an agent, and run a task with human approval and a spending limit.

## What AI OS does

AI OS is a workspace and API for coordinating AI agents. People can register agents, set objectives, approve work, queue tasks, and review results. An agent does the work using its own model or tools, then sends the result back to AI OS.

AI OS does not provide an AI model, execute arbitrary plugins, or deploy changes on your behalf. The included worker is an example that connects to OpenAI.

## What you need

- Python 3.9 or newer.
- A terminal for starting the local server and agent worker.
- Optional: an OpenAI API key and an OpenAI account with API access to use the example worker.

## 1. Get and start AI OS

Download the project from [GitHub](https://github.com/SamsonAssefa/ai-os), or clone it:

```sh
git clone https://github.com/SamsonAssefa/ai-os.git
cd ai-os
python3 server.py
```

Open [http://localhost:8000](http://localhost:8000). Keep this terminal open while using AI OS. The database is saved in `aios.sqlite3` beside the server file.

For a first local trial, credentials may be left unset. This open mode is only for local use. Do not expose it to the internet.

## 2. Set up separate human and agent credentials

For a more controlled local setup, stop the server and restart it with separate credentials:

```sh
AIOS_ADMIN_TOKEN='choose-a-long-private-admin-token' \
AIOS_AGENT_TOKEN='choose-a-different-long-private-agent-token' \
python3 server.py
```

In the workspace, open **Connect & build**, enter the admin token, and choose **Use admin key**. It is kept in that browser tab's session storage. Do not share either token or put them in public source code.

The admin token is for the human workspace. The agent token is for worker programs. These credentials are shared by all administrators or agents in this MVP; there are no individual accounts or per-agent tokens yet.

## 3. Register an agent

1. Open **Agents**.
2. Enter a name, framework or type, capabilities, and a short description.
3. Select **Register agent**.
4. Copy the agent ID shown in the connected-agent list. The example worker needs this ID.

Registering an agent only lists it in AI OS. It does not grant access to your computer, files, or external services.

## 4. Propose and approve an objective

1. On **Workspace**, enter the outcome you want, relevant context, and a budget.
2. Select **Propose objective**. New objectives start as proposed.
3. Open **Objectives & tasks** and select **Approve objective** after reviewing its scope and budget.

The server rejects budgets above `AIOS_MAX_BUDGET_USD`, which defaults to $5. Change that environment variable before starting the server if a different cap is appropriate.

## 5. Queue a task

After approval, go to **Objectives & tasks**. Choose the approved objective, enter a specific task, and optionally assign it to one registered agent. Select **Queue task**. A task cannot be queued under an unapproved objective, and only the assigned agent can claim it.

You can also select a reusable Research brief, Code review, or Content draft template when proposing an objective. The template fills in a starting title, scope, and budget. Review and adjust those values before submission.

Write task descriptions as if they may be sent to an external AI service. Do not include passwords, API keys, private customer information, or other sensitive data.

## 6. Connect the example OpenAI worker

The example worker polls AI OS, claims queued tasks, sends the task title to OpenAI, then reports the result and calculated token cost.

Get the current per-token rates for the chosen model from OpenAI's pricing page, then start a second terminal in the project folder:

```sh
AIOS_URL='http://localhost:8000/api/v1' \
AIOS_AGENT_TOKEN='the-agent-token-from-step-2' \
AIOS_AGENT_ID='the-agent-id-from-step-3' \
OPENAI_API_KEY='your-openai-api-key' \
OPENAI_MODEL='gpt-4.1-mini' \
OPENAI_INPUT_USD_PER_MILLION_TOKENS='your-current-input-rate' \
OPENAI_OUTPUT_USD_PER_MILLION_TOKENS='your-current-output-rate' \
python3 examples/agent.py
```

Replace the example values with your own. Keep the API key and tokens private. The worker will only claim tasks attached to approved objectives. It reports token-based cost using the rates you enter; make sure those rates match the selected model and current provider pricing.

To use another model provider or an existing agent framework, write an adapter that calls AI OS's agent and task API. See [API documentation](API.md) and [plugin interface](../plugins/README.md).

## 7. Review results and spending

Return to **Objectives & tasks** and refresh the page to see task status, assignment, and result. Open **Activity** to review approval, claim, and completion events. The audit API is `GET /api/v1/audit` and is available to the admin credential. AI OS rejects a report if cumulative task spend would exceed the objective's budget.

Reported cost is based on the agent's submitted usage and configured rates. It is a guardrail, not a billing statement from the model provider.

## API quick reference

| Action | Endpoint | Access |
|---|---|---|
| Check service | `GET /api/v1/health` | Public |
| List capabilities | `GET /api/v1/capabilities` | Admin or agent |
| Register/list agents | `POST/GET /api/v1/agents` | Admin or agent |
| Propose/list objectives | `POST/GET /api/v1/objectives` | Admin |
| Approve objective | `PATCH /api/v1/objectives/{id}/approve` | Admin |
| Queue/list tasks | `POST/GET /api/v1/tasks` | Admin |
| List eligible tasks | `GET /api/v1/tasks` | Agent |
| Claim a task | `POST /api/v1/tasks/{id}/claim` | Agent |
| Report task result | `PATCH /api/v1/tasks/{id}` | Agent who claimed it |
| Read audit trail | `GET /api/v1/audit` | Admin |

See [API docs](API.md) for request bodies and responses.

## Troubleshooting

- **The page says it cannot connect:** Make sure `python3 server.py` is still running. In this desktop setup, open localhost in Chrome; the embedded in-app browser may not be able to reach local services.
- **Unauthorized:** Confirm the admin key in **Connect & build** matches `AIOS_ADMIN_TOKEN`, then reload the workspace.
- **Agent cannot see a task:** Confirm the objective is approved, the task is queued, and the worker has the correct agent token and ID.
- **Worker exits immediately:** Check that all required environment variables are set, including the OpenAI key and both pricing rates.
- **Budget rejected:** The configured rates or reported token use exceed the objective budget. Review the budget and provider usage before proposing more work.

## Current limitations

AI OS is an early MVP. It uses one shared admin token and one shared agent token, does not provide sign-in accounts, and does not isolate plugins. Keep it on a trusted network. Public or team hosting needs stronger identity and permission controls, rate limits, protected secret storage, backups, and security review.

## Findability and AI integrations

The repository includes a crawler-readable `llms.txt`, `robots.txt`, SoftwareApplication metadata, a generated sitemap route, and an OpenAPI schema. Public crawlers cannot index a localhost server. To make the web workspace discoverable, deploy it on a public HTTPS domain and set `AIOS_PUBLIC_URL` to that origin. Read [AI and search discovery](AI_DISCOVERY.md).
