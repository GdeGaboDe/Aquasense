# ADR-005: Publicación por Cloudflare Tunnel desde la laptop

**Estado:** aceptada · **Fecha:** 2026-11-05

## Contexto

La web debe abrirse desde cualquier lugar, incluido un celular con datos móviles. El servidor es una
laptop en una red doméstica, sin IP pública fija y sin acceso a la configuración del router del
proveedor. No hay presupuesto para hosting.

## Decisión

`cloudflared` abre una conexión saliente desde la laptop hacia Cloudflare, que entrega una URL pública
con HTTPS. **El ESP32 siempre usa la IP local** de la laptop, nunca la URL pública.

| Modo | Uso |
|---|---|
| Túnel con nombre (cuenta gratuita y dominio propio) | Demo y entrega: URL fija |
| Quick Tunnel (`trycloudflare.com`, sin cuenta) | Pruebas: la URL cambia en cada reinicio |

## Razones

- **Sin abrir puertos en el router:** la laptop no queda expuesta directamente.
- **HTTPS sin administrar certificados.**
- **El sistema sigue funcionando sin internet:** el ESP32 habla por la red local. El túnel tampoco
  consume cuota con la telemetría.
- No se usa ngrok gratuito: su límite mensual de peticiones se agota con el polling, y muestra una página
  de advertencia.

## Consecuencias

- **La API del dispositivo solo acepta la red local:** responde `403` a lo que llega por el túnel (trae
  `CF-Connecting-IP` o `X-Forwarded-For`) o desde una IP pública (`DISPOSITIVO_SOLO_LAN`).
- **La IP real del cliente** se toma de `CF-Connecting-IP` solo si la conexión viene de `127.0.0.1`.
  Uvicorn arranca con `--proxy-headers --forwarded-allow-ips 127.0.0.1`.
- **`HOSTS_PERMITIDOS`** debe incluir la URL pública; con el Quick Tunnel hay que actualizarla en cada
  reinicio.
- **Riesgo aceptado:** el tramo ESP32–laptop va por HTTP dentro de la red local, porque el ESP32 no maneja
  bien TLS. Ese tramo nunca sale a internet.
- **Si la laptop se apaga, la URL deja de responder.** El ESP32 sigue guardando en LittleFS y reenvía al
  volver. La laptop debe quedarse encendida, sin suspenderse (ver `docs/operacion.md`).
