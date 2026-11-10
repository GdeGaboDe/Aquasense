# Guía: montar el servidor común de AquaSense en una laptop

Paso a paso para que una laptop con Windows sea el servidor del equipo: guarda los datos, recibe la
información del ESP32 y publica la página web para que cualquiera entre desde su celular.

**Tiempo estimado:** 1 a 2 horas la primera vez, casi todo esperando descargas.
**Quién la sigue:** la persona dueña de la laptop. Los demás solo necesitan la URL y su contraseña.

## Antes de empezar

| Requisito | Por qué |
|---|---|
| Windows 10 u 11 de 64 bits, con al menos 8 GB de RAM y 10 GB libres | Docker y la base de datos |
| Permisos de administrador | Para instalar programas y ajustar el firewall |
| Virtualización activada en la BIOS | Docker la necesita. Si al abrir Docker Desktop aparece un error de virtualización, actívala en la BIOS ("Intel VT-x", "AMD-V" o "SVM") |
| Que la laptop pueda quedarse encendida y conectada a la corriente | Si se apaga, la página deja de responder |
| Que use **la misma red WiFi que el ESP32**, en 2.4 GHz | El ESP32 le envía los datos por la red local |

Los comandos son para **PowerShell**: menú Inicio → escribe "PowerShell". Algunos dicen "**como
administrador**": clic derecho en PowerShell → "Ejecutar como administrador".

---

## Paso 1. Instalar Git y Docker Desktop

1. **Git:** descárgalo de <https://git-scm.com/download/win> e instálalo con las opciones por defecto.
2. **Docker Desktop:** descárgalo de <https://www.docker.com/products/docker-desktop/>. Durante la
   instalación deja marcado **"Use WSL 2"**. Reinicia si te lo pide.
3. Abre Docker Desktop y espera a que diga **"Engine running"** abajo a la izquierda.
4. En Docker Desktop → **Settings → General**, marca **"Start Docker Desktop when you sign in"**. Así
   arranca solo al encender la laptop.
5. Comprueba en PowerShell:

```powershell
git --version
```

```powershell
docker compose version
```

Los dos deben mostrar un número de versión.

---

## Paso 2. Descargar el proyecto

Elige una carpeta fija, que no se vaya a borrar ni mover, por ejemplo `C:\AquaSense`:

```powershell
cd C:\
```

```powershell
git clone https://github.com/GdeGaboDe/Aquasense.git AquaSense
```

```powershell
cd C:\AquaSense
```

> **Importante:** mientras no se haya hecho el merge a `main`, el código completo está en otra rama.
> Comprueba con `git branch -r`. Si `main` todavía no tiene todo, cambia a la rama más reciente:
>
> ```powershell
> git checkout feature/guia-servidor
> ```
>
> Cuando ya esté en `main`, usa `git checkout main`.

---

## Paso 3. Crear el archivo de configuración `.env`

El `.env` guarda las contraseñas y **nunca se sube a GitHub** (ya está excluido). Cada servidor tiene el
suyo.

1. Copia la plantilla:

```powershell
Copy-Item .env.example .env
```

2. Genera **cuatro valores aleatorios**: tres contraseñas para MySQL y la clave de las sesiones. Corre
   este comando **cuatro veces** y copia cada resultado en un lugar seguro:

```powershell
$b = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); -join ($b | ForEach-Object { $_.ToString('x2') })
```

   Cada uno es un texto de 64 caracteres con números y letras de la a a la f. No uses otros
   símbolos: las contraseñas van dentro de direcciones y solo admiten letras, números, `-` y `_`.

3. Abre el archivo con el Bloc de notas:

```powershell
notepad .env
```

4. Cambia estas líneas. Donde dice `CLAVE_1`, `CLAVE_2`, `CLAVE_3` y `CLAVE_4`, pega los valores del
   punto 2. **La misma contraseña debe aparecer en dos lugares**, como se indica:

