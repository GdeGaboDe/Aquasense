# Operación del servidor (laptop)

Cómo dejar AquaSense funcionando 24/7 en la ThinkPad (CLAUDE.md, sección 14). Los comandos son para
PowerShell. Los que cambian la configuración de Windows se corren **como administrador**.

> **Estado:** los procedimientos de esta guía todavía no se han ensayado de punta a punta en la laptop.
> Ensáyalos completos una vez antes de la primera demo, empezando por el respaldo y su restauración.

## 1. Antes de guardar historial real

1. **Borra los datos simulados.** Las lecturas del simulador contaminarían la predicción. Lo más simple
   es recrear la base: `docker compose down -v` borra el volumen de **todo** MySQL, así que respalda
   antes si hay algo que conservar. Luego `docker compose up -d --wait` y `alembic upgrade head`.
2. **Crea el administrador definitivo** con una contraseña nueva de al menos 12 caracteres:
   `python -m tools.crear_admin --usuario <nombre>`. No reutilices las contraseñas de desarrollo.
3. **Da de alta el autónomo real** con `python -m tools.crear_nodo` y guarda su token para el firmware.
4. **Revisa `.env`:** `ENTORNO=produccion`, `DOCS_PUBLICAS=false` y `HOSTS_PERMITIDOS` con la URL pública
   y la IP local de la laptop.
5. **Fija los umbrales de cada tanque** en Ajustes, incluido el máximo de TDS: sin él no hay predicción.

## 1.1 Con Docker (recomendado)

```powershell
docker compose up -d --build --wait
```

- **`mysql`**: la base, con su volumen de datos.
- **`migraciones`**: aplica las migraciones con el usuario que puede cambiar el esquema, y termina.
- **`app`**: la aplicación, solo con el usuario de mínimo privilegio, en el puerto `PUERTO_APP` de la laptop.
  Corre como usuario sin privilegios y la imagen no lleva el `.env`.
- **`cloudflared`** (perfil `tunel`): el túnel con nombre, con IP fija `IP_TUNEL` dentro de la red de
  Docker. La app solo confía en los encabezados de proxy que llegan desde esa IP.

Para crear el administrador dentro del contenedor:

```powershell
docker compose run --rm app python -m tools.crear_admin --usuario <nombre>
```

`.env` debe incluir `127.0.0.1` en `HOSTS_PERMITIDOS`, porque la revisión de salud del contenedor
consulta por esa dirección. Las contraseñas de MySQL van dentro de URLs, así que usa solo letras,
números, `-` y `_`.

> **Con Docker, el túnel debe ir en el contenedor `cloudflared`, no como servicio de Windows.** Desde Windows
> las peticiones llegarían a la app por la red de Docker, que no es el proxy de confianza. Se perderían la
> cookie `Secure`, HSTS y el límite de login por persona.

## 2. Red y energía

- **IP fija para la laptop:** resérvala en el router (DHCP), porque el ESP32 la tiene configurada.
- **WiFi en 2.4 GHz con canal fijo:** el ESP32 y ESP-NOW lo necesitan.
- **Que no se suspenda conectada a la corriente:**

```powershell
powercfg /change standby-timeout-ac 0
```

```powershell
powercfg /change hibernate-timeout-ac 0
```

- **Puerto 8010 abierto solo para la red local**, para el ESP32:

```powershell
New-NetFirewallRule -DisplayName "AquaSense ESP32" -Direction Inbound -Protocol TCP -LocalPort 8010 -Profile Private -RemoteAddress LocalSubnet -Action Allow
```

- **Puerto 8010 libre:** si otro proyecto lo usa (por ejemplo, un contenedor de Docker), en Windows
  ambos pueden quedar escuchando sin error. Comprueba que `http://localhost:8010/health` responda
  `"base_de_datos":"conectada"`.

## 3. Arranque automático

Con Docker basta con activar en Docker Desktop la opción de iniciar con la sesión de Windows: todos los
contenedores tienen `restart: unless-stopped`.

