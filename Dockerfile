FROM node:24.20-bookworm-slim AS frontend-build

WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN NITRO_PRESET=node-server npm run build

FROM python:3.12-slim-bookworm AS backend-build

RUN python -m pip install --no-cache-dir uv
WORKDIR /src/backend
COPY backend/pyproject.toml backend/uv.lock ./
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
RUN uv sync --locked --no-dev --no-install-project

FROM python:3.12-slim-bookworm AS runtime

ENV PATH="/opt/venv/bin:/usr/local/bin:/usr/bin:/usr/sbin:/bin:/sbin" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend \
    FRESHFIRST_ENV=production \
    DATABASE_URL=sqlite:////data/freshfirst.db \
    PORT=8000

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates libatomic1 libstdc++6 passwd \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 freshfirst \
    && useradd --system --uid 10001 --gid freshfirst --home-dir /nonexistent --shell /usr/sbin/nologin freshfirst \
    && mkdir -p /app/backend /app/frontend /app/container /data \
    && chown 10001:10001 /data

COPY --from=frontend-build /usr/local/bin/node /usr/local/bin/node
COPY --from=backend-build /opt/venv /opt/venv
COPY --chown=root:root backend/app /app/backend/app
COPY --chown=root:root openapi.yaml /app/openapi.yaml
COPY --from=frontend-build --chown=root:root /src/frontend/.output /app/frontend/.output
COPY --chown=root:root container/ /app/container/

WORKDIR /app
USER 10001:10001

EXPOSE 8000
VOLUME ["/data"]
HEALTHCHECK --interval=15s --timeout=4s --start-period=45s --retries=5 \
    CMD ["node", "/app/container/healthcheck.mjs"]

ENTRYPOINT ["node", "/app/container/start.mjs"]
