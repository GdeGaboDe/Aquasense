# CLAUDE.md — AquaSense (plataforma web y base de datos)

Este archivo es la fuente de verdad para Claude Code en este repositorio. Léelo completo antes de escribir código.
Idioma de trabajo: **español** (código de dominio, mensajes, documentación). Los términos técnicos del framework se quedan en inglés.

---

## 1. Qué es AquaSense

Sistema embebido para monitorear y controlar peceras. Nodos ESP32 miden la calidad del agua, actúan sobre la pecera
(alimentador, aireador, alarma) y envían todo a un servidor que guarda el historial, muestra una aplicación web y
estima cuándo toca el siguiente cambio de agua.

Proyecto académico (Sistemas Embebidos, UAEMéx). Equipo de 3 personas. **Entrega: 30 de noviembre de 2026.**

### 1.1 Alcance de ESTE repositorio

Solo lo que **no es circuito**:

- API para los nodos ESP32 (recibir telemetría, entregar configuración y comandos, recibir confirmaciones).
- Base de datos.
- Aplicación web para celular y escritorio.
- Predicción del cambio de agua.
- Simulador del ESP32 para desarrollar y probar sin hardware.

**Fuera de alcance:** el firmware del ESP32 y el protocolo ESP-NOW entre nodos. El firmware solo nos importa a través
del contrato de la sección 6, que es obligatorio para ambos lados.

### 1.2 Arquitectura física (contexto)

```
[Nodo satélite 1..n] ──ESP-NOW (radio, cada 10 s)──►
                                                    [Nodo autónomo / main] ──WiFi 2.4 GHz · HTTP · JSON──► Router
                                                                                                             │ red local
                                                                          Servidor: laptop ThinkPad ◄────────┘
                                                                          FastAPI + MySQL + cloudflared
                                                                                    │ túnel saliente (HTTPS)
                                                                                    ▼
                                               Cualquier navegador ◄── internet ── Cloudflare (URL pública)
```

- **El ESP32 habla con el servidor por la red local** (IP de la laptop). No pasa por el túnel: así el sistema sigue
  funcionando aunque se caiga internet, y el túnel no consume cuota con la telemetría.
- **Las personas usan la web por la URL pública** (HTTPS) desde cualquier lugar. El túnel sale desde la laptop hacia
  Cloudflare, así que no hace falta abrir puertos en el router.

- **Nodo autónomo (main):** uno por instalación. Es el **único** que habla con el servidor. Reenvía las lecturas de sus
  satélites y les retransmite comandos por ESP-NOW. Tiene internet a través del router.
- **Nodos satélite:** **modulares**. Cada cliente decide qué módulos lleva cada satélite; el máximo es el mismo
  conjunto de módulos que el autónomo. No se conectan a WiFi.
- **Operación sin red (fog computing):** si el servidor no responde, los nodos siguen operando con la última
  configuración guardada en NVS y almacenan lecturas en LittleFS para reenviarlas después. El servidor debe aceptar
  esos lotes atrasados sin duplicar datos.

### 1.3 Módulos posibles por nodo

| Código de módulo | Tipo | Variable(s) que reporta | Unidad |
|---|---|---|---|
| `temp` | Sensor (DS18B20, OneWire) | `temp_c` | °C |
| `tds` | Sensor (TDS V1.0, ADC) | `tds_ppm` | ppm |
| `turbidez` | Sensor (ADC con divisor) | `turbidez_ntu` | NTU |
| `flotador` | Sensor (digital) | `flotador_bajo` | booleano |
| `luz` | Sensor (LDR o BH1750) | `nivel_luz_adc`, `luz_clase` | ADC 0–4095 / 0,1,2 |
| `tolva` | Sensor (HC-SR04) | `distancia_tolva_cm`, `tolva_vacia` | cm / booleano |
| `servo` | Actuador (alimentador) | — (genera eventos de dosis) | — |
| `aireador` | Actuador (relevador) | `aireador_encendido` | booleano |
| `calentador` | Actuador opcional (relevador) | `calentador_encendido` | booleano |
| `alarma` | Actuador (LED + zumbador) | `alarma_activa` | booleano |
| `rtc` | Módulo opcional (DS3231) | — | — |

Ningún módulo es obligatorio en el código del servidor: **todo se descubre por lo que reporta cada nodo**.

---

## 2. Cómo debes trabajar (reglas para Claude Code)

Sigue la skill **buenas-practicas-desarrollo**. En concreto:

1. **Entiende antes de tocar.** Lee este archivo, `docs/contrato-api.md`, los ADRs y el código existente.
2. **Pregunta si algo es ambiguo** y la suposición sería cara de deshacer. Si es menor y reversible, decide, y escríbelo
   en el resumen del cambio.
3. **Trabaja por fases** (sección 13), en cambios pequeños que se puedan verificar uno a uno.
4. **Prueba de verdad.** Corre `ruff check`, `ruff format --check` y `pytest` antes de dar algo por terminado. Si una
   interfaz cambió, ábrela en el navegador (vista móvil) y revísala.
5. **No inventes** librerías, funciones ni versiones. Verifica que existan antes de usarlas. Al fijar versiones en
   `requirements.txt`, usa versiones reales y estables.
6. **Nunca** desactives o debilites pruebas para que pasen, ni hagas cambios destructivos (borrar datos, migraciones
   que eliminen columnas con datos, `push --force`) sin confirmación.
