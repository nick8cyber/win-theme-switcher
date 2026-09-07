"""Расчёт восхода и заката по алгоритму NOAA ("General Solar Position Calculations").

Возвращает локальное время с учётом часового пояса и перевода часов системы.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Tuple

# 90.833° = сумеречный зенит: центр солнца на 50' под горизонтом (рефракция + диск)
ZENITH_OFFICIAL = 90.833


def _event_instant(utc_hours: float, day: date) -> datetime:
    """Момент события, приходящийся на локальные сутки *day*.

    utc_hours может быть отрицательным или больше 24 (восточные/западные
    долготы), поэтому перебираем соседние UTC-дни и берём вариант,
    попадающий в запрошенные локальные сутки.
    """
    base = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    day_start = datetime(day.year, day.month, day.day).astimezone()  # локальная полночь
    day_end = day_start + timedelta(days=1)
    for k in (-1, 0, 1):
        candidate = base + timedelta(hours=utc_hours + 24 * k)
        if day_start <= candidate < day_end:
            return candidate.astimezone()
    # полярные широты/вырожденные случаи: ближайший по времени вариант
    nearest = min((base + timedelta(hours=utc_hours + 24 * k) for k in (-1, 0, 1)),
                  key=lambda c: abs((c - day_start).total_seconds()))
    return nearest.astimezone()


def sun_times(day: date, lat: float, lon: float,
              zenith: float = ZENITH_OFFICIAL) -> Tuple[Optional[datetime], Optional[datetime]]:
    """(восход, закат) в локальном времени для даты *day*.

    None означает полярный день или ночь для соответствующего события.
    """
    day_of_year = day.timetuple().tm_yday
    lng_hour = lon / 15.0

    def event(t: float, rising: bool) -> Optional[datetime]:
        mean_anomaly = (0.9856 * t) - 3.289
        true_long = (mean_anomaly
                     + 1.916 * math.sin(math.radians(mean_anomaly))
                     + 0.020 * math.sin(math.radians(2 * mean_anomaly))
                     + 282.634) % 360.0
        # прямое восхождение с поправкой на квадрант
        ra = math.degrees(math.atan(0.91764 * math.tan(math.radians(true_long)))) % 360.0
        ra += (true_long // 90) * 90 - (ra // 90) * 90
        ra /= 15.0
        # склонение солнца
        sin_dec = 0.39782 * math.sin(math.radians(true_long))
        cos_dec = math.cos(math.asin(sin_dec))
        cos_h = (math.cos(math.radians(zenith))
                 - sin_dec * math.sin(math.radians(lat))) / (cos_dec * math.cos(math.radians(lat)))
        if cos_h > 1.0 or cos_h < -1.0:
            return None  # солнце не восходит / не заходит
        hour_angle = (360.0 - math.degrees(math.acos(cos_h))) if rising else math.degrees(math.acos(cos_h))
        hour_angle /= 15.0
        local_mean = hour_angle + ra - 0.06571 * t - 6.622
        ut = local_mean - lng_hour
        return _event_instant(ut, day)

    t_rise = day_of_year + (6.0 - lng_hour) / 24.0
    t_set = day_of_year + (18.0 - lng_hour) / 24.0
    return event(t_rise, True), event(t_set, False)
