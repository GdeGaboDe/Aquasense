# ADR-006: Tailwind y Chart.js por CDN

**Estado:** aceptada · **Fecha:** 2026-11-05 · **Actualizada:** 2026-11-08 (Chart.js)

## Contexto

La web es pequeña: siete páginas en HTML con JavaScript sin frameworks. Instalar Node.js solo para
compilar CSS agregaría una herramienta que el resto del proyecto no usa (ADR-001).

## Decisión

- **Tailwind** desde `cdn.tailwindcss.com`, que genera los estilos en el navegador.
- **Chart.js 4.6.1** desde `cdn.jsdelivr.net`, fijado por versión exacta, solo en el detalle del tanque.

## Razones

- **Sin paso de compilación:** se editan los archivos de `web/` y basta con recargar.
- **Es un proyecto académico** con una sola instalación, no un producto con miles de usuarios.

## Consecuencias

- **Avisos en la consola:** Tailwind advierte que su CDN no es para producción. Es esperado.
- **CSP con excepciones:** la política permite esos dos dominios en `script-src`, y `'unsafe-inline'` en
  `style-src`, porque Tailwind inyecta una etiqueta `<style>`. Los scripts siguen siendo solo archivos;
  ningún dato del servidor se pinta con `innerHTML`.
- **Riesgo aceptado:** no hay hash de integridad (SRI). Si el CDN sirviera un archivo alterado, se
  ejecutaría en la página. Chart.js va fijado por versión para reducir ese riesgo; Tailwind por CDN no
  publica un archivo estable que se pueda fijar.
- **Hace falta internet para dar estilo:** sin acceso al CDN, la web funciona pero sin estilos de
  Tailwind. `web/css/app.css` mantiene lo esencial: el foco visible y los elementos ocultos.
- **Si hiciera falta,** el paso a producción sería compilar Tailwind con su CLI y servir ambos archivos
  desde `web/`.