7. **No hagas commit ni push** a menos que el usuario lo pida.
8. **Informa con honestidad:** qué cambió, cómo se verificó y qué queda pendiente o riesgoso.
9. **YAGNI:** no agregues lo que no está en este documento. Si crees que algo falta, propónlo antes de hacerlo.

---

## 3. Stack

| Capa | Tecnología | Nota |
|---|---|---|
| Lenguaje | Python 3.12 | Type hints en todo el código |
| API | FastAPI + Uvicorn | Documentación OpenAPI automática en `/docs` |
| Validación | Pydantic v2 + pydantic-settings | Toda entrada externa pasa por un esquema |
| Acceso a datos | SQLAlchemy 2.0 (estilo 2.0, tipado) | Todo el SQL vive en `repositories/` |
| Migraciones | Alembic | **Nunca** cambios manuales a la base |
| Base de datos | MySQL 8 (contenedor Docker en desarrollo) | Driver PyMySQL. Cambiar de motor = cambiar `DATABASE_URL` |
| Contraseñas | `bcrypt` | |
| Sesión web | `SessionMiddleware` de Starlette (cookie firmada) | `HttpOnly`, `SameSite=Strict`, `Secure` configurable |
| Límite de intentos | `slowapi` | Solo en el login |
| Predicción | numpy | scikit-learn solo si se justifica |
| Frontend | HTML semántico + Tailwind (CDN) + JavaScript sin frameworks + Chart.js | Sin herramientas de compilación. Lo sirve el mismo FastAPI |
| Calidad | Ruff (lint + formato), pytest, pip-audit | |
| CI | GitHub Actions | Ruff + pytest con servicio MySQL |
| Publicación | Cloudflare Tunnel (`cloudflared`) en la laptop | URL pública con HTTPS sin abrir puertos (ADR-005) |

**Decisiones explícitas (ver ADRs):** no usar WebSockets ni MQTT (polling basta, ADR-003); no usar Node.js (ADR-001);
Tailwind por CDN es aceptable para este proyecto académico (ADR-006).

---

## 4. Estructura del repositorio

```
aquasense/
├─ app/
│  ├─ main.py               # crea la app, middlewares, monta routers y /web estático
│  ├─ config.py             # Settings desde .env (pydantic-settings); nada fijo en el código
│  ├─ db.py                 # engine y sesión de SQLAlchemy
│  ├─ api/                  # capa HTTP: valida → llama servicio → responde. Sin lógica de negocio
│  │  ├─ deps.py            #   dependencias: sesión BD, usuario actual, nodo por token
│  │  ├─ errores.py         #   formato de error único y manejadores
│  │  ├─ dispositivo.py     #   /api/v1/device/*
│  │  ├─ auth.py            #   /api/v1/auth/*
│  │  ├─ tanques.py, lecturas.py, alertas.py, comandos.py,
│  │  └─ configuracion.py, cambios_agua.py, prediccion.py, salud.py
│  ├─ dominio/              # lógica PURA: sin FastAPI, sin SQLAlchemy, sin reloj del sistema
│  │  ├─ tiempo.py          #   asignación de medido_en (sección 7.1)
│  │  ├─ alertas.py         #   evaluación de umbrales con histéresis
│  │  ├─ comandos.py        #   máquina de estados de comandos
│  │  ├─ parametros.py      #   validación de parámetros y reglas entre ellos
│  │  └─ prediccion.py      #   baseline + regresión del TDS
│  ├─ servicios/            # orquesta dominio + repositorios; maneja transacciones
│  ├─ repositorios/         # consultas SQLAlchemy
│  ├─ modelos/              # tablas SQLAlchemy
│  └─ esquemas/             # contratos Pydantic de entrada y salida
├─ migrations/              # Alembic
├─ web/                     # index.html, vistas, css/, js/
├─ tools/
│  ├─ simulador_esp32.py    # simula un autónomo con n satélites
│  ├─ crear_admin.py        # crea el usuario administrador
│  └─ crear_nodo.py         # da de alta un nodo y muestra su token UNA sola vez
├─ tests/
│  ├─ unit/                 # dominio/
│  └─ integration/          # API contra MySQL de prueba
├─ docs/
│  ├─ contrato-api.md       # contrato legible para quien programa el firmware
│  └─ adr/                  # decisiones de arquitectura
├─ docker-compose.yml       # solo MySQL
├─ .env.example
├─ requirements.txt         # versiones fijas
├─ requirements-dev.txt
├─ pyproject.toml           # configuración de Ruff y pytest
└─ README.md
```

**Regla de dependencias:** `api → servicios → (dominio, repositorios)`. `dominio/` no importa nada de las otras capas.
Las funciones de `dominio/` reciben la hora actual como parámetro (nunca llaman a `datetime.now()`), para poder probarlas.

---

## 5. Base de datos

Diseño normalizado a **3FN**. Todas las fechas en **UTC**, tipo `DATETIME(3)`. La web convierte a hora local
(`America/Mexico_City`). Restricciones en la propia base: FK, `NOT NULL`, `UNIQUE` y `CHECK`.

### 5.1 Tablas

**`usuario`** — cuentas de la web (un solo rol: administrador).
`id` PK · `usuario` UK · `hash_contrasena` · `creado_en` · `ultimo_acceso` NULL

**`tanque`** — cada pecera.
`id` PK · `nombre` UK · `volumen_l` DECIMAL · `especie` NULL · `notas` NULL

