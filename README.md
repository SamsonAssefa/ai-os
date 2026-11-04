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

Start with the [user manual](docs/USER_GUIDE.md) and see the [product roadmap](docs/PRODUCT_ROADMAP.md). AI and search discovery files are documented in [AI_DISCOVERY.md](docs/AI_DISCOVERY.md); see the [OpenAPI schema](openapi.yaml), [API docs](docs/API.md), and the [`examples/agent.py`](examples/agent.py) worker. The example calls OpenAI using a key kept in the worker environment, then reports the model response and token-based cost. Configure its model and current pricing rates as described in the API docs.

## AI and search discovery

The project includes crawler-readable `llms.txt`, `robots.txt`, structured app metadata, a generated sitemap, and an OpenAPI schema. Public crawlers cannot index localhost. For website discovery, host the app on a public HTTPS domain and set `AIOS_PUBLIC_URL`; read [AI and search discovery](docs/AI_DISCOVERY.md).

## Included

- Workspace UI for agents, objectives, tasks, approvals, and capabilities.
- Human and agent API roles with separate bearer tokens.
- Persistent SQLite state, reusable workflow templates, agent-specific task routing, task claiming, result reporting, budget enforcement, and an audit activity view.
- Extension contract, API docs, CI, tests, contribution guide, and MIT license.

## Scope and safety

AI OS coordinates external agents; it does not bundle a model provider or run arbitrary plugins. Agent work only starts against a human-approved objective. Keep keys out of browser code and use a trusted network. Production deployments still need managed identity, rate limiting, encrypted secrets, database backups, and isolated execution.

## Test

`python3 -m unittest discover -s tests -v`

## License

MIT. See [LICENSE](LICENSE).
