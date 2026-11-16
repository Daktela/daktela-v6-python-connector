# Contributing to Daktela Python SDK

Thank you for your interest in contributing!

## Development setup

```bash
# Clone the repository
git clone https://github.com/Daktela/daktela-v6-python-connector.git
cd daktela-v6-python-connector

# Build the development container
docker compose build sdk
```

## Running tests

```bash
# Run the complete suite with the enforced coverage gate
docker compose run --rm sdk pytest

# Run specific test file
docker compose run --rm sdk pytest tests/unit/test_client.py -v
```

## Code quality

```bash
# Type checking
docker compose run --rm sdk mypy src/daktela

# Linting
docker compose run --rm sdk ruff check src/ tests/ examples/

# Fix linting issues automatically
docker compose run --rm sdk ruff check src/ tests/ examples/ --fix

# Build and validate release artifacts
docker compose run --rm sdk python -m build
docker compose run --rm sdk twine check dist/*
```

## Live integration tests

`tests/integration` runs against a real instance and skips itself unless
`DAKTELA_URL` and `DAKTELA_ACCESS_TOKEN` are set. `DAKTELA_USERNAME` with
`DAKTELA_PASSWORD`, and `DAKTELA_RECORDING_ACTIVITY`, enable the login and
recording tests:

```bash
docker compose run --rm -e DAKTELA_URL -e DAKTELA_ACCESS_TOKEN sdk \
    pytest tests/integration --no-cov -rs
```

## Dependencies

`requirements-dev.txt` pins the development environment that the Docker image
and CI install as constraints. Dependabot proposes weekly updates for it and
for the workflow actions, which are pinned to commit SHAs. After changing the
dev extras in `pyproject.toml`, regenerate it from the image:

```bash
docker compose build sdk
docker compose run --rm sdk pip freeze --exclude-editable
```

Keep the comment header at the top of the file. The library itself declares
only lower bounds; CI also tests the minimum supported httpx version.

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Ensure tests pass and add new tests for new functionality
5. Run type checking and linting
6. Commit your changes (`git commit -m "Add my feature"`)
7. Push to your fork (`git push origin feature/my-feature`)
8. Open a Pull Request

## Code Style

- Follow PEP 8
- Use type hints for all public functions
- Write docstrings for public classes and methods
- Keep lines under 100 characters

## Reporting Issues

When reporting issues, please include:
- Python version
- SDK version
- Minimal code example to reproduce
- Full error traceback
