# Lista de verificación antes de cada demo

Hazla completa el día anterior y repite la sección 3 una hora antes. Lleva el celular **con datos
móviles y sin WiFi**: así se prueba lo mismo que verá cualquier persona fuera de la red local.

## 1. En la laptop

- [ ] Respaldo de hoy hecho **y restaurado** en una base de prueba (`docs/operacion.md`, sección 5).
- [ ] La laptop está conectada a la corriente y no se suspende.
- [ ] `http://localhost:8000/health` responde `"base_de_datos":"conectada"`, y es AquaSense, no otro
      programa en el mismo puerto.
- [ ] `cloudflared` está corriendo y la URL pública está en `HOSTS_PERMITIDOS`.
- [ ] El nodo autónomo está encendido y en la misma red; su última lectura tiene menos de 30 s.
- [ ] La tolva tiene alimento y el tanque tiene agua.

## 2. Pruebas automáticas

- [ ] `ruff check .` y `ruff format --check .` sin avisos.
- [ ] `pytest` en verde contra MySQL.
- [ ] La rama que se presenta tiene una etiqueta de versión (`git tag`).

## 3. En el celular, con datos móviles

- [ ] La URL pública abre por **HTTPS** y muestra el login.
- [ ] Una contraseña incorrecta muestra "Usuario o contraseña incorrectos." sin dar detalles.
- [ ] El login correcto abre el panel.
- [ ] Cada tanque muestra sus valores, el estado "En línea" y la hora del último dato.
- [ ] Los valores cambian solos en unos 10 s.
- [ ] **Alertas:** al sacar el flotador del agua aparece "Nivel de agua bajo" en el panel y en Alertas, y
      se resuelve sola al regresarlo.
- [ ] **Alimentación:** "Dispensar ahora" con 1 carga pasa de "Enviando…" a "Listo: alimentación
      confirmada", el servo se mueve y la dosis aparece en la bitácora en unos 10 s.
- [ ] Un segundo "Dispensar" inmediato muestra el aviso de alimentación en curso, y **no** da doble ración.
- [ ] **Ajustes:** cambiar un parámetro muestra "Pendiente de aplicar", y el aviso desaparece cuando el
      nodo lo aplica.
- [ ] **Detalle del tanque:** las gráficas cargan en 6 h, 24 h y 7 días.
- [ ] **Predicción:** muestra los días estimados y la referencia por historial. Si aún no hay 24 h de datos
      del ciclo actual, dice "Estimación aún no confiable"; nunca muestra un número inventado.
- [ ] "Cerrar sesión" regresa al login, y al usar el botón Atrás vuelve a pedir el login.

## 4. Plan de respaldo para el día de la demo

- [ ] Si falla el túnel con nombre: Quick Tunnel y su URL nueva en `HOSTS_PERMITIDOS` (reiniciar la app).
- [ ] Si falla el hardware: el simulador con `python tools/simulador_esp32.py`.
- [ ] Si falla internet en el salón: la web por la IP local de la laptop, desde un celular en la misma red.
