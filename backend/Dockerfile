FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY backend/requirements.runtime.txt /tmp/requirements.runtime.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install -r /tmp/requirements.runtime.txt \
    && addgroup --system aleria \
    && adduser --system --ingroup aleria aleria \
    && mkdir -p /app/backend/data \
    && chown -R aleria:aleria /app

COPY --chown=aleria:aleria backend /app/backend
COPY --chown=aleria:aleria data /app/data
COPY --chown=aleria:aleria prompts /app/prompts
COPY --chown=aleria:aleria scripts /app/scripts

USER aleria

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=4 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()"

CMD ["sh", "-c", "python -m scripts.upgrade_schema && python -m scripts.ensure_demo_world && exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
