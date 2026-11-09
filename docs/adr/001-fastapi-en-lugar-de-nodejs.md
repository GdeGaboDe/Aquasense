# ADR-001: FastAPI en lugar de Node.js

**Estado:** aceptada · **Fecha:** 2026-11-05

## Contexto

El servidor recibe telemetría de los ESP32, guarda el historial, sirve la aplicación web y calcula la
predicción del cambio de agua. El equipo es de tres personas, con más experiencia en Python, y la
entrega es el 30 de noviembre de 2026.

## Decisión

Usar Python 3.12 con FastAPI y Uvicorn. Validación con Pydantic v2 y acceso a datos con SQLAlchemy 2.0.

## Razones

- **Un solo lenguaje para todo:** la predicción usa numpy. Con Node.js habría un segundo lenguaje o un
  servicio aparte solo para el análisis.
- **Validación en el contrato:** Pydantic rechaza con `422` cualquier lote que no cumpla el esquema, sin
  escribir validaciones a mano en cada ruta.
- **Documentación automática** de la API en `/docs`, útil para quien programa el firmware. Solo se
  publica en desarrollo (`DOCS_PUBLICAS`).
- **Pruebas sencillas** con pytest y el `TestClient` de FastAPI.

## Consecuencias

- Las rutas son síncronas y FastAPI las corre en un pool de hilos. Para una instalación con pocos
  nodos y un solo proceso alcanza de sobra; no se usa `async` en el acceso a datos.
- El frontend no necesita herramientas de compilación: FastAPI sirve los archivos de `web/` tal cual.
