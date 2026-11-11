#!/usr/bin/env python3
"""Punto de entrada compatible para Rust 133 Dev Blog."""
from bot import build_app, require_env


if __name__ == "__main__":
    require_env()
    build_app().run_polling(allowed_updates=__import__("telegram").Update.ALL_TYPES, drop_pending_updates=True)
