# ADR-003: Polling en lugar de WebSockets o MQTT

**Estado:** aceptada · **Fecha:** 2026-11-05

## Contexto

El ESP32 manda lecturas cada 10 s y necesita recibir comandos. La web muestra datos casi en vivo y el
estado de un comando en curso.

## Decisión

Todo por HTTP con polling:

| Quién | Qué consulta | Cada cuánto |
|---|---|---|
| ESP32 | Telemetría (`POST`) | 10 s |
| ESP32 | Configuración y comandos | 5 s |
| Web | Panel general | 10 s |
| Web | Comando en curso | 3 s, solo mientras dura |
| Web | Gráficas | 60 s |

Los intervalos de la web vienen del servidor (`POLLING_*`), no fijos en el JavaScript.

## Razones

- Un comando tarda como máximo unos 5 s en llegar al nodo, más que suficiente para alimentar peces.
- **Sin infraestructura extra:** no hay broker MQTT ni conexiones abiertas que mantener, y el túnel de
  Cloudflare funciona sin configuración especial.
- **Más fácil para el firmware:** el ESP32 maneja peticiones HTTP simples mejor que una conexión
  persistente, y si se cae la red reintenta sin perder estado.

## Consecuencias

- **El polling se pausa** cuando la pestaña no está visible. Al volver, solo se consulta si ya pasó el
  intervalo: cambiar de app seguido en el celular no multiplica las peticiones.
- **Límite por IP:** la API web acepta 120 peticiones por minuto. La pantalla más pesada, el detalle del
  tanque con 6 gráficas, queda muy por debajo.
- **Cada pestaña abierta genera tráfico,** también las que están en internet. Por eso los intervalos son
  configurables.
