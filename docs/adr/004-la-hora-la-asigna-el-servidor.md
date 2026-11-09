# ADR-004: La hora la asigna el servidor (NTP como respaldo)

**Estado:** aceptada · **Fecha:** 2026-11-05

## Contexto

Los ESP32 no tienen un reloj confiable: al arrancar sin red no saben la hora, y el RTC es opcional.
Sin una hora correcta, el historial y la predicción no sirven.

## Decisión

El servidor pone `medido_en` a cada lectura (`app/dominio/tiempo.py`):

1. Si la lectura es del arranque actual del autónomo (`boot` igual): hora de recepción menos `edad_ms`.
   Origen `servidor`.
2. Si es de un arranque anterior y trae `epoch_ms` válido: esa hora. Origen `ntp`.
3. Si no: hora de recepción, con origen `desconocida`.

Un `epoch_ms` más de 60 s en el futuro, o anterior a 2026, se descarta.

## Razones

- `edad_ms` lo mide el autónomo con su propio contador, que sí es confiable aunque no sepa la hora real.
- El reloj del servidor está sincronizado: es la mejor fuente disponible.
- Marcar el origen permite excluir de gráficas y predicción lo que no tiene una hora confiable, en lugar
  de inventarla.

## Consecuencias

- **Reenvíos del arranque actual:** una lectura reenviada obtiene otra hora, porque depende del momento
  de recepción, y no se detecta como duplicada. El firmware debe reenviar con `epoch_ms` (documentado en
  `docs/contrato-api.md`).
- **Alertas:** las lecturas atrasadas o de hora desconocida no abren ni cierran alertas.
- **`servidor_epoch_ms`:** viaja en `GET /device/config` para que el nodo pueda ajustar su reloj sin NTP.