Sin Docker para la app, una tarea programada que corra al iniciar sesión. Ajusta la ruta del proyecto:

```powershell
$accion = New-ScheduledTaskAction -Execute "D:\1_Universidad\5-SEMESTRE\Embebed\Proyecto\Code\.venv\Scripts\python.exe" -Argument "-m uvicorn app.main:app --host 0.0.0.0 --port 8010 --proxy-headers --forwarded-allow-ips 127.0.0.1" -WorkingDirectory "D:\1_Universidad\5-SEMESTRE\Embebed\Proyecto\Code"
```

```powershell
Register-ScheduledTask -TaskName "AquaSense" -Action $accion -Trigger (New-ScheduledTaskTrigger -AtLogOn) -RunLevel Limited
```

Usa `--host 0.0.0.0` para que el ESP32 llegue por la red local. El firewall limita el acceso a esa red.

## 4. Túnel con nombre (URL fija)

Con Docker: crea el túnel en el panel apuntando a `http://app:8000`, pon su token en
`CLOUDFLARE_TUNNEL_TOKEN` y corre `docker compose --profile tunel up -d`. Los pasos siguientes son para
la app sin Docker.

1. En el panel de Cloudflare, con un dominio propio: **Zero Trust → Networks → Tunnels → Create**.
2. Asigna un nombre público, por ejemplo `aquasense.tudominio.com`, apuntando a `http://127.0.0.1:8010`.
   Debe ser `127.0.0.1`, no `localhost`, porque es la única IP de la que el servidor acepta encabezados
   de proxy.
3. Instala el servicio de Windows con el token que da el panel, para que arranque solo:

```powershell
cloudflared service install <token-del-panel>
```

4. Agrega `aquasense.tudominio.com` a `HOSTS_PERMITIDOS` y reinicia la app.

Para pruebas rápidas sigue sirviendo el Quick Tunnel; recuerda que su URL cambia en cada reinicio:

```powershell
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --no-autoupdate --url http://127.0.0.1:8010
```

## 5. Respaldo y restauración

**El historial no se puede regenerar.** Respalda a diario y antes de cada demo, guarda los archivos fuera
del repositorio (`*.sql` está en `.gitignore`), y **prueba la restauración**: un respaldo que no se ha
restaurado no cuenta como respaldo.

El respaldo se genera dentro del contenedor y luego se copia, porque en PowerShell 5.1 la redirección
`>` guarda en UTF-16 y el archivo ya no se puede restaurar.

**Respaldar:**

```powershell
docker exec aquasense-mysql sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --no-tablespaces --databases aquasense --result-file=/tmp/respaldo.sql'
```

```powershell
docker cp aquasense-mysql:/tmp/respaldo.sql "D:\Respaldos\aquasense_$(Get-Date -Format yyyy-MM-dd_HHmm).sql"
```

**Probar la restauración** en una base aparte, sin tocar la real. El respaldo trae el nombre
`aquasense` (por `--databases`), así que primero se cambia por `aquasense_restauracion`:

```powershell
docker exec aquasense-mysql sh -c 'sed "s/\`aquasense\`/\`aquasense_restauracion\`/g" /tmp/respaldo.sql > /tmp/restauracion.sql && mysql -uroot -p"$MYSQL_ROOT_PASSWORD" < /tmp/restauracion.sql'
```

```powershell
docker exec aquasense-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "SELECT (SELECT COUNT(*) FROM aquasense.lectura) AS original, (SELECT COUNT(*) FROM aquasense_restauracion.lectura) AS restaurada"'
```

Si los dos conteos coinciden, el respaldo sirve. Después borra la base de prueba:

```powershell
docker exec aquasense-mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE aquasense_restauracion"'
```

## 6. Versiones

Etiqueta cada versión estable para poder regresar a ella: `git tag v0.1-ingesta` y, al entregar,
`git tag v1.0-entrega`.
