"""Иконка в системном трее (pystray): статус, ручное переключение, настройки, выход."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pystray

from .config import MODE_OFF
from .theme import DARK, LIGHT

_THEME_NAMES = {LIGHT: "светлая", DARK: "тёмная"}


class Tray:
    def __init__(self, app) -> None:
        self.app = app
        cfg = app.config
        from .theme import current_theme
        current = current_theme(cfg.apply_apps, cfg.apply_system)
        self._icon = pystray.Icon(
            "WinThemeSwitcher",
            app.tray_image(current, cfg.mode == MODE_OFF),
            title="Win Theme Switcher",
            menu=self._build_menu())
        self._thread = None

    def start(self) -> None:
        import threading
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        try:
            self._icon.stop()
        except Exception:
            pass

    # ---------- меню ----------

    def _build_menu(self) -> pystray.Menu:
        app = self.app
        return pystray.Menu(
            pystray.MenuItem("Открыть настройки", lambda *_: app.show_settings(), default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Светлая тема сейчас",
                             lambda *_: app.set_override(LIGHT)),
            pystray.MenuItem("Тёмная тема сейчас",
                             lambda *_: app.set_override(DARK)),
            pystray.MenuItem("Переключить тему", lambda *_: app.toggle_theme()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("По расписанию",
                             lambda item: app.toggle_schedule(),
                             checked=lambda item: app.schedule_enabled()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", lambda *_: app.quit()),
        )

    def rebuild_menu(self) -> None:
        self._icon.menu = self._build_menu()
        try:
            self._icon.update_menu()
        except Exception:
            pass

    # ---------- состояние ----------

    def update_state(self, current: str, disabled: bool,
                     nxt: Optional[object]) -> None:
        try:
            self._icon.image = self.app.tray_image(current, disabled)
        except Exception:
            pass
        parts = ["Win Theme Switcher"]
        if disabled:
            parts.append("расписание выключено")
        else:
            parts.append(f"тема: {_THEME_NAMES.get(current, current)}")
            if nxt:
                parts.append(f"далее: {_THEME_NAMES[nxt.theme]} в {nxt.at:%H:%M}")
        try:
            self._icon.title = "  ·  ".join(parts)
            self._icon.update_menu()
        except Exception:
            pass
