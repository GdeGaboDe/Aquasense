# Contrato de la API para el ESP32

Referencia para quien programa el firmware. Base: `/api/v1/device`. Solo JSON.

- **Autenticación:** header `X-API-Token` con el token del **nodo autónomo**.
- **Red:** el autónomo llama por la IP local de la laptop, por HTTP y nunca por la URL pública. Una
  petición que llega por el túnel o desde una IP pública responde `403`.
- **Host:** la IP local debe estar en `HOSTS_PERMITIDOS`; si no, el servidor responde `400`.
- **Cadencias:** telemetría cada 10 s; configuración cada 5 s.

| Endpoint | Estado |
|---|---|
| `POST /telemetry` | Disponible |
| `GET /config` | Disponible |
| `POST /ack` | Disponible |

## `POST /telemetry`

```json
{
  "lote": 1842,
  "enviado_epoch_ms": 1793750400000,
  "nodos": [
    {
      "mac": "24:6F:28:AB:CD:EF",
      "firmware": "1.2.0",
      "boot": 7,
      "modulos": ["temp", "tds", "servo"],
      "config_version_aplicada": 4
    }
  ],
  "lecturas": [
    { "mac": "24:6F:28:AB:CD:EF", "variable": "temp_c", "valor": 25.4,
      "edad_ms": 1200, "boot": 7, "epoch_ms": null }
  ],
  "eventos": [
    { "mac": "24:6F:28:AB:CD:EF", "tipo": "dosis", "cargas": 2, "origen": "automatico",
      "comando_id": null, "edad_ms": 30000, "boot": 7, "epoch_ms": null }
  ]
}
```

| Campo | Regla |
|---|---|
| `nodos` | Se manda en **cada** lote, con el autónomo incluido. Máximo 50 |
| `nodos[].modulos` | Lista completa de módulos actuales: un módulo que deja de aparecer se considera retirado |
| `lecturas` | Máximo 5,000 por lote |
| `eventos` | Máximo 1,000 por lote. `cargas` de 1 a 5; `origen`: `remoto`, `automatico` o `local` |
| `edad_ms` | Milisegundos entre la medición y el envío, según el reloj del autónomo |
| `boot` | Contador de arranques **del autónomo** al medir |
| `epoch_ms` | Hora Unix si el autónomo tenía NTP al medir; si no, `null` |
| `valor` | Los booleanos viajan como `0` o `1`. No admite `NaN` ni infinito |

Una lectura solo se acepta si su variable pertenece a un módulo anunciado en `nodos`, en este lote o
en uno anterior.

### Cómo se asigna la hora

1. `boot` igual al del autónomo en este lote: hora del servidor menos `edad_ms`.
2. Arranque anterior con `epoch_ms` válido: se usa `epoch_ms`.
3. En otro caso: hora de recepción, marcada como `desconocida` y excluida de gráficas y predicción.

Un `epoch_ms` más de 60 s en el futuro o anterior a 2026 se descarta y se aplica el paso 3.

### Respuesta `200`

```json
{
  "aceptadas": 41,
  "duplicadas": 3,
  "rechazadas": [ { "lista": "lecturas", "indice": 7, "motivo": "MAC_NO_REGISTRADA" } ]
}
```

Los contadores incluyen lecturas y eventos. `lista` indica en qué arreglo está `indice`.
Un rechazo es definitivo: **no** reenvíes ese elemento.

| Motivo | Significado |
|---|---|
| `MAC_NO_REGISTRADA` | La MAC no está dada de alta |
| `NODO_AJENO` | La MAC pertenece a otro autónomo |
| `NODO_INACTIVO` | El nodo está desactivado |
| `VARIABLE_DESCONOCIDA` | La variable no está en el catálogo |
| `VARIABLE_NO_ANUNCIADA` | El nodo no ha anunciado el módulo de esa variable |
| `FUERA_DE_RANGO_FISICO` | El valor está fuera del rango físico de la variable |
| `VALOR_NO_BOOLEANO` | Una variable booleana trae algo distinto de `0` o `1` |
| `COMANDO_INVALIDO` | La dosis cita un comando inexistente o de otro nodo |

### Reenvíos

Se detectan duplicados por sensor y hora de medición (por nodo y hora en las dosis). **Una lectura
del arranque actual reenviada obtiene otra hora**, porque depende del momento de recepción, y no se
detecta como duplicada. Para reenviar con seguridad, incluye `epoch_ms` y conserva el valor original.
Una dosis ligada a un comando nunca se duplica.

## `GET /config`

```json
{
  "servidor_epoch_ms": 1793750400123,
  "nodos": [
    { "mac": "24:6F:28:AB:CD:EF", "config_version": 5,
      "parametros": { "MODO_DISPENSA": "AUTOMATICO", "INTERVALO_ALIMENTACION_HORAS": 8, "CANTIDAD_CARGAS": 2 } }
  ],
  "comandos": [
    { "id": 912, "mac": "24:6F:28:AB:CD:EF", "tipo": "DISPENSAR", "argumento": 2 }
  ]
}
```

- Incluye al autónomo y a sus satélites activos. El autónomo retransmite por ESP-NOW lo de cada satélite.
- `parametros` trae **todos** los que aplican al nodo, con su valor vigente: el configurado o el de fábrica.
  Solo aparecen los de los módulos que el nodo anunció. Enteros y decimales viajan como número; las
  opciones, como texto.
- Aplica la configuración cuando `config_version` sea mayor que la que tienes, y reporta la versión
  aplicada en `nodos[].config_version_aplicada` del siguiente lote de telemetría.
- `servidor_epoch_ms` sirve para ajustar el reloj si no hay NTP.
- **Un comando se entrega una sola vez:** al aparecer aquí pasa a `entregado` y no se repite. Si se pierde,
  no se reenvía. Un comando que no se entrega en 120 s expira.

| Comando | `argumento` | Módulo |
|---|---|---|
| `DISPENSAR` | cargas, de 1 a 5 | `servo` |
| `SILENCIAR_ALARMA` | minutos, de 1 a 60 | `alarma` |
| `AIREADOR` | `0` apagar, `1` encender | `aireador` |

## `POST /ack`

```json
{ "comando_id": 912, "resultado": "confirmado", "detalle": null }
```

- `resultado`: `confirmado` o `fallido`. `detalle`: texto opcional de hasta 200 caracteres.
- Respuesta `200`: `{"comando_id": 912, "estado": "confirmado"}`.
- Repetir el mismo ACK no cambia nada: reintenta sin miedo si no recibiste respuesta.
- Al ejecutar un `DISPENSAR`, envía también el evento `dosis` con su `comando_id` y `origen: "remoto"`.

| Código | Cuándo |
|---|---|
| 403 `COMANDO_AJENO` | El comando no es de este autónomo ni de sus satélites |
| 404 `COMANDO_NO_ENCONTRADO` | No existe ese comando |
| 409 `ACK_INVALIDO` | El ACK contradice el estado: otro resultado ya registrado, o comando expirado |

## Errores

Formato único: `{"error": {"code": "TOKEN_INVALIDO", "message": "…", "details": null}}`.

| Código | Cuándo | Qué hacer |
|---|---|---|
| 401 | Falta el token, no es válido o el autónomo está desactivado | Revisar el token; no reintentar en ciclo rápido |
| 403 | La petición no viene de la red local | Usar la IP local |
| 409 | Otro envío guardó los mismos datos a la vez | Reintentar el lote |
| 422 | El JSON no cumple el esquema; no se guarda nada del lote | Corregir el firmware |
| 429 | Demasiadas peticiones | Esperar y reintentar |
