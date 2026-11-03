# AI OS API v1

The same JSON API serves the web workspace and agents in any language. Base URL: `http://localhost:8000/api/v1`.

Set `AIOS_API_TOKEN` on the server to require `Authorization: Bearer <token>`. Unset means open local development access. Never embed a server token in a public client. Set `AIOS_MAX_BUDGET_USD` to change the per-objective ceiling (default $5).

- `GET /health` — service version and whether authentication is enabled.
- `GET /capabilities` — available starter capability catalog.
- `GET|POST /agents` — list or register `{ "name": "Researcher", "kind": "custom", "description": "...", "capabilities": ["research"] }`.
- `GET|POST /objectives` — list or propose `{ "title": "...", "description": "...", "budget_usd": 1.25 }`. Returns 201; status is `proposed` and approval is required.
- `GET|POST /tasks` — list or queue `{ "objective_id": "...", "title": "..." }`.
- `PATCH /tasks/{id}` — report `{ "status": "running|completed|failed", "result": "..." }`.
- `GET /audit` — in-memory event feed.

Errors use `{ "error": "..." }`. Invalid JSON returns 400, invalid fields 422, missing auth 401, unknown IDs 404. Responses are JSON. Data resets when the server restarts.

```sh
# Start the local workspace
AIOS_API_TOKEN=local-demo-token python3 server.py

# Register an agent
curl -H 'Authorization: Bearer local-demo-token' -H 'Content-Type: application/json' \
  -d '{"name":"My agent","kind":"custom","capabilities":["research"]}' \
  http://localhost:8000/api/v1/agents
```

This MVP coordinates proposals and task reports. It does not execute agents, store durable data, provide per-user identities, or safely host third-party plugins. See `../plugins/README.md` for the adapter boundary.
