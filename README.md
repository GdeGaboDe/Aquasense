# AquaSense

Plataforma web y base de datos para monitorear y controlar peceras con nodos ESP32. Proyecto de
Sistemas Embebidos (UAEMéx). La especificación completa está en [CLAUDE.md](CLAUDE.md).

Estado: **Fase 0** (base del proyecto, catálogos y `/health`).

## Requisitos

- Python 3.12
- Docker Desktop (para MySQL)

## Instalación

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows con Git Bash; en Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # y reemplaza cada CAMBIAR y SECRET_KEY
docker compose up -d --wait
alembic upgrade head
```

## Correr el servidor

```bash
uvicorn app.main:app --reload
```

Comprueba que funciona en <http://localhost:8000/health>. Debe responder
`{"estado":"ok","base_de_datos":"conectada"}`; si la base no contesta, responde `503`.

## Pruebas y calidad

```bash
ruff check .
ruff format --check .
pytest
pip-audit -r requirements.txt
```

Las pruebas de integración necesitan MySQL encendido y `TEST_DATABASE_URL`, cuya base debe terminar
en `_test` porque las pruebas borran sus tablas.

## Variables de entorno

Todas están descritas en [.env.example](.env.example).

## Estructura

```
app/         API, servicios, repositorios, modelos y esquemas
migrations/  Migraciones de Alembic
docker/      Script que crea las bases y los usuarios de MySQL
tests/       unit/ sin base; integration/ contra MySQL
```
