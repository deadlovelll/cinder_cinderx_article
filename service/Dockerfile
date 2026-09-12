ARG PY_IMAGE=python:3.14-slim-bookworm

FROM ${PY_IMAGE} AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

FROM base AS deps

ARG DEP_EXTRA=c
ARG WITH_CINDERX=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-install-project --extra "${DEP_EXTRA}" \
 && if [ "${WITH_CINDERX}" = "1" ]; then uv sync --frozen --no-install-project \
        --extra "${DEP_EXTRA}" --extra runtime; fi

FROM base AS runtime

COPY --from=deps /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}" \
    VIRTUAL_ENV=/app/.venv

COPY src ./src
COPY gunicorn_conf.py ./

ARG DEP_EXTRA=c
ARG WITH_CINDERX=1
ENV RECSYS_DEP_EXTRA=${DEP_EXTRA} \
    RECSYS_WITH_CINDERX=${WITH_CINDERX} \
    PYTHONPATH=/app/src

RUN useradd --create-home --uid 10001 app && chown -R app /app
USER app

EXPOSE 8000

CMD ["gunicorn", "-c", "gunicorn_conf.py", "recsys.api.app:app"]
