# Contributing

Keep changes focused. Open an issue before starting a new storage backend, update transport, or
deployment system.

## Development

```bash
python -m venv .venv
. .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy
pytest --cov
python -m build
python -m twine check dist/*
```

Tests must use synthetic file names, identifiers, command results, and file content. Never submit
credentials, Telegram sessions, real chat or user IDs, OneDrive data, `rclone.conf`, server paths,
logs, or production configuration.

## Commits and changelog

Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):

```text
type(optional-scope): concise imperative summary
```

Add user-visible behavior, security, configuration, and compatibility changes under `Unreleased`
in [CHANGELOG.md](CHANGELOG.md). By contributing, you agree that your contribution is licensed under
the MIT License.
