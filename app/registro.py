"""Logs estructurados en JSON (CLAUDE.md, 10.2). Nunca registrar contraseñas, tokens ni cookies."""

import json
import logging
from datetime import UTC, datetime


class FormatoJson(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "momento": datetime.fromtimestamp(record.created, UTC).isoformat(),
                "nivel": record.levelname,
                "origen": record.name,
                "mensaje": record.getMessage(),
            },
            ensure_ascii=False,
        )


def configurar_registro() -> None:
    manejador = logging.StreamHandler()
    manejador.setFormatter(FormatoJson())
    raiz = logging.getLogger()
    raiz.handlers = [manejador]
    raiz.setLevel(logging.INFO)
