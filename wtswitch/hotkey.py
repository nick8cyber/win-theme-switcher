"""Глобальная горячая клавиша: RegisterHotKey + цикл сообщений в отдельном потоке."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import threading
from typing import Callable, Optional

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

_MODIFIERS = {"ctrl": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT, "win": MOD_WIN}


def parse_combo(combo: str) -> Optional[tuple]:
    """'ctrl+alt+d' -> (модификаторы, виртуальный код клавиши)."""
    try:
        parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
        if not parts:
            return None
        key = parts[-1]
        mods = 0
        for part in parts[:-1]:
            if part not in _MODIFIERS:
                return None
            mods |= _MODIFIERS[part]
        if len(key) == 1 and key.isalnum():
            vk = ord(key.upper())
        elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
            vk = 0x70 + int(key[1:]) - 1
        else:
            return None
        if mods == 0:
            return None  # без модификаторов глобально перехватит обычную клавишу
        return mods, vk
    except (ValueError, AttributeError):
        return None


class HotkeyThread:
    """Регистрирует горячую клавишу; при нажатии вызывает колбэк (из своего потока)."""

    def __init__(self, combo: str, on_trigger: Callable[[], None],
                 on_error: Optional[Callable[[str], None]] = None) -> None:
        self._combo = combo
        self._on_trigger = on_trigger
        self._on_error = on_error
        self._thread: Optional[threading.Thread] = None
        self._thread_id = 0
        self.failed = False

    def start(self) -> None:
        parsed = parse_combo(self._combo)
        if parsed is None:
            self._fail(f"Не удалось разобрать комбинацию «{self._combo}»")
            return
        self._thread = threading.Thread(target=self._run, args=parsed, daemon=True)
        self._thread.start()

    def _fail(self, message: str) -> None:
        self.failed = True
        if self._on_error:
            self._on_error(message)

    def _run(self, mods: int, vk: int) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        if not user32.RegisterHotKey(None, 1, mods, vk):
            self._fail(f"Комбинация «{self._combo}» занята другим приложением")
            return
        self._thread_id = kernel32.GetCurrentThreadId()
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam == 1:
                self._on_trigger()
        user32.UnregisterHotKey(None, 1)

    def stop(self) -> None:
        if self._thread_id:
            ctypes.windll.kernel32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            self._thread_id = 0
