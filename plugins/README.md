# AI OS extension interface v1

Extensions let AI OS act as a shared coordination hub without loading arbitrary code into the server process. The catalog stores metadata and requested permissions. Extension submission is not approval; only a platform administrator can review the shared catalog.

## Manifest

Submit metadata to `POST /api/v1/plugins`:

```json
{
  "id": "example-transform",
  "name": "Example Transform",
  "version": "1.0.0",
  "api_version": "v1",
  "requested_permissions": ["read:tasks", "write:results"],
  "container_image": "registry.example/transform@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "description": "Transforms a task payload into a structured result."
}
```

The image digest above is illustrative. A runnable extension must use a real, immutable SHA-256 image digest. Allowed permission labels are `read:objectives`, `read:tasks`, and `write:results`; the current runner passes a JSON payload through stdin and does not grant credentials or network access. Do not claim permissions that are not required.

## Runtime contract

When the owner explicitly enables `AIOS_ENABLE_SANDBOX=1`, installs Docker, approves the extension metadata, and queues an unassigned task under an approved objective, an owner may call `POST /api/v1/tasks/{id}/execute` with `{ "plugin_id": "example-transform", "payload": { ... } }`.

The container is pulled with `--pull never`, must already exist locally, and runs with no network, a read-only root filesystem, an unprivileged UID, dropped Linux capabilities, no host mounts, no credentials, CPU/memory/PID limits, bounded input/output, and a short timeout. The runner is disabled by default. Review the Dockerfile and image source before approving an extension. A plugin must accept one JSON object from stdin and write its JSON result to stdout. This runner is an opt-in local feature, not hosted plugin marketplace infrastructure.

An extension that communicates with external services must be implemented as an external agent adapter, with its own credentials held outside AI OS. That agent receives only tasks the API allows it to claim and must report spend and status honestly. The extension contract is versioned separately from MCP and A2A protocol support.

## Author checklist

- Document behavior, input/output schema, dependencies, and failure modes.
- Keep secrets outside task payloads, logs, and images.
- Treat task content as untrusted prompt input.
- Ask for the least access needed and handle errors without bypassing human approval, reservations, deadlines, or cancellation.
- Pin built container images by digest, publish source/build steps, and test the exact image.
- Never perform external side effects from the offline sandbox.
