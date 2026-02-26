# Contributing

## Development Setup

1. Create and activate a virtual environment.
2. Install development dependencies:

```bash
pip install -e ".[dev]"
```

3. Run local quality gates:

```bash
ruff check .
mypy openatoms
pytest -q
python -m build
```

## Pull Request Requirements

- Add or update tests for behavior changes.
- Keep exported IR and error contracts backward compatible, or document the version bump in `UPGRADE.md`.
- Update `CHANGELOG.md` with user-facing changes.
- Ensure examples remain executable.

## Commit Style

- Use clear, imperative commit messages.
- Keep changes scoped to one concern per commit where possible.
