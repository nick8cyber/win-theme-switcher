"""Определение координат по внешнему IP (ip-api.com). Опционально, с таймаутом."""
from __future__ import annotations

import json
import urllib.request

_URL = "http://ip-api.com/json/?fields=status,lat,lon,city&lang=ru"


def detect_by_ip(timeout: float = 6.0) -> tuple:
    """Возвращает (широта, долгота, название города). Бросает исключение при неудаче."""
    req = urllib.request.Request(_URL, headers={"User-Agent": "WinThemeSwitcher/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    if data.get("status") != "success":
        raise RuntimeError(data.get("message") or "служба геолокации недоступна")
    return float(data["lat"]), float(data["lon"]), str(data.get("city") or "")
