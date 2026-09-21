# Multimedia Tool API — FastAPI / uvicorn (no UI)
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /usr/local/bin/uv

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SERVE_UI=0 \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md requirements.txt ./
COPY src ./src

RUN uv venv /app/.venv \
    && uv pip install --python /app/.venv/bin/python --no-cache . \
    && mkdir -p /app/data /app/uploads/reference_assets /app/renders/cutscenes /app/renders/images

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "src.server:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
