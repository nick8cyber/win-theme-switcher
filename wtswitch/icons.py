"""Генерация иконок (солнце/луна) для трея и окна приложения средствами Pillow."""
from __future__ import annotations

from PIL import Image, ImageDraw

_SUN_COLOR = (255, 190, 60, 255)
_SUN_DISABLED = (150, 150, 150, 255)
_MOON_COLOR = (200, 210, 235, 255)


def sun_icon(size: int = 64, disabled: bool = False) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = _SUN_DISABLED if disabled else _SUN_COLOR
    c = size / 2
    r = size * 0.26
    ray_in, ray_out = size * 0.34, size * 0.46
    width = max(1, int(size * 0.055))
    for i in range(8):
        angle = i * 45 * 3.14159265 / 180
        draw.line(
            [(c + ray_in * _cos(angle), c + ray_in * _sin(angle)),
             (c + ray_out * _cos(angle), c + ray_out * _sin(angle))],
            fill=color, width=width)
    draw.ellipse([c - r, c - r, c + r, c + r], fill=color)
    return img


def moon_icon(size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    c = size / 2
    r = size * 0.38
    draw.ellipse([c - r, c - r, c + r, c + r], fill=255)
    # вырезаем соседний круг, чтобы получился полумесяц
    cut_r = size * 0.34
    cut_c = c + size * 0.16
    draw.ellipse([cut_c - cut_r, c - cut_r, cut_c + cut_r, c + cut_r], fill=0)
    img.paste(Image.new("RGBA", (size, size), _MOON_COLOR), (0, 0), mask)
    return img


def _cos(angle: float) -> float:
    from math import cos
    return cos(angle)


def _sin(angle: float) -> float:
    from math import sin
    return sin(angle)


def app_icon(size: int = 256) -> Image.Image:
    """Квадратная иконка приложения: слева светлая половина с солнцем, справа тёмная с луной."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = size * 0.18
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=(245, 246, 250, 255))
    # правая (тёмная) половина с той же скруглённостью
    mask = Image.new("L", (size, size), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    mdraw.rectangle([size // 2, 0, size, size], fill=255)
    img.paste(Image.new("RGBA", (size, size), (32, 33, 36, 255)), (0, 0), mask)
    # солнце на светлой половине, луна на тёмной
    half = size // 2
    sun = sun_icon(half).resize((int(half * 0.92), int(half * 0.92)), Image.LANCZOS)
    img.alpha_composite(sun, (int(half * 0.06), int((size - sun.height) // 2)))
    moon = moon_icon(half).resize((int(half * 0.92), int(half * 0.92)), Image.LANCZOS)
    img.alpha_composite(moon, (half + int(half * 0.06), int((size - moon.height) // 2)))
    return img
