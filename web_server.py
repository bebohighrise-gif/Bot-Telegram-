#!/usr/bin/env python3
"""Servidor HTTP mínimo para la Mini App y health check de Botkeep."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from aiohttp import web

LOG = logging.getLogger("gamaer.web")
WEB_ROOT = Path(__file__).resolve().parent / "webapp"
PORT = int(os.getenv("PORT", "8080"))
HOST = "0.0.0.0"


def create_app() -> web.Application:
    app = web.Application()

    async def health(_: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "service": "gamaer-city-miniapp"})

    async def index(_: web.Request) -> web.StreamResponse:
        return web.FileResponse(WEB_ROOT / "verification.html")

    app.router.add_get("/healthz", health)
    app.router.add_get("/", index)
    app.router.add_get("/verification.html", index)
    return app


def run_web_server() -> None:
    if not (WEB_ROOT / "verification.html").is_file():
        raise RuntimeError(f"No existe la Mini App: {WEB_ROOT / 'verification.html'}")
    LOG.info("Mini App escuchando en http://%s:%s", HOST, PORT)
    web.run_app(create_app(), host=HOST, port=PORT, handle_signals=False, print=None)


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
    run_web_server()