**`nodo`** — cada ESP32.
`id` PK · `mac` UK · `nombre` · `tanque_id` FK UK (un nodo por tanque) · `padre_id` FK→`nodo` NULL ·
`token_hash` UK NULL · `firmware` NULL · `boot_actual` INT NULL · `config_version` INT NOT NULL DEFAULT 1 ·
`config_version_aplicada` INT NULL · `ultimo_contacto` NULL · `activo` BOOL
- El **rol no se guarda**: con `padre_id` es satélite; sin él, autónomo.
- `CHECK`: un autónomo (`padre_id IS NULL`) tiene `token_hash`; un satélite no tiene token.
- `token_hash` = SHA-256 del token. El token en claro **nunca** se guarda.

**`variable`** — catálogo de lo que se puede medir.
`id` PK · `codigo` UK (`temp_c`, `tds_ppm`…) · `nombre` · `unidad` NULL · `tipo` ENUM(`numero`,`booleano`) ·
`min_fisico` NULL · `max_fisico` NULL

**`sensor`** — una variable que un nodo reporta. Se crea sola cuando el nodo anuncia sus módulos.
`id` PK · `nodo_id` FK · `variable_id` FK · `detectado_en` · `ultimo_visto` · UK(`nodo_id`,`variable_id`)

**`lectura`** — el historial.
PK(`sensor_id`, `medido_en`) · `valor` DECIMAL(10,3) · `recibido_en` · `origen_hora` ENUM(`servidor`,`ntp`,`desconocida`)
- La llave compuesta hace que los reenvíos desde LittleFS no se dupliquen.
- Las lecturas con `origen_hora = desconocida` se guardan pero **se excluyen** de gráficas por defecto y de la predicción.

**`umbral`** — rangos aceptables por tanque.
PK(`tanque_id`, `variable_id`) · `minimo` NULL · `maximo` NULL · `histeresis` DECIMAL · `CHECK(minimo < maximo)`

**`tipo_alerta`** — catálogo.
`id` PK · `codigo` UK (`FUERA_DE_RANGO`, `NIVEL_BAJO`, `TOLVA_VACIA`, `COMANDO_FALLIDO`…) · `descripcion` · `severidad` ENUM(`info`,`advertencia`,`critica`)

**`alerta`**
`id` PK · `tanque_id` FK · `nodo_id` FK NULL · `tipo_alerta_id` FK · `variable_id` FK NULL · `valor` NULL ·
`iniciada_en` · `resuelta_en` NULL (NULL = activa)
- Solo puede haber **una alerta activa** por (`tanque_id`, `tipo_alerta_id`, `variable_id`).

**`parametro`** — catálogo de parámetros configurables desde la web.
`id` PK · `codigo` UK · `descripcion` · `tipo` ENUM(`entero`,`decimal`,`opcion`) · `unidad` NULL · `minimo` NULL ·
`maximo` NULL · `opciones` NULL · `valor_defecto` · `modulo_requerido` NULL

**`valor_parametro`** — valor actual de cada parámetro por nodo.
PK(`nodo_id`, `parametro_id`) · `valor` · `modificado_en` · `modificado_por` FK→`usuario`
- Cada cambio incrementa `nodo.config_version`, en la **misma transacción**.

**`comando`**
`id` PK · `nodo_id` FK · `tipo` ENUM(`DISPENSAR`,`SILENCIAR_ALARMA`,`AIREADOR`) · `argumento` INT NULL ·
`estado` ENUM(`pendiente`,`entregado`,`confirmado`,`fallido`,`expirado`) · `creado_por` FK→`usuario` ·
`creado_en` · `expira_en` · `entregado_en` NULL · `resuelto_en` NULL · `detalle` NULL

**`dosis`** — bitácora de alimentación (incluye las automáticas y las del botón físico).
`id` PK · `nodo_id` FK · `cargas` · `origen` ENUM(`remoto`,`automatico`,`local`) · `dosificada_en` ·
`comando_id` FK UK NULL · UK(`nodo_id`,`dosificada_en`)
- El tanque se obtiene a través del nodo (no se duplica).

**`cambio_agua`**
`id` PK · `tanque_id` FK · `realizado_en` · `porcentaje` · `registrado_por` FK→`usuario`
- Al dar de alta un tanque se registra automáticamente un cambio inicial (el llenado).

**`prediccion`**
`id` PK · `cambio_agua_id` FK · `generada_en` · `modelo_version` · `pendiente` · `intercepto` · `limite_tds` ·
`r2` NULL · `n_muestras` · `baseline_dias` NULL
- Los días restantes **no se guardan**: se calculan a partir de la fila (evita dependencia transitiva).

### 5.2 Índices adicionales

- `alerta(tanque_id, resuelta_en)`
- `comando(nodo_id, estado)`
- `dosis(nodo_id, dosificada_en)`

### 5.3 Datos iniciales (migración de datos)

- Catálogo `variable` con las variables de la sección 1.3.
- Catálogo `tipo_alerta`.
- Catálogo `parametro` con los parámetros de la sección 8.3.

---

## 6. Contrato con el ESP32 (obligatorio)

Base: `/api/v1/device`. Autenticación: header `X-API-Token` del **nodo autónomo**. Solo JSON.
Cadencias: telemetría cada **10 s**; consulta de configuración cada **5 s**.

### 6.1 `POST /api/v1/device/telemetry`

