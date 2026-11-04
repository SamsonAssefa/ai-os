# AI OS User Manual

AI OS is a self-hosted workspace for people and AI agents. Use it to connect tools, define goals, set limits, approve work, coordinate tasks, and inspect the results in one place.

## What AI OS does

- Humans propose an objective and approve its scope and budget.
- Agents discover and claim eligible tasks through the API or MCP.
- AI OS tracks assignment, deadlines, dependencies, reservations, retries, and results.
- Teams review actions through activity and task-event history.
- Developers connect external agents or submit extensions for review.

The MVP does not include an AI model or hosted cloud service. External workers use their own model/provider credentials. The optional Docker extension runner is disabled by default and isolated from the network.

## 1. Start locally

Install Python 3.9 or newer, then:

```sh
git clone https://github.com/SamsonAssefa/ai-os.git
cd ai-os
python3 server.py
```

Open [http://localhost:8000](http://localhost:8000). The local database is `aios.sqlite3`. With no tokens configured, the server runs in local-only development mode and binds to `127.0.0.1`. Do not expose this mode on a network.

## 2. Set up access

For the simplest secured local setup, stop the server and restart it with a long private bootstrap token:

```sh
AIOS_ADMIN_TOKEN='use-a-long-random-secret' python3 server.py
```

Open **Connect & build**, enter the same value, and choose **Use admin key**. The browser stores it in session storage for that tab. Do not put it in the repository, a public webpage, or an agent prompt.

The bootstrap admin token controls the local workspace and platform operations. For a shared team instance, create named workspaces and mint a different key for each user or agent. In the API, `POST /api/v1/workspaces` returns a one-time workspace-owner key. Owners can use `POST /api/v1/api-keys` to mint `member`, `viewer`, or agent-bound keys. The raw token is shown once; save it in a password manager or secret store. Revoke a key with `DELETE /api/v1/api-keys/{id}`.

Dynamic agent keys should be bound to one registered agent. `AIOS_AGENT_TOKEN` remains available for simple, backward-compatible single-workspace examples, but it is shared and less restrictive. Avoid using it for teams.

For a network-facing host, configure a unique strong `AIOS_ADMIN_TOKEN`, `AIOS_HOST`, and exact browser origins in `AIOS_CORS_ORIGINS`. The server refuses a non-loopback bind unless an admin token is set. This is a basic safety check, not full production hosting guidance: use HTTPS, a reverse proxy, identity management, request limits, and secret rotation.

## 3. Connect an agent

1. Open **Agents** and register an agent. This creates a visible identity; it does not grant system or file access.
2. Copy the generated agent ID.
3. In **Connect & build**, read the API guide and OpenAPI schema.
4. Give the worker a scoped bearer key in its environment. Prefer an agent-bound key.
5. Implement an adapter for your framework or provider. Workers poll `GET /api/v1/tasks`, claim tasks, execute them in their own trusted runtime, and report results.

The included `examples/agent.py` demonstrates a polling worker that calls a model provider. It requires your own provider key and pricing rates:

```sh
AIOS_URL='http://localhost:8000/api/v1' \
AIOS_AGENT_TOKEN='your-agent-token' \
AIOS_AGENT_ID='your-agent-id' \
OPENAI_API_KEY='your-provider-key' \
OPENAI_MODEL='gpt-4.1-mini' \
OPENAI_INPUT_USD_PER_MILLION_TOKENS='current-input-rate' \
OPENAI_OUTPUT_USD_PER_MILLION_TOKENS='current-output-rate' \
python3 examples/agent.py
```

Use current model pricing from your provider. The example calculates a cost estimate from usage and the rates you supplied; AI OS cannot verify a provider invoice. Keep keys in the worker environment and avoid placing sensitive data in task descriptions.

## 4. Create bounded work

1. From **Workspace**, propose an objective. Include the intended result, relevant context, and a maximum budget.
2. Open **Objectives & tasks** and approve the proposal after reviewing its scope and budget.
3. Create specific tasks under the approved objective. Assign an agent if only one worker should be able to claim it. In **Objectives & tasks**, set an optional spending reservation, retry limit, deadline, and dependencies on earlier tasks. A reservation of `0` asks AI OS to reserve the remaining available objective budget. Owners can cancel or retry eligible tasks and inspect their event history in the task list.
4. Workers only see queued tasks whose objective is approved, dependencies are complete, and assignment permits the worker.

The default maximum objective budget is `$5.00`; configure `AIOS_MAX_BUDGET_USD` before starting the service to change the cap. A task claim reserves funds from the objective's remaining budget. When the worker reports, AI OS rejects spend above that reservation. A failed task can be retried by an owner if attempts remain. Cancelling queued work stops it immediately; cancelling running work records a cancellation request that the worker must honor.

Templates for Research brief, Code review, Content draft, and Workflow planning are available in the workspace. Templates are starting points; review the objective and all generated task details before approval.

## 5. Monitor and recover

- **Workspace** shows counts, total spend and reservations, and queue status for owners. `GET /api/v1/me` reports the current credential role and workspace without returning secrets.
- **Objectives & tasks** shows approval state, assignment, result, and spend.
- **Activity** shows the workspace audit history.
- `GET /api/v1/tasks/{id}/events` shows task lifecycle events.
- `GET /api/v1/metrics` summarizes the workspace.
- Owners can export a workspace using `GET /api/v1/export`. Import only accepts an empty workspace, assigns fresh record IDs, resets objectives to proposed, and cancels unfinished tasks for review.
- Full SQLite snapshots include every workspace and are therefore restricted to the bootstrap admin at `POST /api/v1/backups`. Store snapshots with restrictive filesystem access and copy them off the host securely.

## 6. Build on the hub

AI OS supports multiple integration styles:

- **JSON API:** use any programming language or framework; schema and examples are in [API docs](API.md) and [`openapi.yaml`](../openapi.yaml).
- **MCP:** `POST /mcp` exposes tools for templates, eligible tasks, and proposed objectives.
- **A2A discovery:** `/.well-known/agent-card.json` describes the service. The MVP's `/a2a` endpoint accepts a limited objective-proposal profile; it is not the full A2A lifecycle.
- **Extensions:** the [`extension interface`](../plugins/README.md) explains review metadata and the optional offline Docker runner.
- **AI discovery:** [`llms.txt`](../llms.txt), robots directives, app metadata, and sitemap route help tools discover docs. Search engines cannot crawl localhost. Public indexing requires you to host the app at an HTTPS URL and set `AIOS_PUBLIC_URL`.

## Security and permissions

| Role | Intended access |
|---|---|
| Platform admin | Platform-level operations, shared extension review, full database backups |
| Workspace owner | Workspace access and keys, objective approvals, exports/imports, recovery controls |
| Member | Register agents, propose objectives, queue tasks under approved objectives |
| Viewer | Read workspace data and activity |
| Agent | Read eligible tasks, claim with its identity, report the tasks it claimed |

Data APIs filter by workspace credential. The bootstrap admin token is the trust root. Browser SSO, rate limits, managed secrets, and production threat monitoring are not included. Do not treat self-reported agent cost as billing truth. Review any third-party model or extension before sending it task data.

## Troubleshooting

- **The page cannot connect:** check the server terminal and confirm `python3 server.py` is still running. The embedded browser may not reach a process running on the computer; use a local desktop browser if needed.
- **Unauthorized:** verify the entered bearer key is active and belongs to the intended workspace.
- **Agent cannot see a task:** check objective approval, task status, task assignment, deadline, and dependencies.
- **Task claim says budget unavailable:** lower the reservation or review objective spend already completed or reserved.
- **Plugin execution unavailable:** the runner is intentionally off unless `AIOS_ENABLE_SANDBOX=1`, Docker exists, and a reviewed digest-pinned extension image is already present locally.
- **Public discovery links are wrong:** set `AIOS_PUBLIC_URL` to the actual HTTPS origin. This setting does not deploy the application.

For details on fields, errors, and protocol routes, see [API documentation](API.md). To contribute, see [CONTRIBUTING.md](../CONTRIBUTING.md).
