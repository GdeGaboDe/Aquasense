# ADR-002: MySQL 8

**Estado:** aceptada · **Fecha:** 2026-11-05

## Contexto

El historial de lecturas no se puede regenerar y es la base de la predicción. El modelo de datos está
normalizado a 3FN y necesita restricciones en la propia base.

## Decisión

MySQL 8.4 (LTS) en un contenedor de Docker, con el driver PyMySQL. Migraciones con Alembic, nunca
cambios manuales.

## Razones

- Es el motor que el equipo conoce de la carrera, y soporta lo que pide el diseño: llaves foráneas,
  `CHECK`, `DATETIME(3)` con milisegundos, `JSON` y columnas generadas.
- **Mínimo privilegio:** la app se conecta con un usuario sin `DROP`, `CREATE` ni `ALTER`. Las migraciones
  usan otro usuario. Lo crea `docker/mysql/01-usuarios.sh`.
- **Sin duplicados por diseño:** la llave `(sensor_id, medido_en)` de `lectura` evita duplicar los
  reenvíos desde LittleFS.

## Consecuencias

- **Una alerta activa por tipo:** MySQL no tiene índices parciales. La regla se impone con dos columnas
  generadas en un índice único (`alerta.variable_clave` y `alerta.activa`).
- **Cambiar de motor solo cambia `DATABASE_URL`:** todo el SQL pasa por SQLAlchemy, sin funciones propias
  de MySQL, y la agregación de series se hace en Python. Por eso el desarrollo sin Docker funciona con
  SQLite.
- **SQLite no sustituye a MySQL:** CI prueba contra MySQL, que sigue siendo la referencia.
- **Respaldos obligatorios:** `mysqldump` diario y antes de cada demo, probando la restauración (ver
  `docs/operacion.md`).
