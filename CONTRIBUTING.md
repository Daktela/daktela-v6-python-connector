# Contributing to Daktela Python SDK

Thank you for your interest in contributing!

## Development Setup

```bash
# Clone the repository
git clone https://github.com/Daktela/daktela-v6-python-connector.git
cd daktela-v6-python-connector

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"
```

## Running Tests

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ -v --cov=daktela --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_client.py -v
```

## Code Quality

```bash
# Type checking
mypy src/daktela --ignore-missing-imports

# Linting
ruff check src/

# Fix linting issues automatically
ruff check src/ --fix
```

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
