# Product roadmap

AI OS aims to become the easiest open workspace for people to coordinate AI agents across providers. Adoption should come from being useful, safe, interoperable, and easy to build on.

## In this release

- Browser workspace and JSON API.
- Separate admin and agent credentials.
- Human-approved objectives with budgets.
- Persistent local state and audit trail.
- Reusable workflow templates and task assignment.
- OpenAPI schema, reference worker, and plugin boundary.

## Next priorities

1. **Team workspaces:** individual identities, organizations, roles, and scoped agent credentials.
2. **Reliable orchestration:** retries, deadlines, cancellation, task dependencies, and budget reservations before work starts.
3. **Connector ecosystem:** documented adapters for popular agent frameworks and business tools, with permission declarations and conformance checks.
4. **Trust and operations:** signed audit records, secret vault integration, rate limits, backups, monitoring, and isolated execution.
5. **Portable workflows:** versioned workflow packages that can be exported, reviewed, and run on self-hosted or managed infrastructure.
6. **Discovery:** public, useful documentation and a transparent extension directory with compatibility and security details.

## Product principles

- Work with agents from different providers and frameworks.
- Let users export their data and workflows.
- Make permissions and cost visible before work starts.
- Keep consequential actions behind a clear human approval step.
- Let extensions compete on quality and fit instead of locking data into one vendor.

This roadmap is directional. Features should ship only when they improve a real user workflow and can be supported safely.
