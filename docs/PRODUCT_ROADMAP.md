# Product roadmap

AI OS is an open, self-hosted workspace for coordinating AI agents with people in control of scope and consequential actions. The goal is to make connections, permissions, and work portable across providers and frameworks.

## Available in v0.5.0

- Browser workspace with a black-and-white default, appearance customization, objective/task views, activity, team workspaces, scoped access keys, extension metadata catalog, live operations metrics, task reservations/dependencies/deadlines, and owner recovery controls.
- JSON API, OpenAPI reference, MCP tool profile, A2A agent discovery card, and a limited A2A objective-proposal profile.
- Human-approved objectives; task dependencies, deadlines, reservations, spend checks, retries, cancellation requests, event history, and per-agent assignment.
- Workspace export/import and bootstrap-admin full database snapshots.
- Optional local Docker runner for reviewed, digest-pinned extensions. It is disabled by default, offline, read-only, unprivileged, and resource limited.
- Worker example, user manual, AI discovery resources, tests, MIT license, and GitHub Actions CI.

## Next priorities

1. **Team identity:** SSO/OIDC, durable user sessions, invitations, and delegated organization roles.
2. **Reliable orchestration:** durable job queues, worker heartbeats, leases, idempotency, and recovery after server restarts.
3. **Connector ecosystem:** maintained adapters and conformance tests for common agent frameworks, models, and business tools.
4. **Trust and operations:** rate limits, encrypted secret storage, signed audit events, dependency and image scanning, backup retention, and operational monitoring.
5. **Portable workflows:** versioned workflow packages with reproducible inputs, permission manifests, compatibility checks, and migration support.
6. **Production readiness:** threat model, independent security review, performance testing, deployment guidance, and supported upgrade paths.

## Product principles

- Let agents built by different providers and frameworks interoperate.
- Let users export their data and move between self-hosted and managed options.
- Show permissions, budgets, and pending approvals before work begins.
- Keep consequential actions behind clear human review.
- Let integrations compete on quality and fit instead of locking data into one vendor.

This roadmap is directional. Features should ship only when they solve a real workflow and can be supported safely.
