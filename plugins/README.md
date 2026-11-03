# Extension interface (draft v1)

Plugins are adapters, not privileged code inside the core. A future host can load a manifest with `name`, `version`, `api_version`, `requested_permissions`, and `entrypoint`. Each adapter exposes `plan(input) -> proposed_actions[]`; execution is outside this MVP.

Requirements: declare least-privilege permissions; return JSON-schema-valid data; never receive secrets by default; honor objective budget and cancellation; record an audit event for each proposal. The host must validate the manifest and require human approval before any consequential action. See `docs/API.md` for the stable transport contract.
