#!/usr/bin/env python3
"""Punto de entrada del bot y del servidor HTTP de la Mini App."""
from __future__ import annotations

import logging
import threading

from bot import main as run_bot
from web_server import run_web_server

LOG = logging.getLogger("gamaer.main")


def main() -> None:
    web_thread = threading.Thread(
        target=run_web_server,
        name="gamaer-miniapp",
        daemon=True,
    )
    web_thread.start()
    LOG.info("Mini App iniciada en paralelo; usando PORT asignado por Botkeep")
    run_bot()

if __name__ == "__main__":
    main()