```json
{
  "lote": 1842,
  "enviado_epoch_ms": 1793750400000,
  "nodos": [
    {
      "mac": "24:6F:28:AB:CD:EF",
      "firmware": "1.2.0",
      "boot": 7,
      "modulos": ["temp", "tds", "turbidez", "flotador", "luz", "tolva", "servo", "aireador", "alarma"],
      "config_version_aplicada": 4
    },
    {
      "mac": "24:6F:28:11:22:33",
      "firmware": "1.2.0",
      "boot": 3,
      "modulos": ["temp", "turbidez", "flotador", "alarma"],
      "config_version_aplicada": 2
    }
  ],
  "lecturas": [
    { "mac": "24:6F:28:AB:CD:EF", "variable": "temp_c",    "valor": 25.4,  "edad_ms": 1200, "boot": 7, "epoch_ms": null },
    { "mac": "24:6F:28:AB:CD:EF", "variable": "tds_ppm",   "valor": 182.0, "edad_ms": 1200, "boot": 7, "epoch_ms": null },
    { "mac": "24:6F:28:11:22:33", "variable": "flotador_bajo", "valor": 0, "edad_ms": 4300, "boot": 7, "epoch_ms": null }
  ],
  "eventos": [
    { "mac": "24:6F:28:AB:CD:EF", "tipo": "dosis", "cargas": 2, "origen": "automatico", "comando_id": null,
      "edad_ms": 30000, "boot": 7, "epoch_ms": null }
  ]
}
```

Reglas:
- `edad_ms`: cuántos milisegundos antes del envío se midió el dato, **calculado por el autónomo con su propio reloj**
  (para lecturas de satélites, desde que las recibió por ESP-NOW). `boot`: contador de arranques del **autónomo** en el
  momento de la medición.
- `epoch_ms`: hora Unix si el autónomo tenía NTP sincronizado al medir; si no, `null`.
- `nodos`: el autónomo lo manda en **cada** lote. El servidor crea o marca `sensor` según `modulos` (autodescubrimiento)
  y actualiza `firmware`, `boot_actual`, `config_version_aplicada` y `ultimo_contacto`.
- Los booleanos viajan como `0`/`1`.
- Lecturas de MAC no registradas, de nodos que no pertenecen a este autónomo, de variables desconocidas o fuera del
  rango físico se **rechazan individualmente**; el resto del lote se guarda.

Respuesta `200`:
```json
{ "aceptadas": 41, "duplicadas": 3, "rechazadas": [ { "indice": 7, "motivo": "MAC_NO_REGISTRADA" } ] }
```

### 6.2 `GET /api/v1/device/config`

Respuesta `200`:
```json
{
  "servidor_epoch_ms": 1793750400123,
  "nodos": [
    { "mac": "24:6F:28:AB:CD:EF", "config_version": 5,
      "parametros": { "MODO_DISPENSA": "AUTOMATICO", "INTERVALO_ALIMENTACION_HORAS": 8, "CANTIDAD_CARGAS": 2 } },
    { "mac": "24:6F:28:11:22:33", "config_version": 2, "parametros": { "FRECUENCIA_ALARMA_BUZZER": 2500 } }
  ],
  "comandos": [
    { "id": 912, "mac": "24:6F:28:AB:CD:EF", "tipo": "DISPENSAR", "argumento": 2 }
  ]
}
```
- Incluye al autónomo y a sus satélites. El autónomo retransmite por ESP-NOW lo que corresponde a cada satélite.
- Solo se incluyen los parámetros cuyo `modulo_requerido` tiene el nodo.
- `servidor_epoch_ms` permite al nodo ajustar su hora si no tiene NTP.
- Al entregar un comando, pasa de `pendiente` a `entregado`.

### 6.3 `POST /api/v1/device/ack`

```json
{ "comando_id": 912, "resultado": "confirmado", "detalle": null }
```
`resultado`: `confirmado` | `fallido`. Repetir el mismo ACK no cambia nada (idempotente).
Un ACK de un comando que no pertenece a los nodos de este token responde `403`.

### 6.4 Errores del contrato

| Código | Cuándo |
|---|---|
| 401 | Falta el token o no es válido |
| 403 | El token es válido pero el recurso no le pertenece |
| 422 | El JSON no cumple el esquema |
| 429 | Demasiadas peticiones |

Formato único: `{"error": {"code": "TOKEN_INVALIDO", "message": "…", "details": null}}`.

---

## 7. Reglas de negocio (`app/dominio/`)

### 7.1 Hora de cada lectura (la pone el servidor)

Para cada lectura o evento, con `recibido_en` = hora UTC del servidor al recibir el lote:

1. Si `boot` de la lectura **es igual** al `boot` actual del autónomo en ese lote:
   `medido_en = recibido_en − edad_ms` y `origen_hora = servidor`.
2. Si no (la lectura viene de un arranque anterior, reenviada desde LittleFS) y tiene `epoch_ms`:
   `medido_en = epoch_ms` y `origen_hora = ntp`.
3. Si no hay ninguna de las dos: `medido_en = recibido_en` y `origen_hora = desconocida`.

Además: descarta `epoch_ms` que esté en el futuro (más de 60 s adelante del servidor) o antes de 2026-01-01; en ese caso
aplica el paso 3. Redondea `medido_en` a milisegundos.

### 7.2 Alertas

- Se evalúan **al recibir** cada lectura, en el servicio de ingesta.
- Variables numéricas: alerta `FUERA_DE_RANGO` si `valor < minimo` o `valor > maximo` del umbral del tanque.
  Se resuelve cuando el valor regresa a `[minimo + histeresis, maximo − histeresis]`.
- `flotador_bajo = 1` → `NIVEL_BAJO`. `tolva_vacia = 1` → `TOLVA_VACIA`. Se resuelven al volver a `0`.
- Nunca dos alertas activas iguales (mismo tanque, tipo y variable).
- Un comando `fallido` o `expirado` genera `COMANDO_FALLIDO`.
- **Nodo sin reportar:** si `ultimo_contacto` es más antiguo que 3 veces la cadencia (30 s), el estado del tanque se
  muestra como "sin conexión". Se calcula **al consultar**; no hay tareas en segundo plano.

