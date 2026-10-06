"""Точка входа Win Theme Switcher."""
from __future__ import annotations

import ctypes
import logging
import os
import sys


def _setup_logging() -> None:
    from logging.handlers import RotatingFileHandler

    from wtswitch.config import config_dir
    handler = RotatingFileHandler(
        os.path.join(config_dir(), "log.txt"),
        maxBytes=256 * 1024, backupCount=1, encoding="utf-8")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[handler])


def main() -> int:
    from wtswitch.singleinstance import SingleInstance
    instance = SingleInstance()
    if not instance.acquired:
        ctypes.windll.user32.MessageBoxW(
            0,
            "Win Theme Switcher уже запущен — ищите значок в системном трее.",
            "Win Theme Switcher",
            0x40)  # MB_ICONINFORMATION
        return 0

    _setup_logging()
    logging.info("запуск (python %s)", sys.version.split()[0])

    from wtswitch.app import App
    app = App()
    try:
        app.run()
    except Exception:
        logging.exception("критическая ошибка")
        raise
    finally:
        instance.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())
