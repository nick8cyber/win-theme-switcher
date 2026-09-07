"""Чтение и переключение темы Windows через реестр (как это делает Auto Dark Mode).

Ключи: HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize
  AppsUseLightTheme    — тема приложений
  SystemUsesLightTheme — тема оболочки (панель задач, Пуск, проводник)
Изменения применяются сразу; рассылка WM_SETTINGCHANGE("ImmersiveColorSet")
помогает части приложений подхватить новую схему без перезапуска.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import winreg

_PERSONALIZE = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
_HWND_BROADCAST = 0xFFFF
_WM_SETTINGCHANGE = 0x001A
_SMTO_ABORTIFHUNG = 0x0002

LIGHT = "light"
DARK = "dark"


def _read_bool(name: str, default: bool = True) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _PERSONALIZE) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return bool(int(value))
    except OSError:
        return default


def _write(name: str, light: bool) -> None:
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _PERSONALIZE, 0,
                            winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, int(light))


def broadcast_change() -> None:
    res = wt.DWORD()
    ctypes.windll.user32.SendMessageTimeoutW(
        _HWND_BROADCAST, _WM_SETTINGCHANGE, 0, "ImmersiveColorSet",
        _SMTO_ABORTIFHUNG, 1000, ctypes.byref(res))


def current_apps_theme() -> str:
    return LIGHT if _read_bool("AppsUseLightTheme") else DARK


def current_system_theme() -> str:
    return LIGHT if _read_bool("SystemUsesLightTheme") else DARK


def current_theme(apps: bool = True, system: bool = True) -> str:
    """Текущая тема по тем разделам, которыми программа управляет."""
    if apps:
        return current_apps_theme()
    if system:
        return current_system_theme()
    return LIGHT


def set_theme(mode: str, apps: bool = True, system: bool = True) -> None:
    light = mode == LIGHT
    if apps:
        _write("AppsUseLightTheme", light)
    if system:
        _write("SystemUsesLightTheme", light)
    broadcast_change()
