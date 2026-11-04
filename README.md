# AI OS

An open-source workspace where people can connect agents, approve bounded work, and review results.

## Run locally

Requires Python 3.9+. Run `python3 server.py` and open [http://localhost:8000](http://localhost:8000). No packages are required. The workspace stores data in `aios.sqlite3`.

For local use, you may leave credentials unset. To separate human and agent access, start the server with `AIOS_ADMIN_TOKEN` and `AIOS_AGENT_TOKEN`. Put the admin token into the Connect page in the workspace tab. Never expose an open local development server to the public internet.

## A complete supervised task flow

1. Register an agent in the Agents page and copy its ID.
2. Propose an objective with a budget.
3. A human admin approves the objective.
4. Queue a task under that approved objective.
5. Connect an agent worker. It claims eligible tasks and reports a result and measured spend.
6. AI OS rejects reports that would exceed the approved objective budget and records state changes in the audit log.

See [API docs](docs/API.md) and the [`examples/agent.py`](examples/agent.py) adapter skeleton. The example calls OpenAI using a key kept in the worker environment, then reports the model response and token-based cost. Configure its model and current pricing rates as described in the API docs.

## Included

- Workspace UI for agents, objectives, tasks, approvals, and capabilities.
- Human and agent API roles with separate bearer tokens.
- Persistent SQLite state, task claiming, result reporting, budget enforcement, and audit records.
- Extension contract, API docs, CI, tests, contribution guide, and MIT license.

## Scope and safety

AI OS coordinates external agents; it does not bundle a model provider or run arbitrary plugins. Agent work only starts against a human-approved objective. Keep keys out of browser code and use a trusted network. Production deployments still need managed identity, rate limiting, encrypted secrets, database backups, and isolated execution.

## Test

`python3 -m unittest discover -s tests -v`

## License

MIT. See [LICENSE](LICENSE).