### 7.3 Comandos

Estados: `pendiente → entregado → confirmado | fallido`; `pendiente → expirado`.

- Un comando `pendiente` expira 120 s después de creado si no se entregó.
- Un comando `entregado` sin ACK en 60 s se muestra como "sin confirmar" en la web, pero **no se reenvía**.
- **Seguridad:** un `DISPENSAR` nunca se reenvía automáticamente. Mejor no dispensar que dar doble ración.
- Solo un `DISPENSAR` activo (`pendiente` o `entregado`) por nodo a la vez; otro intento responde `409`.
- Al confirmar un `DISPENSAR`, se espera el evento `dosis` con ese `comando_id`; si llega, se liga.

| Tipo | Argumento | Requiere módulo |
|---|---|---|
| `DISPENSAR` | cargas, 1–5 | `servo` |
| `SILENCIAR_ALARMA` | minutos, 1–60 | `alarma` |
| `AIREADOR` | 0 = apagar, 1 = encender | `aireador` |

### 7.4 Parámetros

Validación en servidor con el catálogo `parametro` (tipo, rango, opciones) y estas reglas entre parámetros:

- `UMBRAL_LUZ_OSCURIDAD < UMBRAL_LUZ_MODERADA`
- `ANGULO_REPOSO_SERVO < ANGULO_DISPENSA_SERVO`
- `TEMP_ENCENDER_CALENTADOR < TEMP_APAGAR_CALENTADOR` (solo si el nodo tiene `calentador`)

Un parámetro solo se puede asignar a un nodo que tenga su `modulo_requerido`.

### 7.5 Predicción del cambio de agua

- Serie: lecturas de `tds_ppm` del tanque desde el último `cambio_agua`, solo con `origen_hora` `servidor` o `ntp`.
- **Baseline:** duración promedio de los ciclos anteriores completos.
- **Modelo:** regresión lineal de TDS contra tiempo (horas). Días restantes = momento en que la recta cruza
  `umbral.maximo` de `tds_ppm` del tanque, menos ahora.
- **Mínimos para estimar:** 24 h de datos y 50 muestras. Si no se cumple, o la pendiente es ≤ 0, responde
  "estimación aún no confiable" y el baseline si existe. **Nunca** inventes un número.
- **Evaluación sin fuga de datos:** división cronológica por ciclos (entrenar con ciclos viejos, evaluar con el último);
  nunca aleatoria. Métrica: MAE en días, comparada contra el baseline.
- Se guarda una fila en `prediccion` como máximo una vez por hora por ciclo, con `modelo_version`.

---

## 8. API para la aplicación web

Base: `/api/v1`. Autenticación por cookie de sesión. Todas las rutas (salvo login y `/health`) requieren sesión.

### 8.1 Rutas

| Método y ruta | Uso |
|---|---|
| `POST /auth/login` · `POST /auth/logout` · `GET /auth/yo` | Sesión. Login con límite de 5 intentos por minuto por IP |
| `GET /tanques` | Lista con estado actual: últimas lecturas, alertas activas, "sin conexión" |
| `POST /tanques` · `PATCH /tanques/{id}` | Alta y edición (el alta registra el cambio de agua inicial) |
| `GET /tanques/{id}/lecturas?variable=&desde=&hasta=&intervalo=` | Serie para gráficas, **agregada en el servidor** (promedio por intervalo: 1m, 5m, 1h). Máximo 2,000 puntos |
| `GET /alertas?activa=&tanque_id=&pagina=&tamano=` | Paginado, máximo 100 por página |
| `POST /comandos` · `GET /comandos?nodo_id=&pagina=` | Crear y consultar comandos |
| `GET /nodos/{id}/parametros` · `PUT /nodos/{id}/parametros` | Configuración (valida y sube `config_version`) |
| `GET /tanques/{id}/umbrales` · `PUT /tanques/{id}/umbrales` | Umbrales |
| `GET /tanques/{id}/dosis?pagina=` | Bitácora de alimentación |
| `POST /tanques/{id}/cambios-agua` · `GET /tanques/{id}/cambios-agua` | Cambios de agua |
| `GET /tanques/{id}/prediccion` | Días estimados, baseline, confianza |
| `POST /nodos` (devuelve el token una sola vez) · `PATCH /nodos/{id}` | Alta de autónomos y satélites |
| `GET /health` | Estado del servidor y de la base, sin sesión |

### 8.2 Convenciones

- Códigos: 200, 201, 204, 400, 401, 403, 404, 409, 422, 429. Formato de error único (sección 6.4).
- Toda lista paginada con límite máximo.
- Todas las fechas en ISO 8601 UTC (`2026-11-20T15:04:05.123Z`).

### 8.3 Catálogo inicial de parámetros

