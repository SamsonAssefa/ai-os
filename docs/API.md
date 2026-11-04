# AI OS API v1

Base URL: `http://localhost:8000/api/v1`. Send JSON with `Content-Type: application/json`. Authenticated routes accept `Authorization: Bearer <token>`. Full schema: [`openapi.yaml`](../openapi.yaml).

## Authentication and roles

Local development works without credentials only when both bootstrap token variables are unset; the server binds to loopback by default and refuses non-loopback binding without `AIOS_ADMIN_TOKEN`. Never expose this mode to a network.

Set `AIOS_ADMIN_TOKEN` for a bootstrap administrator and optionally `AIOS_AGENT_TOKEN` for a legacy shared worker token. For multi-workspace use, create workspaces and mint individual keys using the workspace/key routes. Dynamic agent keys are bound to one registered agent, can be revoked, and their raw value is returned once. Prefer those over the shared legacy agent token. Store credentials in a secret manager or process environment, never in public source or client-side application code.

| Role | Typical access |
|---|---|
| `admin` | Platform operations, create workspaces, global plugin review, full DB backup |
| `owner` | Manage a workspace, approve objectives, create scoped keys, export/import workspace |
| `member` | Register agents, propose objectives, queue tasks after approval |
| `viewer` | Read workspace records and audit history |
| `agent` | Propose objectives for human review; read eligible tasks, claim work, report results for its bound identity |

Workspace data is isolated by the credential's workspace. Admin keys minted for a workspace remain scoped to that workspace; the bootstrap `AIOS_ADMIN_TOKEN` controls the local workspace and platform-wide operations.

## Main workflow

1. `POST /objectives` with `{ "title": "...", "description": "...", "budget_usd": 2 }`. The status is `proposed`.
2. A human calls `PATCH /objectives/{id}/approve`.
3. `POST /tasks` with `{ "objective_id": "...", "title": "...", "description": "Task instructions", "reserve_usd": 0.5, "max_attempts": 3, "deadline_at": "2026-12-01T00:00:00Z", "depends_on": [] }`.
4. An agent calls `GET /tasks`, then `POST /tasks/{id}/claim` with `{ "agent_id": "..." }` (bound dynamic keys already carry their agent ID).
5. The claiming agent calls `PATCH /tasks/{id}` with `{ "status": "completed", "result": "...", "spent_usd": 0.23 }`.

The default per-objective budget cap is `$5.00`, configurable using `AIOS_MAX_BUDGET_USD`. A task's reservation is limited to remaining objective budget. Reported spend cannot exceed its reservation. Configure current model rates in your worker; AI OS does not verify provider invoices.

## Optional AI planner

Configure `AIOS_MODEL_BASE_URL` and `AIOS_MODEL_NAME` on the server to enable an OpenAI-compatible `/chat/completions` endpoint. The endpoint can be local; remote endpoints must use HTTPS. Keep an optional `AIOS_MODEL_API_KEY` in the server environment or secret manager. The key is never returned by the API or sent to the browser. The planner is disabled by default.

The browser requires explicit consent before sending the objective title and context to the configured model provider. `GET /planner/status` returns only provider host, model, and local/secure status. `POST /plan` is limited to workspace owners/admins and five calls per workspace/IP per minute. It returns a summary and 1–8 validated tasks with bounded text. The planner does not receive tools and cannot create records. The UI may include the draft in a proposed objective for review; owners still approve the objective and explicitly queue tasks. Planning-provider charges are separate from the objective budget and are not metered by AI OS.

## Routes

All paths below are relative to `/api/v1` unless noted.

