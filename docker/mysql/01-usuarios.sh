#!/bin/sh
# Crea las bases y separa privilegios: la app no puede alterar el esquema (CLAUDE.md, 10.2).
# MySQL solo ejecuta este script la primera vez que se inicializa el volumen de datos.
set -eu

mysql --protocol=socket -uroot -p"$MYSQL_ROOT_PASSWORD" <<SQL
CREATE DATABASE IF NOT EXISTS aquasense CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE IF NOT EXISTS aquasense_test CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE USER 'aquasense_app'@'%' IDENTIFIED BY '$MYSQL_APP_PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE ON aquasense.* TO 'aquasense_app'@'%';

CREATE USER 'aquasense_migraciones'@'%' IDENTIFIED BY '$MYSQL_MIGRACIONES_PASSWORD';
GRANT ALL PRIVILEGES ON aquasense.* TO 'aquasense_migraciones'@'%';
GRANT ALL PRIVILEGES ON aquasense_test.* TO 'aquasense_migraciones'@'%';
SQL
