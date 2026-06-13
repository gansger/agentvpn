FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system agentvpn \
    && useradd --system --gid agentvpn --home-dir /app agentvpn

COPY pyproject.toml README.md /app/
COPY apps /app/apps
COPY infrastructure /app/infrastructure
COPY alembic.ini /app/alembic.ini

RUN pip install --upgrade pip \
    && pip install .

USER agentvpn

CMD ["uvicorn", "apps.api.agentvpn_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
