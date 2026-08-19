FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    COVERAGE_FILE=/tmp/daktela-python-coverage

WORKDIR /workspace

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir -e ".[dev]"

COPY tests ./tests
COPY examples ./examples

CMD ["pytest"]
