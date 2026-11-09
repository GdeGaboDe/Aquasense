"""Protecciones de la exposición pública (CLAUDE.md, 10.1)."""

from fastapi import Request, status
from limits import parse
from slowapi import Limiter
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import obtener_settings
from app.servicios.errores import ErrorDeNegocio

_HSTS = "max-age=31536000; includeSubDomains"
_CSP = "; ".join(
    [
        "default-src 'self'",
        # Chart.js va fijado por versión en jsDelivr (ADR-006).
        "script-src 'self' https://cdn.tailwindcss.com https://cdn.jsdelivr.net",
        # Tailwind por CDN genera sus estilos en una etiqueta <style> (ADR-006).
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "connect-src 'self'",
        "base-uri 'self'",
        "form-action 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
    ]
)
# Solo se sirve en /docs, que únicamente existe con DOCS_PUBLICAS=true.
_CSP_DOCS = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "img-src 'self' data: https://fastapi.tiangolo.com",
        "frame-ancestors 'none'",
    ]
)

ENCABEZADOS_BASE = {
    "Content-Security-Policy": _CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
}


def ip_cliente(request: Request) -> str:
    """IP real: `CF-Connecting-IP` solo se cree si la conexión viene de cloudflared."""
    host = request.client.host if request.client else "desconocida"
    if host in obtener_settings().ips_proxy_confiables:
        return request.headers.get("cf-connecting-ip", host)
    return host


limitador = Limiter(key_func=ip_cliente)
LIMITE_LOGIN = "5/minute"
_LIMITE_API_WEB = parse("120/minute")


def limitar_api_web(request: Request) -> None:
    if not limitador.limiter.hit(_LIMITE_API_WEB, "api_web", ip_cliente(request)):
        raise ErrorDeNegocio(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "DEMASIADAS_PETICIONES",
            "Demasiadas peticiones. Espera un momento e inténtalo de nuevo.",
        )


class EncabezadosDeSeguridad:
    """Agrega los encabezados a toda respuesta y marca la cookie como Secure si llegó por HTTPS.

    La misma app se usa por HTTPS (túnel) y por HTTP (red local); con `Secure` fijo, el
    navegador no guardaría la cookie al entrar por la IP local.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        es_https = scope.get("scheme") == "https"
        ruta: str = scope.get("path", "")

        async def enviar(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                encabezados = MutableHeaders(scope=mensaje)
                for nombre, valor in ENCABEZADOS_BASE.items():
                    encabezados[nombre] = valor
                if ruta.startswith("/docs"):
                    encabezados["Content-Security-Policy"] = _CSP_DOCS
                # La API lleva datos de la sesión: nunca se guarda. La web se revalida siempre,
                # para que una actualización llegue sin que el usuario tenga que borrar la caché.
                es_api = ruta.startswith("/api/")
                encabezados.setdefault("Cache-Control", "no-store" if es_api else "no-cache")
                if es_https:
                    encabezados["Strict-Transport-Security"] = _HSTS
                    _marcar_cookies_seguras(encabezados)
            await send(mensaje)

        await self.app(scope, receive, enviar)


def _marcar_cookies_seguras(encabezados: MutableHeaders) -> None:
    cookies = encabezados.getlist("set-cookie")
    if not cookies:
        return
    del encabezados["set-cookie"]
    for cookie in cookies:
        encabezados.append("set-cookie", f"{cookie}; Secure")
