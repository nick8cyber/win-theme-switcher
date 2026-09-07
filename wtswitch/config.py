"""Настройки приложения: хранятся в %APPDATA%\\WinThemeSwitcher\\settings.json."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from typing import Optional

APP_NAME = "WinThemeSwitcher"

MODE_FIXED = "fixed"   # по фиксированному времени
MODE_SOLAR = "solar"   # по восходу и закату
MODE_OFF = "off"       # расписание выключено, только ручное переключение


def config_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def config_path() -> str:
    return os.path.join(config_dir(), "settings.json")


@dataclass
class Config:
    mode: str = MODE_FIXED
    light_time: str = "08:00"    # когда включать светлую тему (режим fixed)
    dark_time: str = "23:00"     # когда включать тёмную тему (режим fixed)
    sunrise_offset: int = 0      # минуты относительно восхода (режим solar)
    sunset_offset: int = 0       # минуты относительно заката (режим solar)
    lat: Optional[float] = None
    lon: Optional[float] = None
    apply_apps: bool = True      # тема приложений
    apply_system: bool = True    # тема оболочки (панель задач, Пуск)
    enforce: bool = True         # возвращать тему, если её поменяли вручную
    hotkey_enabled: bool = True
    hotkey: str = "ctrl+alt+d"   # глобальная горячая клавиша
    start_with_windows: bool = False
    start_minimized: bool = True

    @classmethod
    def load(cls) -> "Config":
        cfg = cls()
        try:
            with open(config_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            known = {f.name for f in fields(cls)}
            for key, value in data.items():
                if key in known:
                    setattr(cfg, key, value)
        except (OSError, ValueError):
            pass
        return cfg

    def save(self) -> None:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        """Собрать и провалидировать настройки из UI. ValueError — с текстом для пользователя."""
        import re

        from .hotkey import parse_combo

        cfg = cls()
        mode = str(data.get("mode", cfg.mode))
        if mode not in (MODE_FIXED, MODE_SOLAR, MODE_OFF):
            raise ValueError("Неизвестный режим расписания")
        cfg.mode = mode

        def time_of(key: str, default: str) -> str:
            value = str(data.get(key, default)).strip()
            if not re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", value):
                raise ValueError(f"Неверное время «{value}» — укажите ЧЧ:ММ")
            h, m = value.split(":")
            return f"{int(h):02d}:{int(m):02d}"

        cfg.light_time = time_of("light_time", cfg.light_time)
        cfg.dark_time = time_of("dark_time", cfg.dark_time)

        def int_of(key: str, default: int) -> int:
            try:
                value = int(str(data.get(key, default)))
            except (TypeError, ValueError):
                raise ValueError("Смещение должно быть целым числом минут")
            return max(-720, min(720, value))

        cfg.sunrise_offset = int_of("sunrise_offset", 0)
        cfg.sunset_offset = int_of("sunset_offset", 0)

        def coord(key: str):
            value = data.get(key)
            if value in (None, ""):
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                raise ValueError("Координаты должны быть числами")

        cfg.lat = coord("lat")
        cfg.lon = coord("lon")
        if cfg.lat is not None and not -90 <= cfg.lat <= 90:
            raise ValueError("Широта — число от -90 до 90")
        if cfg.lon is not None and not -180 <= cfg.lon <= 180:
            raise ValueError("Долгота — число от -180 до 180")
        if cfg.mode == MODE_SOLAR and (cfg.lat is None or cfg.lon is None):
            raise ValueError("Для режима «Солнце» задайте координаты (или определите по IP)")

        if not (data.get("apply_apps") or data.get("apply_system")):
            raise ValueError("Выберите хотя бы одну цель: приложения или оболочка")
        cfg.apply_apps = bool(data.get("apply_apps"))
        cfg.apply_system = bool(data.get("apply_system"))
        cfg.enforce = bool(data.get("enforce"))
        cfg.hotkey_enabled = bool(data.get("hotkey_enabled"))
        cfg.hotkey = str(data.get("hotkey", cfg.hotkey)).lower()
        if cfg.hotkey_enabled and parse_combo(cfg.hotkey) is None:
            raise ValueError("Неверная комбинация горячей клавиши")
        cfg.start_with_windows = bool(data.get("start_with_windows"))
        cfg.start_minimized = bool(data.get("start_minimized"))
        return cfg
