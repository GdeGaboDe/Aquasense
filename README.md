# AquaSense

Plataforma web y base de datos para monitorear y controlar peceras con nodos ESP32. Proyecto de
Sistemas Embebidos (UAEMéx). La especificación completa está en [CLAUDE.md](CLAUDE.md) y el contrato
para el firmware en [docs/contrato-api.md](docs/contrato-api.md).

| Documento | Contenido |
|---|---|
| [docs/contrato-api.md](docs/contrato-api.md) | API del ESP32: telemetría, configuración, comandos y ACK |
| [docs/operacion.md](docs/operacion.md) | Dejar la laptop 24/7: arranque, túnel, firewall, respaldos |
| [docs/checklist-demo.md](docs/checklist-demo.md) | Qué revisar en el celular antes de cada demo |
| [docs/adr/](docs/adr/) | Decisiones de arquitectura (ADR-001 a ADR-006) |

**Disponible:** telemetría, alertas, comandos con confirmación, parámetros, umbrales, gráficas,
cambios de agua y predicción, con sus pantallas web y el simulador del ESP32. **Falta:** la imagen de
Docker para dejar todo listo para producción, y la verificación de las migraciones 0002 a 0004 en MySQL.

## Pantallas

| Pantalla | Qué hace |
|---|---|
| Panel general | Una tarjeta por tanque: valores actuales, estado de conexión y alertas activas |
| Detalle del tanque | Gráficas (6 h, 24 h, 7 días), predicción del cambio de agua y registro de cambios |
| Alertas | Activas e historial, con filtros por estado y tanque |
| Alimentación | "Dispensar ahora" con su estado en vivo, programa, bitácora de dosis y tolva |
| Ajustes | Umbrales, parámetros por nodo, control manual y alta de tanques y nodos |

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
python -m tools.crear_admin --usuario admin
```

## Correr el servidor

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1
```

Abre <http://localhost:8000>. Si otro programa ya usa el puerto 8000, en Windows ambos pueden quedar
escuchando sin ningún error: comprueba que `/health` responda
`{"estado":"ok","base_de_datos":"conectada"}` o cambia de puerto.

Todo host por el que se entre debe estar en `HOSTS_PERMITIDOS`, incluida la IP local que usa el ESP32
y la URL pública del túnel.

## Dar de alta un nodo

```bash
python -m tools.crear_nodo --mac 24:6F:28:AB:CD:EF --nombre Principal --tanque Betta --volumen-l 20 --usuario admin
```

El token del autónomo se muestra una sola vez. Para un satélite, agrega `--padre` con la MAC de su
autónomo.

## Simulador del ESP32

```bash
export AQUASENSE_TOKEN=token_del_autonomo
python tools/simulador_esp32.py --mac 24:6F:28:AB:CD:EF --satelite 24:6F:28:11:22:33=temp,turbidez,flotador,alarma
```

Con `--sin-red N` acumula N ciclos antes de reenviarlos, y con `--reinicio` cambia `boot`, para probar
la asignación de hora. `python tools/simulador_esp32.py --help` muestra todas las opciones.
**Sus datos quedan en la base:** no lo apuntes a la base con el historial real.

## Acceso público

Prueba rápida, sin cuenta, con una URL que cambia en cada reinicio:

```bash
cloudflared tunnel --url http://localhost:8000
```

Agrega el host que muestre a `HOSTS_PERMITIDOS` y reinicia el servidor. La configuración definitiva
está en la sección 14 de [CLAUDE.md](CLAUDE.md).

## Desarrollo sin Docker

Mientras no haya MySQL, se puede usar SQLite apuntando ambas URL a un archivo. Las variables de
entorno tienen prioridad sobre `.env`, y `*.db` está en `.gitignore`:

```bash
export DATABASE_URL=sqlite:///aquasense_dev.db MIGRACIONES_DATABASE_URL=sqlite:///aquasense_dev.db
alembic upgrade head
```

Las pruebas de integración también corren en SQLite con
`TEST_DATABASE_URL=sqlite:///ruta/aquasense_test`. SQLite sirve para desarrollar: la referencia sigue
siendo MySQL, que es lo que usa CI.

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
app/api/          Capa HTTP: valida, llama al servicio y responde
app/servicios/    Orquesta dominio y repositorios; maneja transacciones
app/dominio/      Reglas puras, sin framework ni base de datos
app/repositorios/ Consultas de SQLAlchemy
app/modelos/      Tablas
app/esquemas/     Contratos de entrada y salida
migrations/       Migraciones de Alembic
web/              Aplicación web
tools/            Simulador y altas por línea de comandos
docker/           Script que crea las bases y los usuarios de MySQL
tests/            unit/ sin base; integration/ contra MySQL
```
