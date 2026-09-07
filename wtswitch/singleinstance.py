"""Защита от второго запуска через именованный мьютекс."""
from __future__ import annotations

import ctypes

ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    def __init__(self, name: str = "WinThemeSwitcher_Singleton") -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._handle = kernel32.CreateMutexW(None, False, name)
        self.acquired = ctypes.get_last_error() != ERROR_ALREADY_EXISTS

    def release(self) -> None:
        if self._handle:
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None
