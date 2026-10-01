FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.9.6 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, so code changes don't invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations migrations
COPY app app

RUN useradd --create-home --uid 1000 app
USER app


FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


FROM base AS importer
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends osmium-tool \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /app/data \
    && chown app /app/data
COPY etl etl
USER app
ENTRYPOINT ["python", "-m", "etl"]
CMD ["import"]
