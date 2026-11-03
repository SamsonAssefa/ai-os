# Contributing

1. Open an issue describing the change and its user impact.
2. Keep changes small and document API or permission changes.
3. Run `python -m unittest discover -s tests -v` before opening a pull request.
4. Never add credentials, production data, or actions that bypass approval and budgets.
5. New integrations should implement the adapter contract in `plugins/README.md` and request the least permissions needed.

Pull requests should explain behavior, tests, and security implications. Maintainers review changes before merge.