```
ENTORNO=produccion
DATABASE_URL=mysql+pymysql://aquasense_app:CLAVE_2@localhost:3306/aquasense
MIGRACIONES_DATABASE_URL=mysql+pymysql://aquasense_migraciones:CLAVE_3@localhost:3306/aquasense
SECRET_KEY=CLAVE_4
HOSTS_PERMITIDOS=localhost,127.0.0.1
DOCS_PUBLICAS=false

MYSQL_ROOT_PASSWORD=CLAVE_1
MYSQL_APP_PASSWORD=CLAVE_2
MYSQL_MIGRACIONES_PASSWORD=CLAVE_3

PUERTO_APP=8010
```

   - `CLAVE_2` va en `DATABASE_URL` y en `MYSQL_APP_PASSWORD`.
   - `CLAVE_3` va en `MIGRACIONES_DATABASE_URL` y en `MYSQL_MIGRACIONES_PASSWORD`.
   - Deja las demás líneas como están. Guarda y cierra.

> **Cuidado:** MySQL toma estas contraseñas **solo la primera vez** que arranca. Si después las
> cambias en `.env`, ya no coincidirán. Para empezar de nuevo hay que borrar el volumen de datos
> (`docker compose down -v`), y eso **borra toda la información**. Decide bien las contraseñas antes del
> Paso 4.

---

## Paso 4. Arrancar AquaSense

```powershell
docker compose up -d --build --wait
```

La primera vez tarda varios minutos, porque descarga MySQL y construye la aplicación. Al terminar debe
decir que `aquasense-mysql` y `aquasense-app` están **Healthy**, y que el contenedor de migraciones
terminó (`Exited`). Esto es normal: solo prepara la base y se cierra.

Comprueba:

```powershell
docker compose ps
```

```powershell
curl.exe http://localhost:8010/health
```

Debe responder `{"estado":"ok","base_de_datos":"conectada"}`.

---

## Paso 5. Crear las cuentas de acceso

Cada persona del equipo puede tener su propio usuario. Por cada una:

```powershell
docker compose run --rm app python -m tools.crear_admin --usuario NOMBRE
```

Pide la contraseña dos veces, sin mostrarla. Debe tener **al menos 12 caracteres**. Todos los usuarios
son administradores.

---

## Paso 6. Abrir la página en la laptop

1. Abre <http://localhost:8010> en el navegador.
2. Entra con el usuario que creaste.
3. En **Ajustes → Nuevo tanque**, crea los tanques (nombre y litros).
4. En **Ajustes → Umbrales**, después de que el ESP32 envíe datos, define el rango de cada variable. El
   **máximo de TDS** es necesario para la predicción del cambio de agua.

---

## Paso 7. Preparar la red para el ESP32

1. **Conecta la laptop al mismo WiFi del ESP32**, el que tiene escrito el firmware (`ssid`), en 2.4 GHz.
2. **Marca esa red como privada:** Configuración → Red e Internet → Wi-Fi → tu red → Perfil de red:
   **Privada**.
3. **Busca la IP de la laptop:**

```powershell
ipconfig
```

   Busca la sección **"Adaptador de LAN inalámbrica Wi-Fi"** y anota la **Dirección IPv4**, por ejemplo
   `192.168.1.50`. Ignora los adaptadores "vEthernet", "VirtualBox" o "WSL".