| Código | Tipo | Rango | Defecto | Módulo |
|---|---|---|---|---|
| `INTERVALO_ENVIO_S` | entero | 5–60 | 10 | — |
| `MODO_DISPENSA` | opción | MANUAL, AUTOMATICO | MANUAL | servo |
| `INTERVALO_ALIMENTACION_HORAS` | entero | 1–24 | 8 | servo |
| `CANTIDAD_CARGAS` | entero | 1–5 | 1 | servo |
| `TIEMPO_APERTURA_DISPENSA` | entero (ms) | 200–2000 | 500 | servo |
| `ANGULO_REPOSO_SERVO` | entero (°) | 0–30 | 10 | servo |
| `ANGULO_DISPENSA_SERVO` | entero (°) | 45–90 | 75 | servo |
| `DISTANCIA_TOLVA_VACIA` | decimal (cm) | 5.0–30.0 | 15.0 | tolva |
| `UMBRAL_LUZ_OSCURIDAD` | entero (ADC) | 0–1500 | 1000 | luz |
| `UMBRAL_LUZ_MODERADA` | entero (ADC) | 1501–3000 | 2500 | luz |
| `COEF_CALIBRACION_TDS` | decimal | 0.80–1.20 | 1.00 | tds |
| `VOLTAJE_REFERENCIA_ADC` | decimal (V) | 3.20–3.35 | 3.30 | — |
| `FRECUENCIA_ALARMA_BUZZER` | entero (Hz) | 1000–4000 | 2500 | alarma |
| `TEMP_ENCENDER_CALENTADOR` | decimal (°C) | 18–30 | 24.5 | calentador |
| `TEMP_APAGAR_CALENTADOR` | decimal (°C) | 18–30 | 25.5 | calentador |

---

## 9. Aplicación web (`web/`)

### 9.1 Pantallas

| Pantalla | Contenido |
|---|---|
| Login | Usuario y contraseña |
| **Monitoreo** — Panel general | Una tarjeta por tanque: valores actuales de los módulos que tiene, estado (texto + color + ícono), hora del último dato, alertas activas, "sin conexión" |
| **Monitoreo** — Detalle del tanque | Gráfica por variable con selector de rango (6 h, 24 h, 7 días), predicción de cambio de agua, botón "Registrar cambio de agua" |
| **Monitoreo** — Alertas | Activas e historial |
| **Configuración** — Alimentación | "Dispensar ahora" (1–5 cargas) con estado del comando en vivo, modo, intervalo, cargas, bitácora de dosis, estado de la tolva |
| **Configuración** — Ajustes | Umbrales por tanque, parámetros por nodo (solo los de sus módulos), "pendiente de aplicar" si `config_version_aplicada < config_version`, alta de nodos |

Solo se muestran los controles de los módulos que el nodo reporta (satélites modulares).

### 9.2 Reglas

- **Mobile-first:** la demo es en celular. Probar también en escritorio.
- **Accesibilidad WCAG 2.2 AA:** `lang="es"`, un `h1` por página, `label` en todo campo, contraste ≥ 4.5:1, foco
  visible, todo operable con teclado, el estado **nunca solo por color**.
- **Estados de carga, vacío y error** en cada vista que pide datos.
- **XSS:** los datos se pintan con `textContent` o creando nodos; **nunca** `innerHTML` con datos del servidor.
- **Content-Security-Policy** que solo permita el propio origen y los CDN usados.
- Validación en el formulario para la experiencia de usuario y **siempre** también en el servidor.
- Polling cada 10 s en el panel, cada 3 s solo mientras un comando está en curso y cada 60 s en gráficas. **Se pausa**
  cuando la pestaña no está visible (`document.visibilityState`). Los intervalos vienen de la configuración del
  servidor, no fijos en el JS: con la web pública, cada pestaña abierta en cualquier lugar genera tráfico.
- Todas las URL del frontend son relativas (`/api/v1/...`): la misma web funciona por la IP local y por la URL pública.
- `js/api.js`: un solo envoltorio de `fetch` que maneja el formato de error y redirige al login con 401.
- Fechas mostradas en hora local; nunca se envía hora local al servidor.

---

## 10. Seguridad

**La web está expuesta a internet.** Cualquier persona puede llegar a la página de login, así que todo lo de esta sección
es obligatorio, no opcional.

### 10.1 Exposición pública

- **Separar quién entra por dónde:**
  - La API del dispositivo (`/api/v1/device/*`) solo acepta peticiones de la **red local**. Si una petición llega por
    el túnel (trae `CF-Connecting-IP` o `X-Forwarded-For`) o de una IP no privada, responde `403`. Configurable con
    `DISPOSITIVO_SOLO_LAN` (por defecto `true`).
  - La web y su API son accesibles desde la URL pública, siempre con sesión.
- **Hosts permitidos:** `TrustedHostMiddleware` con la URL pública, la IP local de la laptop y `localhost`
  (`HOSTS_PERMITIDOS`). Cualquier otro `Host` responde `400`.
- **IP real del cliente:** `cloudflared` se conecta a la app desde `127.0.0.1`. Para el límite de intentos, la IP del
  cliente se toma de `CF-Connecting-IP` **solo** si la petición viene de `127.0.0.1`; nunca se confía en ese header
  si viene de otra IP. Uvicorn arranca con `--proxy-headers --forwarded-allow-ips 127.0.0.1`.
