# AI OS API v1

AI OS coordinates external agents over JSON. Base URL: `http://localhost:8000/api/v1`.

## Credentials and roles

Set `AIOS_ADMIN_TOKEN` for the human workspace and `AIOS_AGENT_TOKEN` for workers. Admins can propose/approve objectives, register agents, and queue work. Agents can register, view eligible tasks, claim a task, and report results. Keep tokens in environment variables. When neither token is configured, local development mode is open; agents identify themselves with `X-AI-OS-Role: agent`. Never expose open mode to a network you do not trust.

Set `AIOS_MAX_BUDGET_USD` for the maximum objective budget (default `$5`). State is stored in `aios.sqlite3`; set `AIOS_DB_PATH` to choose the database path.

- `GET /health` — service health/version.
- `GET /capabilities` — starter capability catalog.
- `GET|POST /agents` — list/register `{ "name": "Researcher", "kind": "custom", "capabilities": ["research"] }`.
- `GET|POST /objectives` — list/propose `{ "title": "...", "description": "...", "budget_usd": 1.25 }`.
- `PATCH /objectives/{id}/approve` — human admin approves a proposal.
- `GET|POST /tasks` — admins list tasks or queue `{ "objective_id": "...", "title": "..." }`. Task creation requires an approved objective.
- `POST /tasks/{id}/claim` — agent claims a queued task using `{ "agent_id": "..." }`.
- `PATCH /tasks/{id}` — claimed agent reports `{ "agent_id": "...", "status": "completed|failed", "result": "...", "spent_usd": 0.12 }`. Cumulative reported spend cannot exceed the objective budget.
- `GET /audit` — human admin audit trail.

Errors use `{ "error": "..." }`. Invalid JSON returns 400, invalid fields 422, missing auth 401, unknown IDs 404, and unapproved/claimed state conflicts 409.

## Run a worker

Start the server with `AIOS_ADMIN_TOKEN` and `AIOS_AGENT_TOKEN`. Register an agent in the UI, copy its ID, and run:

```sh
AIOS_URL=http://localhost:8000/api/v1 AIOS_AGENT_TOKEN=... AIOS_AGENT_ID=... python3 examples/agent.py
```

The example worker is a safe adapter skeleton. Add your model/tool call to `process_task(task)` and return `(result_text, measured_spend_usd)`. The worker does not fake successful output. See `../plugins/README.md` for extension rules.
