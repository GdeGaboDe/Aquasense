# Imagen de la aplicación AquaSense. La base de datos va en su propio contenedor (docker-compose.yml).
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Usuario sin privilegios: la app no necesita ser root dentro del contenedor.
RUN useradd --create-home --uid 10001 aquasense

# Primero las dependencias: si no cambian, Docker reutiliza esta capa y el build es rápido.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini ./
COPY app ./app
COPY migrations ./migrations
COPY tools ./tools
COPY web ./web

USER aquasense
EXPOSE 8000

# 127.0.0.1 debe estar en HOSTS_PERMITIDOS para que la revisión de salud no reciba un 400.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status != 200)"

# --proxy-headers confía solo en las IP de FORWARDED_ALLOW_IPS (la del contenedor de cloudflared).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
