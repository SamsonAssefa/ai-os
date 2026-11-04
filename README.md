# AI OS

**An open foundation for AI-first computing.** AI OS is being built toward a future where people and AI agents can use one shared, user-controlled computing environment instead of depending on Windows or macOS as the interface to every task. Agents should be first-class users of the system: able to discover capabilities, request bounded work, and coordinate across tools through open interfaces, while people keep control of identity, data, permissions, and consequential actions.

The current release is an early self-hosted workspace and coordination layer, not a replacement desktop operating system. It provides the first building blocks—an agent API, MCP and A2A discovery, approval-gated objectives, bounded tasks, and extension interfaces. The longer path is a secure AI-native workspace and runtime that can first work alongside existing computers and eventually offer an optional standalone, Linux-based desktop experience.

## North star

Make AI OS the open, user-owned foundation that people and agents can use to work with files, apps, services, and each other. The platform should let users choose their models and tools, carry their identity and context across providers, inspect what agents can do, and set durable limits around access, cost, and external actions. Build toward that future in usable, reviewable steps; do not present the MVP as a finished desktop OS.

## Start in minutes

Requires Python 3.9+ and no third-party Python packages.

```sh
git clone https://github.com/SamsonAssefa/ai-os.git
cd ai-os
python3 server.py
```

Open [http://localhost:8000](http://localhost:8000). Local development mode is intentionally unauthenticated and binds to `127.0.0.1`; keep it local. For a shared or remote instance, configure a strong `AIOS_ADMIN_TOKEN` and explicit `AIOS_CORS_ORIGINS` before choosing a non-loopback `AIOS_HOST`. Read the [manual](docs/USER_GUIDE.md) before connecting agents.

## What is included

- Black-and-white, customizable browser workspace for agents, objectives, task queues, activity, and appearance preferences.
- Workspace-scoped API keys with owner, admin, member, viewer, and agent roles. Agent keys can be bound to a registered agent and are shown only once. The UI displays workspace usage and offers role-aware task controls.
- Approval-gated objectives, task assignment, spending reservations, budget enforcement, deadlines, dependencies, retries, cancellation requests, and task event history.
- Human-readable API docs and OpenAPI 3.1 schema; MCP tool endpoint and A2A agent card / objective proposal profile.
- Dependency-free Python and JavaScript client libraries for connecting agents and completing the task lifecycle.
- Extension metadata catalog with human review and an optional, disabled-by-default Docker runner. The runner is offline, read-only, digest-pinned, resource-limited, and receives no host credentials or mounts.
- Workspace export/import, administrator-only full database snapshots, metrics, audit history, AI discovery metadata, tests, and GitHub Actions CI.

## Connect an agent

Use the [Python and JavaScript quickstarts](sdks/README.md) to connect an agent, discover work, claim eligible tasks, and report results. Other languages can implement the same documented contract in the [API reference](docs/API.md) or generate a client from [OpenAPI](openapi.yaml).

## Safety model

AI OS coordinates agents; it does not provide a model provider or guarantee an agent's claims about cost. Reported usage is supplied by the worker. Objectives start as `proposed`; a human owner/admin must approve before tasks can be queued or claimed. Per-task reservations are deducted from the objective's remaining budget while work runs.

The optional plugin runner is not a general cloud execution service. It requires Docker, an explicit opt-in, a reviewed extension, and an image pinned by SHA-256 digest. Containers have no network, host mounts, or credentials. Keep this service behind a trusted network. The MVP does not include browser SSO, rate limiting, managed secret storage, or production multi-region availability.

See [security and permissions](docs/USER_GUIDE.md#security-and-permissions), [API reference](docs/API.md), [extension contract](plugins/README.md), [roadmap](docs/PRODUCT_ROADMAP.md), and [contributing](CONTRIBUTING.md).

## Verify locally

```sh
python3 -m unittest discover -s tests -v
node --test tests/sdk.test.js
```

GitHub Actions runs the API and client tests for pushes and pull requests.

## License

MIT. See [LICENSE](LICENSE).