4. **Reserva esa IP en el router** para que no cambie. Se hace en la página de administración del router
   (normalmente <http://192.168.1.1>), en "DHCP" o "Reserva de direcciones". Si no tienes acceso al
   router, la IP puede cambiar al reiniciar, y habría que actualizarla en el ESP32 o en el puente.
5. **Agrega la IP a `HOSTS_PERMITIDOS`** en `.env`:

```
HOSTS_PERMITIDOS=localhost,127.0.0.1,192.168.1.50
```

6. **Abre el puerto 8010 solo para la red local** (PowerShell **como administrador**):

```powershell
New-NetFirewallRule -DisplayName "AquaSense" -Direction Inbound -Protocol TCP -LocalPort 8010 -Profile Private -RemoteAddress LocalSubnet -Action Allow
```

7. Aplica el cambio de `.env`:

```powershell
docker compose up -d
```

8. **Prueba desde otro equipo o un celular conectado al mismo WiFi:** abre `http://192.168.1.50:8010`,
   con la IP de tu laptop. Debe verse el login.

---

## Paso 8. Que la laptop no se duerma

En PowerShell **como administrador**:

```powershell
powercfg /change standby-timeout-ac 0
```

```powershell
powercfg /change hibernate-timeout-ac 0
```

Para que **cerrar la tapa no la suspenda** (conectada a la corriente):

```powershell
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0
```

```powershell
powercfg /setactive SCHEME_CURRENT
```

Docker Desktop arranca cuando **inicias sesión** en Windows. Si la laptop se reinicia (por ejemplo, por
una actualización), alguien debe iniciar sesión para que AquaSense vuelva.

---

## Paso 9. Conectar el ESP32 (cuando tengan la placa)

Sigue **`docs/conexion-esp32.md`**. En resumen:

1. Enciende el ESP32 y anota su IP desde el monitor serie (115200 baudios).
2. Da de alta el nodo con la MAC del ESP32 (la ves en la lista de equipos del router):

```powershell
docker compose run --rm app python -m tools.crear_nodo --mac AA:BB:CC:DD:EE:FF --nombre Principal --tanque NOMBRE_DEL_TANQUE --usuario TU_USUARIO
```

   Si el tanque no existe todavía, agrega `--volumen-l 20`. **Copia el token** que aparece: no se vuelve
   a mostrar.

3. Agrega a `.env`:

```
PUENTE_ESP32=http://IP_DEL_ESP32
PUENTE_MAC=AA:BB:CC:DD:EE:FF
AQUASENSE_TOKEN=EL_TOKEN
```

4. Arranca el puente:

```powershell
docker compose --profile puente up -d
```

5. Revisa que lleguen datos:

```powershell
docker compose logs -f puente
```

   Debe mostrar `Lote N: … aceptadas` cada 10 s. Sal con `Ctrl+C` (el puente sigue corriendo).

**Sin placa, para probar:** el simulador envía datos falsos. Después del punto 2 (con un nodo creado):

```powershell
docker compose run --rm -e AQUASENSE_TOKEN=EL_TOKEN app python tools/simulador_esp32.py --url http://app:8000 --mac AA:BB:CC:DD:EE:FF --ciclos 30
```

> Los datos del simulador se quedan en la base. Antes de empezar el historial real, bórralos (ver
> "Empezar de cero" al final).

---

## Paso 10. Publicar la página en internet

El túnel de Cloudflare publica la página con HTTPS sin abrir puertos del router. Hay dos opciones.

### Opción A: prueba rápida (sin cuenta, la URL cambia)

```powershell
docker compose --profile tunel-rapido up -d
```

```powershell
docker compose logs tunel-rapido
```

Busca una línea con `https://algo-al-azar.trycloudflare.com`. Agrega **ese nombre, sin `https://`**, a
`HOSTS_PERMITIDOS` en `.env`, y aplica con `docker compose up -d`. Abre esa URL desde un celular **con
datos móviles**.

Cada vez que se reinicia este túnel, la URL cambia y hay que actualizar `HOSTS_PERMITIDOS`. Para
apagarlo:

```powershell
docker compose stop tunel-rapido
```

### Opción B: URL fija (para la demo)

Necesitas una cuenta gratuita de Cloudflare y **un dominio propio** administrado en Cloudflare.

1. En <https://one.dash.cloudflare.com>: **Networks → Tunnels → Create a tunnel** → tipo
   **Cloudflared** → ponle un nombre (por ejemplo, `aquasense`).
2. En la pantalla de instalación, **no instales nada en Windows**: solo copia el **token** (el texto
   largo después de `--token` en cualquiera de los comandos de ejemplo).
3. En **Public Hostname**, agrega:
   - Subdominio: `aquasense`; dominio: el tuyo.
   - Service: tipo **HTTP**, URL **`app:8000`**.
4. En `.env`:

```
CLOUDFLARE_TUNNEL_TOKEN=EL_TOKEN_DEL_TUNEL
HOSTS_PERMITIDOS=localhost,127.0.0.1,192.168.1.50,aquasense.tudominio.com
```

5. Arranca:

```powershell
docker compose --profile tunel up -d
```

6. Abre `https://aquasense.tudominio.com` desde un celular con datos móviles.

> **No instales `cloudflared` como servicio de Windows** con Docker. Desde Windows, las peticiones
> llegarían por la red de Docker y la app no las reconocería como del túnel: se perderían la cookie
> segura, HSTS y el límite de intentos por persona. El túnel debe ir en su contenedor.

---

## Paso 11. Respaldos

El historial no se puede recuperar si se pierde. Haz un respaldo **diario y antes de cada demo**, guárdalo
**fuera de la laptop** (USB o nube), y **prueba la restauración** al menos una vez. Los comandos
probados están en **`docs/operacion.md`, sección 5**. Crea antes la carpeta `C:\Respaldos`, o cambia esa
ruta por la que uses.

---

## Paso 12. Compartir con el equipo

- Comparte la **URL** (de la opción A o B) y el **usuario y contraseña** de cada quien, por un medio
  privado. Nunca en el repositorio ni en grupos públicos.
- Desde la misma red WiFi también funciona `http://IP_DE_LA_LAPTOP:8010`.

---

## Uso diario

| Para | Comando |
|---|---|
| Ver si todo está arriba | `docker compose ps` |
| Ver los mensajes de la app | `docker compose logs -f app` |
| Reiniciar la app | `docker compose restart app` |
| Apagar todo (los datos se conservan) | `docker compose down` |
| Volver a encender | `docker compose up -d` |
| Actualizar a la versión nueva del código | `git pull` y luego `docker compose up -d --build` |

Al actualizar, las migraciones corren solas antes de arrancar la app. Haz un respaldo antes.

## Problemas comunes

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| Docker Desktop no arranca o habla de virtualización | Virtualización apagada en la BIOS | Actívala en la BIOS y reinicia |
| `docker compose up` dice que falta una variable | El `.env` no está completo | Revisa el Paso 3 |
| La página responde **"Bad Request"** (400) | La dirección no está en `HOSTS_PERMITIDOS` | Agrégala en `.env` y corre `docker compose up -d` |
| "Demasiadas peticiones" al entrar | 5 intentos de login fallidos en un minuto | Espera un minuto |
| `migraciones` termina con error o la app no arranca | Las contraseñas de `.env` no coinciden con las que MySQL guardó la primera vez | Revisa el Paso 3; si es una instalación nueva sin datos, `docker compose down -v` y vuelve a arrancar |
| El puerto 8010 está ocupado | Otro programa lo usa | Cambia `PUERTO_APP` en `.env`, y el puerto en la regla del firewall |
| El tanque aparece "Sin conexión" | El ESP32 o el puente no envían datos | `docker compose logs puente`. Revisa la IP del ESP32, que esté en el mismo WiFi y en 2.4 GHz |
| Desde el celular en el WiFi no carga `http://IP:8010` | Firewall o red marcada como pública | Revisa los puntos 2 y 6 del Paso 7 |
| La URL del túnel da error 1033 o no carga | El túnel no está corriendo | `docker compose logs tunel` (o `tunel-rapido`) |

## Empezar de cero (borra todo)

Solo si quieres eliminar **todos** los datos, por ejemplo los de prueba antes del historial real. Haz un
respaldo antes:

```powershell
docker compose down -v
```

```powershell
docker compose up -d --build --wait
```

Después repite el Paso 5 (usuarios), crea los tanques y vuelve a dar de alta el nodo del Paso 9: el token
anterior deja de existir.

## Lista final

- [ ] `docker compose ps` muestra `app` y `mysql` como **healthy**.
- [ ] La página abre en `http://localhost:8010` y en `http://IP_DE_LA_LAPTOP:8010` desde otro equipo del WiFi.
- [ ] Cada persona del equipo tiene su usuario.
- [ ] La laptop no se suspende y la IP está reservada en el router.
- [ ] La URL pública abre desde un celular con **datos móviles**.
- [ ] Hay al menos un respaldo guardado fuera de la laptop, y se probó su restauración.
- [ ] (Con la placa) El tanque aparece "En línea" y "Dispensar ahora" mueve el servo.
