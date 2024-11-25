LABEL maintainer="Luca Ferrario <lucaferrario199@gmail.com>"

# Build stage
FROM python:3.12.7-bullseye AS builder

ENV TZ=Europe/Rome \
    # Python's configuration:
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    # Poetry's configuration:
    POETRY_VERSION=1.8.4 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /builder

# Copy poetry files
COPY poetry.lock pyproject.toml /builder/

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 - --version $POETRY_VERSION
ENV PATH="/root/.local/bin:${PATH}"

RUN poetry env use 3.12 && poetry install --only main --no-root && rm -rf $POETRY_CACHE_DIR

# Runtime stage
FROM python:3.12.7-slim-bullseye AS runtime

# Create a non-root user
RUN useradd --create-home appuser

ARG AWS_DEFAULT_REGION
ARG AWS_ACCOUNT_ID

ENV VIRTUAL_ENV=/builder/.venv \
    PATH="/builder/.venv/bin:$PATH" \
    # NiceGUI settings
    NICEGUI_PORT=8080 \
    NICEGUI_HOST=0.0.0.0 \
    NICEGUI_STORAGE_PATH=/app/.nicegui \
    # AWS settings
    AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION} \
    AWS_ACCOUNT_ID=${AWS_ACCOUNT_ID} \
    AWS_NICEGUI_STORAGE_SECRET=all/nlp/stepfunctionmanager

# Copy virtual environment from builder
COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# Set working directory
WORKDIR /

# Copy application code
COPY app/ /app/
COPY assets/ /assets/
COPY configs/ /configs/

# Change ownership of the application files
RUN chown -R appuser:appuser /app /assets /configs

# Switch to non-root user
USER appuser

# Expose the port NiceGUI runs on
EXPOSE 8080

# Healthcheck to verify the server is running
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

# Set the entry point
CMD ["python", "/app/home.py"]