| Method and path | Permission | Purpose |
|---|---|---|
| `GET /health` | Public | Liveness and version |
| `GET /planner/status`, `POST /plan` | Owner / admin for drafting | Check optional planner configuration or request a consent-gated task-plan draft |
| `GET /me` | Authenticated | Credential role, workspace, and available UI controls (no secret values) |
| `GET /capabilities`, `GET /workflow-templates` | Authenticated | Discover built-in workflow capabilities |
| `GET/POST /workspaces` | Admin / owner | List accessible workspaces or create one (new owner key shown once) |
| `GET/POST /api-keys`, `DELETE /api-keys/{id}` | Admin / owner | Create/list/revoke scoped keys (raw key shown once on creation) |
| `GET/POST /agents` | Member / owner / admin | Register and list agents |
| `GET/POST /objectives` | Authenticated read; member+ propose | List or propose bounded work |
| `PATCH /objectives/{id}/approve` | Owner / admin | Human approval gate |
| `GET/POST /tasks` | Authenticated read; member+ create | List tasks or queue under an approved objective |
| `GET /tasks/{id}`, `GET /tasks/{id}/events` | Authenticated | Inspect task and lifecycle history |
| `POST /tasks/{id}/claim` | Agent | Atomically claim available eligible work |
| `PATCH /tasks/{id}` | Agent that claimed it | Report completion, failure, or requested cancellation |
| `PATCH /tasks/{id}/cancel`, `PATCH /tasks/{id}/retry` | Owner / admin | Cancel or retry eligible work |
| `GET /audit`, `GET /metrics` | Viewer+ for audit; owner/admin for metrics | Review activity and workspace totals, including spent and reserved amounts |
| `GET/POST /export`, `POST /import` | Owner / admin | Export workspace data; import into an empty workspace with proposals reset for review and new record IDs |
| `GET/POST /backups` | Bootstrap admin only | List/create full-database snapshots |
| `GET/POST /plugins` | Authenticated read; owner/admin submit | Browse approved extensions or submit metadata for review |
| `PATCH /plugins/{id}` | Bootstrap admin only | Approve/reject shared catalog metadata |
| `POST /tasks/{id}/execute` | Owner / admin | Run an approved runnable extension in the opt-in isolated Docker runner |
| `GET /runner/status` | Owner / admin | Report runner readiness and restrictions |

## Agent interoperability

For application code, the [Python and JavaScript client quickstarts](../sdks/README.md) wrap identity, workflow discovery, task listing, claiming, and result reporting without extra dependencies.

- `POST /mcp` supports stateless MCP `2026-07-28` discovery and tool calls, plus the legacy `2025-11-25` initialize flow. Modern calls must include per-request metadata and matching `MCP-Protocol-Version`, `Mcp-Method`, and (for `tools/call`) `Mcp-Name` headers. HTTP origins are restricted to `AIOS_CORS_ORIGINS`; authenticated tool calls expose workflow discovery, eligible task listing, and objective proposals. Proposals still require human approval.
- `GET /.well-known/agent-card.json` publishes a discovery card.
- `POST /a2a` accepts the MVP `message/send` objective-proposal profile. Requests create a `proposed` objective; this endpoint is not a complete implementation of all A2A task lifecycle features.
- `GET /openapi.yaml`, `/llms.txt`, `/robots.txt`, and `/sitemap.xml` expose machine-readable API and discovery metadata. Set `AIOS_PUBLIC_URL` when serving a real public HTTPS origin so absolute discovery links are correct. This does not deploy the service.

## Server configuration

- `AIOS_HOST` (default `127.0.0.1`); non-loopback binding requires `AIOS_ADMIN_TOKEN`.
- `PORT` (default `8000`).
- `AIOS_ADMIN_TOKEN`, `AIOS_AGENT_TOKEN` (bootstrap and legacy shared bearer credentials).
- `AIOS_CORS_ORIGINS` (comma-separated exact origins; defaults to localhost and 127.0.0.1 on port 8000).
- `AIOS_DB_PATH` (SQLite file; default `aios.sqlite3` beside the app).
- `AIOS_MAX_BUDGET_USD` (maximum objective budget; default `5.00`).
- `AIOS_MODEL_BASE_URL`, `AIOS_MODEL_NAME`, optional `AIOS_MODEL_API_KEY` (optional OpenAI-compatible planner; disabled unless configured; remote URLs must use HTTPS).
- `AIOS_PLANNER_MAX_OUTPUT_TOKENS` (planner response limit; default `800`, bounded to `200`–`1200`).
- `AIOS_BACKUP_DIR` (snapshot destination; default `backups/`).
- `AIOS_ENABLE_SANDBOX=1` (explicit opt-in to Docker extension runner; default disabled).

Errors return JSON `{ "error": "..." }`; usual codes are 400 invalid JSON, 401 missing/invalid credentials, 403 forbidden, 404 unknown resource, 409 state conflict, 410 expired task, and 422 invalid fields.

## Example worker

See [`examples/agent.py`](../examples/agent.py). It uses a provider key from the worker process environment and reports its own token-based cost. Treat incoming task content as untrusted input and never send private data to a model without permission.
