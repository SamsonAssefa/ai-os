# Product roadmap

## North star: an open foundation for AI-first computing

AI OS aims to become a user-owned computing platform where people and AI agents work together, with agents treated as first-class users of the system. Over time it should provide the shared foundations for identity, context, tools, apps, files, permissions, and reliable execution, so an AI-native environment can stand on its own instead of relying on Windows or macOS as its primary interface.

The current product is an early self-hosted coordination workspace. It is not a desktop operating system yet. The intended path is to make the open agent workspace reliable first, grow it into an AI-native desktop experience that can run alongside existing systems, then explore an optional standalone Linux-based distribution. The system should stay model-neutral and portable, with people controlling data, access, spending, and external actions.

## Available in v0.9.0

- Browser workspace with a goal-centered AI workbench, template-based proposal preview, visible budget and permission boundaries, human approval prompts, black-and-white default, appearance customization, objective/task views, activity, team workspaces, scoped access keys, extension metadata catalog, live operations metrics, task reservations/dependencies/deadlines, and owner recovery controls. Optional consent-gated AI planning returns a bounded draft from a configured OpenAI-compatible model; drafts are never executed automatically.
- JSON API, OpenAPI reference, MCP tool profile, A2A agent discovery card, and a limited A2A objective-proposal profile.
- Human-approved objectives; task dependencies, deadlines, reservations, spend checks, retries, cancellation requests, event history, and per-agent assignment.
- Workspace export/import and bootstrap-admin full database snapshots.
- Optional local Docker runner for reviewed, digest-pinned extensions. It is disabled by default, offline, read-only, unprivileged, and resource limited.
- Worker example, user manual, AI discovery resources, tests, MIT license, and GitHub Actions CI.
- Dependency-free Python and JavaScript clients with shared agent quickstarts, common task operations, and API error handling.
- Guided model-provider setup in the UI with safe live status, copyable environment configuration, and no provider-secret entry in the browser.
- Provider-neutral OpenAI-compatible example worker with HTTPS enforcement for remote endpoints and support for existing OpenAI environment variable names.
- In-product integration directory clarifying which model, agent protocol, SDK, and extension paths are available today.

## Next priorities

1. **Team identity:** SSO/OIDC, durable user sessions, invitations, and delegated organization roles.
2. **Reliable orchestration:** durable job queues, worker heartbeats, leases, idempotency, and recovery after server restarts.
3. **Connector ecosystem:** maintained adapters and conformance tests for common agent frameworks, models, and business tools.
4. **Trust and operations:** rate limits, encrypted secret storage, signed audit events, dependency and image scanning, backup retention, and operational monitoring.
5. **Portable workflows:** versioned workflow packages with reproducible inputs, permission manifests, compatibility checks, and migration support.
6. **Production readiness:** threat model, independent security review, performance testing, deployment guidance, and supported upgrade paths.

## Longer-term stages

1. **Trusted agent foundation:** durable jobs, identity, scoped capabilities, policy enforcement, private context, and recoverable execution.
2. **AI-native workspace:** a human-friendly desktop shell for directing agents, reviewing their work, and connecting files, apps, and services through portable adapters.
3. **Standalone option:** investigate a bootable Linux-based AI OS distribution, with clear upgrade paths and support for running existing desktop applications where practical.

These stages are goals, not shipped features or date commitments. Each depends on reliability, security review, user testing, and a healthy connector ecosystem. AI OS should integrate with existing platforms before it tries to replace them.

## Product principles

- Let agents built by different providers and frameworks interoperate.
- Make the core model-neutral and the user's data, identity, preferences, and policies portable.
- Treat AI agents as first-class system users while giving each one visible, limited permissions.
- Let users export their data and move between self-hosted and managed options.
- Show permissions, budgets, and pending approvals before work begins.
- Keep consequential actions behind clear human review.
- Let integrations compete on quality and fit instead of locking data into one vendor.

This roadmap is directional. Features should ship only when they solve a real workflow and can be supported safely.