- **Límites de peticiones:** login 5 por minuto por IP; resto de la API web 120 por minuto por IP; respuesta `429`.
- **Documentación de la API** (`/docs`, `/openapi.json`) desactivada fuera de desarrollo (`DOCS_PUBLICAS=false`).
- **No indexar:** `<meta name="robots" content="noindex">` y `robots.txt` con `Disallow: /`.
- **Encabezados de seguridad** en todas las respuestas: `Content-Security-Policy` (con `frame-ancestors 'none'`),
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin` y `Strict-Transport-Security` cuando la petición
  llegó por HTTPS.
- **Sesión:** cookie con `Secure` cuando se entra por la URL pública, `HttpOnly`, `SameSite=Strict`, expiración de
  8 h (`SESION_HORAS`) y se invalida al cerrar sesión.
- **Contraseña del administrador:** mínimo 12 caracteres; `tools/crear_admin.py` rechaza contraseñas más cortas.

### 10.2 Reglas generales

- Secretos solo en `.env` (en `.gitignore`). `.env.example` con todas las variables y sin valores reales.
- Contraseñas con bcrypt. Tokens de nodo: 40 caracteres de `secrets.token_urlsafe`, guardados como SHA-256 y
  comparados en tiempo constante.
- **Autorización en el servidor en cada operación:** un token solo puede leer y escribir lo de su autónomo y sus
  satélites (evita IDOR).
- Todas las consultas parametrizadas (SQLAlchemy). Nunca concatenar entradas en SQL.
- Usuario de MySQL de la app con mínimo privilegio (sin `DROP`); las migraciones usan otro usuario.
- Errores al cliente sin trazas ni detalles internos. Logs estructurados (JSON) con nivel; **nunca** registrar
  contraseñas, tokens ni cookies.
- CORS cerrado (la web y la API comparten origen).
- **Riesgo aceptado y documentado:** el ESP32 habla con el servidor por HTTP dentro de la red local (el ESP32 no
  maneja bien TLS y ese tramo nunca sale a internet). Todo el tráfico de personas va por HTTPS a través del túnel.
- **El servidor es la laptop:** debe quedarse encendida, sin suspenderse y con `cloudflared` instalado como servicio
  de Windows para que arranque solo. Si la laptop se apaga, la URL pública deja de responder (el ESP32 sigue guardando
  en LittleFS).

### 10.3 Variables de entorno (`.env.example`)

| Variable | Ejemplo | Uso |
|---|---|---|
| `ENTORNO` | `desarrollo` / `produccion` | Activa o desactiva `/docs` y los mensajes detallados |
| `DATABASE_URL` | `mysql+pymysql://aquasense_app:***@localhost:3306/aquasense` | Usuario de mínimo privilegio |
| `SECRET_KEY` | 64 caracteres aleatorios | Firma de la cookie de sesión |
| `HOSTS_PERMITIDOS` | `aquasense.midominio.com,192.168.1.50,localhost` | `TrustedHostMiddleware` |
| `DISPOSITIVO_SOLO_LAN` | `true` | Ver 10.1 |
| `DOCS_PUBLICAS` | `false` | Ver 10.1 |
| `SESION_HORAS` | `8` | Expiración de la sesión |
| `ZONA_HORARIA_WEB` | `America/Mexico_City` | Solo para mostrar fechas |
| `POLLING_PANEL_S` · `POLLING_GRAFICAS_S` | `10` · `60` | Ver 9.2 |

---

## 11. Pruebas

Pirámide: muchas unitarias, algunas de integración, pocas de extremo a extremo. Estructura AAA. Nombres descriptivos
en español: `test_asigna_hora_ntp_cuando_la_lectura_es_de_un_boot_anterior`.

**Unitarias (`tests/unit/`, todo `dominio/`):**
- Hora: mismo boot, boot anterior con NTP, sin NTP, epoch en el futuro, epoch anterior a 2026.
- Alertas: abre fuera de rango, no duplica, se resuelve solo con histéresis, booleanos.
- Comandos: transiciones válidas e inválidas, expiración, no reenvío de `DISPENSAR`.
- Parámetros: rangos, opciones, reglas entre parámetros, módulo requerido.
- Predicción: sin datos suficientes, pendiente ≤ 0, cruce correcto del umbral, baseline.

**Integración (`tests/integration/`, MySQL de prueba):**
- Token ausente → 401; token de otro autónomo → 403.
- Petición a `/device/*` con `CF-Connecting-IP` o desde IP pública → 403 (con `DISPOSITIVO_SOLO_LAN=true`).
- `Host` no permitido → 400. `CF-Connecting-IP` enviado desde una IP distinta de `127.0.0.1` se ignora.
- Encabezados de seguridad presentes en las respuestas; `/docs` responde 404 con `DOCS_PUBLICAS=false`.
- Lote con duplicados: acepta los nuevos y cuenta los repetidos.
- Lectura de MAC no registrada → rechazada sola, el resto se guarda.
- Autodescubrimiento: un módulo nuevo crea su `sensor`.
- Cambiar parámetros sube `config_version` en la misma transacción.
- Segundo `DISPENSAR` activo → 409.
- Login: contraseña incorrecta → 401; sexto intento en un minuto → 429.

**Extremo a extremo:** `tools/simulador_esp32.py` contra el servidor completo, y una lista de verificación manual en
celular antes de cada demo (en `docs/`).

Nunca borres ni debilites una prueba para que pase.

---

## 12. Simulador del ESP32 (`tools/simulador_esp32.py`)

- Simula un autónomo con N satélites, cada uno con su lista de módulos (argumento de línea de comandos).
- Envía telemetría cada 10 s y consulta configuración cada 5 s, con el contrato exacto de la sección 6.
- Genera TDS que sube poco a poco (para probar la predicción), alertas ocasionales y dosis automáticas.
- Responde ACK a los comandos recibidos.
- Modo `--sin-red` que acumula lecturas y las reenvía en lote, y modo `--reinicio` que cambia `boot`, para probar 7.1.
- `--help` útil; códigos de salida correctos.

---

## 13. Fases de desarrollo

