# AI OS

A starter workspace where people can register AI agents, organize objectives, queue tasks, and connect tools through a small JSON API.

## Run it

Requires Python 3.9+. From this folder, run `python3 server.py` and open [http://localhost:8000](http://localhost:8000). The workspace works with no dependencies. For API auth, set `AIOS_API_TOKEN`; set `AIOS_MAX_BUDGET_USD` to change the default $5 ceiling.

## Included

- Workspace UI for agents, objectives, tasks, and capabilities.
- JSON API that any agent framework can call.
- Agent registration and task result reporting.
- Budget validation, optional bearer-token authentication, approval-gated proposals, and an audit feed.
- API docs, extension contract, CI workflow, tests, contribution guide, and MIT license.

## Safety and scope

The MVP stores data in memory and does not execute agent actions. Objectives remain proposed until human review. Do not expose it to the public internet as-is. Production use needs persistent storage, scoped identity, rate limits, origin protection, secure secret storage, and isolated plugin execution.

## Test

`python3 -m unittest discover -s tests -v`

## Extend it

Implement an adapter using the contract in `plugins/README.md`. Keep permissions explicit and have adapters return proposals that the host can validate. See `docs/API.md` for the transport contract.

## License

MIT. See `LICENSE`.
