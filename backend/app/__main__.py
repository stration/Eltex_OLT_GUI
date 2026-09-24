"""Точка входа для запуска LTP-GUI.

Используется:
  - PyInstaller (build_exe.bat передаёт этот файл как entry point)
  - python -m app  (в dev-режиме)

Почему не app/main.py:
  PyInstaller не поддерживает относительные импорты внутри `main.py`,
  запущенного как скрипт (нет __package__). А __main__.py запускается
  ВНУТРИ пакета app, и все `from .xxx` в main.py работают корректно.
"""
import sys
import uvicorn

from app.config import APP_NAME, APP_VERSION
from app.main import app, ARGS, _is_frozen
from loguru import logger


def main():
    logger.info(
        f"Starting uvicorn on {ARGS.host}:{ARGS.port} "
        f"(frozen={_is_frozen()})"
    )
    uvicorn.run(
        app,
        host=ARGS.host,
        port=ARGS.port,
        reload=False,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()