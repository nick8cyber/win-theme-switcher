"""Логика расписания: какая тема должна быть включена сейчас и когда следующее переключение.

Подход «поток событий»: собираем моменты переключений (восход/закат или
фиксированные точки) за соседние сутки и берём последнее прошедшее/первое
будущее относительно текущего момента. Это устойчиво к любым часовым поясам
и переходам через полночь.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from . import solar
from .config import Config, MODE_FIXED, MODE_OFF, MODE_SOLAR
from .theme import DARK, LIGHT


def parse_hhmm(value: str) -> Tuple[int, int]:
    """'07:30' -> (7, 30). Бросает ValueError при неверном формате."""
    parts = str(value).strip().split(":")
    if len(parts) != 2:
        raise ValueError(value)
    hours, minutes = int(parts[0]), int(parts[1])
    if not (0 <= hours < 24 and 0 <= minutes < 60):
        raise ValueError(value)
    return hours, minutes


def _minutes_of_day(value: str) -> int:
    h, m = parse_hhmm(value)
    return h * 60 + m


@dataclass(frozen=True)
class Switch:
    at: datetime
    theme: str  # тема, которая включится в момент *at*


def _events_for_day(cfg: Config, day: date) -> List[Tuple[datetime, str]]:
    """Плановые переключения за локальные сутки *day* (по возрастанию времени)."""
    events: List[Tuple[datetime, str]] = []
    if cfg.mode == MODE_SOLAR and cfg.lat is not None and cfg.lon is not None:
        rise, set_ = solar.sun_times(day, cfg.lat, cfg.lon)
        if rise:
            events.append((rise + timedelta(minutes=cfg.sunrise_offset), LIGHT))
        if set_:
            events.append((set_ + timedelta(minutes=cfg.sunset_offset), DARK))
        if events:
            return sorted(events)
        # полярный день/ночь или нет координат — запасной вариант: фиксированное время
    base = datetime(day.year, day.month, day.day).astimezone()  # локальная полночь
    events = [
        (base + timedelta(minutes=_minutes_of_day(cfg.light_time)), LIGHT),
        (base + timedelta(minutes=_minutes_of_day(cfg.dark_time)), DARK),
    ]
    return sorted(events)


def _event_stream(cfg: Config, now: datetime, days: int = 1) -> List[Tuple[datetime, str]]:
    """События за *days* суток до и после даты момента *now*, отсортированные."""
    events: List[Tuple[datetime, str]] = []
    for offset in range(-days, days + 1):
        events.extend(_events_for_day(cfg, (now + timedelta(days=offset)).date()))
    return sorted(events)


def _inverse(theme: str) -> str:
    return DARK if theme == LIGHT else LIGHT


def desired_mode(cfg: Config, now: datetime) -> Optional[str]:
    """Какая тема должна быть включена в момент *now* (None — расписание выключено)."""
    if cfg.mode == MODE_OFF:
        return None
    passed = [(at, th) for at, th in _event_stream(cfg, now) if at <= now]
    if passed:
        return passed[-1][1]
    upcoming = _event_stream(cfg, now)[0]
    return _inverse(upcoming[1])


def next_switch(cfg: Config, now: datetime) -> Optional[Switch]:
    """Ближайшее плановое переключение после момента *now*."""
    if cfg.mode == MODE_OFF:
        return None
    for at, th in _event_stream(cfg, now):
        if at > now:
            return Switch(at=at, theme=th)
    return None
