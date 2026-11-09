# Conectar el ESP32 con el firmware actual

El firmware actual del equipo es un **servidor web**: el ESP32 sirve su propia página y expone tres
rutas. AquaSense espera lo contrario, que el nodo le envíe los datos (`docs/contrato-api.md`). Para no
cambiar el firmware, `tools/puente_esp32.py` corre en la laptop y hace de nodo autónomo.

```
ESP32 (firmware web) ◄── /datos, /abrir, /cerrar ── puente (laptop) ── telemetría, config, ACK ──► AquaSense
```

| Ruta del firmware | Para qué la usa el puente |
|---|---|
| `GET /datos` | Lectura de sensores cada 10 s |
| `GET /abrir` | Abrir la tolva al dispensar |
| `GET /cerrar` | Cerrarla después de `TIEMPO_APERTURA_DISPENSA` |

## Pasos

1. **Misma red.** El firmware se conecta al WiFi escrito en su código (`ssid`, `password`). La laptop debe
   estar en esa misma red, en 2.4 GHz.
2. **IP del ESP32.** Al arrancar, el monitor serie (115200 baudios) imprime
   `Abre en tu navegador: http://<IP>`. Abre esa dirección: debe verse la página del ESP32. **Reserva esa
   IP en el router** para que no cambie.
3. **MAC.** El firmware no la imprime; búscala en la lista de equipos conectados del router. AquaSense solo
   la usa como identificador, así que cualquier MAC única sirve mientras sea la misma en los pasos 4 y 5.
4. **Alta del nodo.** Con la app corriendo:

   ```bash
   docker compose run --rm app python -m tools.crear_nodo --mac <MAC> --nombre Principal --tanque <nombre> --volumen-l <litros> --usuario <admin>
   ```

   Copia el token que muestra; no se vuelve a ver.
5. **Configura el puente** en `.env`:

   ```
   PUENTE_ESP32=http://<IP del ESP32>
   PUENTE_MAC=<MAC>
   AQUASENSE_TOKEN=<token>
   ```

6. **Arráncalo:**

   ```bash
   docker compose --profile puente up -d --build
   ```

   Sin Docker: `python tools/puente_esp32.py --servidor http://localhost:8000` (lee las mismas variables).
7. **Comprueba:**
   - En el panel, el tanque aparece "En línea" con luz, TDS, nivel de agua y tolva.
   - `docker compose logs -f puente` muestra `Lote N: … aceptadas`.
   - En Ajustes → Umbrales define el máximo de TDS, para tener alertas y predicción.
   - En Alimentación, "Dispensar ahora" con 1 carga: el servo abre, cierra y aparece "Listo".

## Qué se traduce

| Dato del firmware (`/datos`) | Variable en AquaSense |
|---|---|
| `ldr` | `nivel_luz_adc` |
| `ldr_est` ("Oscuridad Total", "Luz Tenue", "Luz Brillante") | `luz_clase` (0, 1, 2) |
| `tds` | `tds_ppm` |
| `agua_est` contiene "BAJO" | `flotador_bajo` = 1 |
| `comida_est` contiene "ALERTA" | `tolva_vacia` = 1 |
| `dist` (si es −1, no hubo eco y no se envía) | `distancia_tolva_cm` |

El puente anuncia los módulos `luz`, `tds`, `flotador`, `tolva` y `servo`. El firmware no tiene sensor de
temperatura ni de turbidez, así que esas gráficas no aparecen.

## Qué parámetros tienen efecto

| Parámetro | ¿Funciona? |
|---|---|
| `TIEMPO_APERTURA_DISPENSA` | Sí: cuánto tiempo queda abierta la tolva por carga |
| `MODO_DISPENSA`, `INTERVALO_ALIMENTACION_HORAS`, `CANTIDAD_CARGAS` | Sí: el puente hace la alimentación automática, que el firmware no tiene |
| `ANGULO_REPOSO_SERVO`, `ANGULO_DISPENSA_SERVO` | No: el firmware los fija en 10° y 75° |
| `UMBRAL_LUZ_OSCURIDAD`, `UMBRAL_LUZ_MODERADA` | No: el firmware usa 800 y 2400 |
| `DISTANCIA_TOLVA_VACIA` | No: el firmware usa 15 cm, igual que el valor de fábrica |
| `COEF_CALIBRACION_TDS`, `VOLTAJE_REFERENCIA_ADC`, `INTERVALO_ENVIO_S` | No |

La alarma la maneja el propio firmware (buzzer con agua baja, LED con tolva vacía). Por eso no se
anuncia el módulo `alarma`, y la web no muestra "Silenciar alarma".

## Comportamiento ante fallas

- **ESP32 sin respuesta:** el puente no envía nada. El panel marca "sin conexión" a los 30 s, y no se
  piden órdenes que no se podrían ejecutar: un "Dispensar" pendiente expira a los 120 s y abre una alerta.
- **Servidor caído:** el puente guarda hasta una hora de lecturas y las reenvía al volver.
- **Falla al abrir:** se detiene y reporta el comando como fallido: mejor no dispensar que dar doble
  ración.
- **Falla al cerrar:** reintenta tres veces. Si no lo logra, el ACK avisa que la tolva pudo quedar abierta.
- **Reinicio del puente:** en modo automático espera un intervalo completo antes de la primera ración.

## Riesgos que conviene conocer

- `/abrir` y `/cerrar` no piden contraseña: cualquiera en esa red WiFi puede mover el servo.
- Si el puente se detiene justo entre `/abrir` y `/cerrar`, la tolva se queda abierta hasta la siguiente
  orden. Conviene que el firmware cierre solo tras unos segundos.
- La fórmula de TDS del firmware no compensa la temperatura. Si da más de 2,000 ppm (sonda fuera del agua
  o mal conectada), el servidor rechaza esa lectura por estar fuera del rango físico.
- Las credenciales del WiFi están escritas en el firmware: no lo subas a un repositorio público.

## Estado de la verificación

El puente se probó contra un ESP32 simulado que responde con los mismos campos y textos que este
firmware. **No se ha probado con la placa real.** Al conectarla, sigue los pasos de "Comprueba" y revisa
`docker compose logs puente`.
