"""Ядро приложения: Qt-цикл, окно настроек, поток расписания, трей, горячая клавиша."""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, Signal

from . import autostart, schedule, theme
from .config import Config, MODE_OFF
from .hotkey import HotkeyThread
from .icons import moon_icon, sun_icon
from .theme import DARK, LIGHT

POLL_SECONDS = 20


class Marshaler(QObject):
    """Безопасный вызов функций в главном (Qt) потоке из любых фоновых потоков."""

    call = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.call.connect(self._run)

    def _run(self, fn) -> None:
        try:
            fn()
        except Exception:
            logging.exception("ошибка задачи главного потока")

    def submit(self, fn) -> None:
        self.call.emit(fn)


class App:
    def __init__(self) -> None:
        self.config: Config = Config.load()
        self.override: Optional[str] = None      # ручное переключение до следующего события
        self.last_desired: Optional[str] = None  # прошлая плановая тема (для enforce=False)
        self.hotkey_error: str = ""
        self._last_active_mode: str = self.config.mode if self.config.mode != MODE_OFF else "fixed"
        self._poll_stop = threading.Event()
        self._hotkey: Optional[HotkeyThread] = None
        self.tray = None
        self.win = None
        self.qapp = None
        self.marshaler: Optional[Marshaler] = None

    # ---------- запуск / остановка ----------

    def run(self) -> None:
        from PySide6.QtWidgets import QApplication

        self.qapp = QApplication([])
        self.qapp.setStyle("Fusion")
        self.qapp.setApplicationName("Win Theme Switcher")
        import os
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "assets", "icon.ico")
        if os.path.exists(icon_path):
            from PySide6.QtGui import QIcon
            self.qapp.setWindowIcon(QIcon(icon_path))  # иконка диалогов и таскбара
        self.marshaler = Marshaler()

        from .gui import SettingsWindow
        from .tray import Tray

        self.tray = Tray(self)
        self.tray.start()
        self._start_hotkey()
        threading.Thread(target=self._poll_loop, daemon=True).start()

        self.win = SettingsWindow(self)
        if not self.config.start_minimized:
            self.win.show_and_center()
        self._refresh_ui()

        self.qapp.exec()
        self._shutdown()

    def quit(self) -> None:
        logging.info("выход")
        self._poll_stop.set()
        if self.qapp:
            self.qapp.quit()

    def _shutdown(self) -> None:
        self._poll_stop.set()
        if self._hotkey:
            self._hotkey.stop()
        if self.tray:
            self.tray.stop()

    # ---------- фоновый цикл расписания ----------

    def _poll_loop(self) -> None:
        while not self._poll_stop.is_set():
            try:
                self._tick()
            except Exception:
                logging.exception("ошибка в цикле расписания")
            self._poll_stop.wait(POLL_SECONDS)

    def _tick(self) -> None:
        now = datetime.now().astimezone()
        cfg = self.config
        dirty = False

        if cfg.mode != MODE_OFF and self.override:
            nxt = schedule.next_switch(cfg, now)
            if nxt and now >= nxt.at:
                self.override = None  # плановый момент наступил — возвращаемся к расписанию
                dirty = True

        if cfg.mode == MODE_OFF:
            desired = None
        elif self.override:
            desired = self.override
        else:
            desired = schedule.desired_mode(cfg, now)

        if desired is not None:
            current = theme.current_theme(cfg.apply_apps, cfg.apply_system)
            should_apply = cfg.enforce or desired != self.last_desired
            if should_apply and current != desired:
                logging.info("применяю тему %s (override=%s)", desired, self.override)
                theme.set_theme(desired, cfg.apply_apps, cfg.apply_system)
                dirty = True
        self.last_desired = desired
        if dirty:
            self.marshaler.submit(self._refresh_ui)

    # ---------- публичные действия (трей, хоткей, GUI) ----------

    def marshal(self, fn) -> None:
        """Выполнить fn в главном потоке (безопасно из любого потока)."""
        if self.marshaler:
            self.marshaler.submit(fn)

    def set_override(self, mode: str) -> None:
        """Ручное переключение: действует до следующего планового события."""
        def _do():
            logging.info("ручное переключение: %s", mode)
            self.override = mode
            theme.set_theme(mode, self.config.apply_apps, self.config.apply_system)
            self._refresh_ui()
        self.marshal(_do)

    def toggle_theme(self) -> None:
        current = theme.current_theme(self.config.apply_apps, self.config.apply_system)
        self.set_override(DARK if current == LIGHT else LIGHT)

    def apply_config(self, cfg: Config) -> None:
        """Применить новые настройки из окна и сохранить их."""
        def _do():
            self.config = cfg
            cfg.save()
            logging.info("настройки сохранены: режим=%s светлая=%s тёмная=%s",
                         cfg.mode, cfg.light_time, cfg.dark_time)
            self.override = None
            self.last_desired = None
            autostart.set_enabled(cfg.start_with_windows)
            self._start_hotkey()
            if self.tray:
                self.tray.rebuild_menu()
            self._tick()
            self._refresh_ui()
        self.marshal(_do)

    def show_settings(self) -> None:
        def _show():
            if self.win:
                self.win.show_and_center()
        self.marshal(_show)

    def schedule_enabled(self) -> bool:
        return self.config.mode != MODE_OFF

    def toggle_schedule(self) -> None:
        """Переключатель в трее: выкл/вкл расписание (режим запоминаем)."""
        cfg = self.config
        if cfg.mode == MODE_OFF:
            cfg.mode = self._last_active_mode
        else:
            self._last_active_mode = cfg.mode
            cfg.mode = MODE_OFF
        self.apply_config(cfg)

    # ---------- внутреннее ----------

    def _refresh_ui(self) -> None:
        """Обновить иконку/меню трея и окно настроек (главный поток)."""
        cfg = self.config
        now = datetime.now().astimezone()
        current = theme.current_theme(cfg.apply_apps, cfg.apply_system)
        nxt = schedule.next_switch(cfg, now) if cfg.mode != MODE_OFF else None
        if self.tray:
            self.tray.update_state(current, cfg.mode == MODE_OFF, nxt)
        if self.win:
            self.win.refresh_status(current, self.override, nxt, self.hotkey_error)

    def _start_hotkey(self) -> None:
        if self._hotkey:
            self._hotkey.stop()
        self.hotkey_error = ""
        if self.config.hotkey_enabled:
            self._hotkey = HotkeyThread(self.config.hotkey, self.toggle_theme,
                                        on_error=lambda msg: self.marshal(
                                            lambda: self._set_hotkey_error(msg)))
            self._hotkey.start()

    def _set_hotkey_error(self, msg: str) -> None:
        self.hotkey_error = msg
        self._refresh_ui()

    # ---------- иконки ----------

    def tray_image(self, current: str, disabled: bool):
        if current == DARK and not disabled:
            return moon_icon(64)
        return sun_icon(64, disabled=disabled)