| Fechas | Fase | Terminada cuando… |
|---|---|---|
| 5–6 nov | **0. Base:** repo, `pyproject.toml`, Ruff, pytest, CI, `docker-compose.yml`, primera migración con catálogos, `/health` | CI en verde y `/health` responde con la base conectada |
| 7–11 nov | **1. Ingesta:** contrato de telemetría completo (6.1, 7.1), alta de nodos, simulador, login, panel general, seguridad de exposición pública (10.1) y túnel | El autónomo real o el simulador guardan datos 24/7 y el panel se abre desde un celular con datos móviles. **Ruta crítica: la predicción depende de este historial** |
| 12–16 nov | **2. Control:** alertas (7.2), comandos y ACK (6.2, 6.3, 7.3), parámetros (7.4), pantallas de configuración | "Dispensar ahora" desde el celular mueve el servo y queda confirmado |
| 17–20 nov | **3. Análisis:** gráficas agregadas, cambios de agua, predicción (7.5) | La predicción se muestra con su baseline. **Congelación de código: 20 de noviembre** |
| 21–28 nov | **4. Cierre:** solo correcciones, accesibilidad, README, ADRs, ensayo de la demo | Checklist final completo |

---

## 14. Despliegue: acceso público por internet

El servidor vive en la ThinkPad y se publica con **Cloudflare Tunnel**. El túnel abre una conexión **saliente** desde
la laptop hacia Cloudflare, que entrega una URL pública con HTTPS. No se abren puertos en el router.

### 14.1 Servidor en la laptop

- `uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1`
- Router con canal WiFi fijo en 2.4 GHz y la IP de la laptop reservada (el ESP32 la usa).
- Firewall de Windows: permitir el puerto 8000 **solo desde la red local** (perfil privado), para el ESP32.
- La laptop no se suspende; `cloudflared` y la app arrancan solos al iniciar Windows.

### 14.2 Túnel: dos modos

| Modo | Cómo | URL | Para qué |
|---|---|---|---|
| **Túnel con nombre (recomendado)** | Cuenta gratuita de Cloudflare + un dominio propio gestionado en Cloudflare; `cloudflared` instalado como servicio | Fija, p. ej. `https://aquasense.midominio.com` | Que la URL no cambie y se pueda compartir con el profe y el equipo |
| **Quick Tunnel (respaldo)** | `cloudflared tunnel --url http://localhost:8000`, sin cuenta | Aleatoria en `trycloudflare.com`, **cambia cada vez que se reinicia** | Pruebas o emergencia el día de la demo. Cloudflare lo marca como solo para pruebas y sin garantía de disponibilidad |

- Al cambiar de URL, actualizar `HOSTS_PERMITIDOS`.
- **No usar el plan gratuito de ngrok:** tiene un límite mensual de peticiones HTTP que el polling de la web agota en
  pocos días, y muestra una página de advertencia antes de abrir el sitio.
- El ESP32 **siempre** usa la IP local, nunca la URL pública.

### 14.3 Operación

- **Respaldo:** `mysqldump` diario y antes de cada demo, **probando la restauración**. El historial no se puede
  regenerar. Los respaldos no van al repositorio.
- **Versiones:** una etiqueta git por versión estable (`v0.1-ingesta`, `v1.0-entrega`) para poder regresar.
- **Verificación antes de la demo:** abrir la URL pública desde un celular **con datos móviles** (fuera de la red
  local), iniciar sesión, ver datos en vivo y dispensar.

---

## 15. Git y documentación

- Ramas `feature/…` y `fix/…`; `main` siempre funcional. Commits pequeños con Conventional Commits
  (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`). Pull request con qué, por qué y cómo probar.
- `.gitignore`: `.env`, entornos virtuales, `__pycache__`, respaldos `.sql`, archivos del IDE.
- **README:** qué es, requisitos, instalación, variables de entorno, cómo correr servidor, simulador y pruebas,
  estructura.
- **ADRs** en `docs/adr/`:
  - 001 FastAPI en lugar de Node.js
  - 002 MySQL
  - 003 Polling en lugar de WebSockets/MQTT
  - 004 La hora la asigna el servidor (NTP como respaldo)
  - 005 Publicación por Cloudflare Tunnel desde la laptop (y por qué el ESP32 usa la red local)
  - 006 Tailwind por CDN
- `docs/contrato-api.md` se actualiza **en el mismo cambio** que modifique el contrato del dispositivo.

---

## 16. Fuera de alcance (no implementar)

Registro de usuarios y roles · WebSockets/MQTT · tareas en segundo plano · hosting en la nube (VPS o PaaS; la
publicación es solo por túnel desde la laptop) · que el ESP32 use la URL pública · aplicación móvil nativa · consejos
generados por IA · sensor de oxígeno disuelto · LoRa · integración con plataformas de otros equipos.

---

## 17. Checklist antes de dar por terminada una tarea

- [ ] Cumple lo pedido, sin funcionalidad extra.
- [ ] Casos límite y errores manejados.
- [ ] `ruff check` y `ruff format --check` sin advertencias.
- [ ] Pruebas nuevas para la lógica nueva; **todas** las pruebas pasan (ejecutadas, no supuestas).
- [ ] Sin secretos en el código; entradas validadas; consultas parametrizadas; permisos verificados en el servidor.
- [ ] Web: revisada en vista móvil, accesible, con estados de carga, vacío y error.
- [ ] Si toca la exposición pública: probado por la URL pública y las pruebas de 10.1 pasan.
- [ ] Migración creada si cambió el modelo.
- [ ] README, contrato o ADR actualizados si aplica.
- [ ] Resumen honesto: qué cambió, cómo se verificó y qué queda pendiente.
