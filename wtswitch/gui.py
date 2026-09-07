"""Окно настроек на PySide6: фреймлес-окно в стиле WinUI 3.

Кастомный тайтлбар с перетаскиванием, карточки со скруглениями и тенью,
переключатели Win11 с анимацией, сегмент-контрол, тёмная и светлая темы.
"""
from __future__ import annotations

import io
import os
import re
import threading
from datetime import datetime
from typing import Optional

from PySide6.QtCore import (QEasingCurve, QPointF, QRectF, QSize, Qt, QTimer,
                            QVariantAnimation)
from PySide6.QtGui import (QBrush, QColor, QIcon, QPainter, QPixmap,
                           QRegularExpressionValidator, QRadialGradient)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
                               QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget)

from . import geoloc, schedule
from .config import Config, MODE_FIXED, MODE_OFF, MODE_SOLAR
from .icons import app_icon, moon_icon, sun_icon
from .theme import DARK, LIGHT

WINDOW_W, WINDOW_H = 720, 890

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")
_MOD_SETS = ["Ctrl+Alt", "Ctrl+Shift", "Ctrl+Alt+Shift", "Alt+Shift",
             "Ctrl+Win", "Alt+Win", "Shift+Win"]
_KEYS = ["D", "T", "L", "K", "M", "N", "W", "A", "B", "C", "E", "R", "S", "V",
         "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
         "F9", "F10", "F11", "F12"]
_THEME_NAMES = {LIGHT: "светлая", DARK: "тёмная"}

LIGHT_PAL = dict(bg="#f2f5fa", card="#ffffff", brd="rgba(9,30,66,0.09)", brd2="#c7cfdb",
                 text="#191d23", sub="#5f6875", hover="#e8edf4", pressed="#dde4ee",
                 accent="#0067c0", accent_h="#1976d2", accent_text="#ffffff",
                 seg_bg="rgba(9,30,66,0.07)", seg_on="#ffffff",
                 danger="#c42b1c", ok="#0f7b3d", knob_off="#5f6875")
DARK_PAL = dict(bg="#1e1f24", card="#2a2b31", brd="rgba(255,255,255,0.08)", brd2="#4a4c55",
                text="#f1f2f5", sub="#9aa2ad", hover="#34353d", pressed="#3d3e47",
                accent="#4cc2ff", accent_h="#7dd2ff", accent_text="#062338",
                seg_bg="rgba(255,255,255,0.07)", seg_on="#3c3d45",
                danger="#e5647a", ok="#6ccb92", knob_off="#9aa2ad")


def _pil_to_pixmap(img, size: int = 0) -> QPixmap:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    pm = QPixmap()
    pm.loadFromData(buf.getvalue(), "PNG")
    if size:
        pm = pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return pm


def _theme_name(theme: str) -> str:
    return _THEME_NAMES.get(theme, theme)


def _human_delta(minutes: int) -> str:
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} ч {mins} мин"
    if hours:
        return f"{hours} ч"
    return f"{mins} мин"


def build_qss() -> str:
    """Единый QSS с вариантами [theme=light] и [theme=dark]."""
    blocks = []
    for name, v in (("light", LIGHT_PAL), ("dark", DARK_PAL)):
        blocks.append(f"""
        QWidget#Root[theme="{name}"] {{ background-color: {v['bg']}; }}
        QWidget#Root[theme="{name}"] QFrame[card="true"] {{
            background-color: {v['card']}; border: 1px solid {v['brd']};
            border-radius: 12px; }}
        QWidget#Root[theme="{name}"] QLabel {{ background: transparent; color: {v['text']}; }}
        QWidget#Root[theme="{name}"] QLabel[sect="true"] {{
            color: {v['sub']}; font-size: 11px; font-weight: 600; }}
        QWidget#Root[theme="{name}"] QLabel[secondary="true"] {{ color: {v['sub']}; }}
        QWidget#Root[theme="{name}"] QLabel#HeroStatus {{ color: {v['sub']}; font-size: 13px; }}
        QWidget#Root[theme="{name}"] QLabel#AppTitle {{ color: {v['sub']}; font-size: 12px; }}
        QWidget#Root[theme="{name}"] QPushButton {{
            background-color: {v['card']}; color: {v['text']};
            border: 1px solid {v['brd2']}; border-radius: 6px;
            padding: 8px 14px; font-size: 13px; }}
        QWidget#Root[theme="{name}"] QPushButton:hover {{ background-color: {v['hover']}; }}
        QWidget#Root[theme="{name}"] QPushButton:pressed {{ background-color: {v['pressed']}; }}
        QWidget#Root[theme="{name}"] QPushButton[ghost="true"] {{ background: transparent; }}
        QWidget#Root[theme="{name}"] QPushButton[ghost="true"]:hover {{ background: {v['hover']}; }}
        QWidget#Root[theme="{name}"] QPushButton#Accent {{
            background-color: {v['accent']}; color: {v['accent_text']};
            border: none; font-weight: 600; padding: 10px 22px; font-size: 13px; }}
        QWidget#Root[theme="{name}"] QPushButton#Accent:hover {{ background-color: {v['accent_h']}; }}
        QWidget#Root[theme="{name}"] QPushButton:disabled {{
            color: {v['sub']}; background-color: {v['bg']}; }}
        QWidget#Root[theme="{name}"] QLineEdit, QWidget#Root[theme="{name}"] QComboBox {{
            background-color: {v['bg']}; color: {v['text']};
            border: 1px solid {v['brd2']}; border-radius: 6px;
            padding: 6px 10px; font-size: 14px; }}
        QWidget#Root[theme="{name}"] QLineEdit:focus,
        QWidget#Root[theme="{name}"] QComboBox:focus {{ border: 1px solid {v['accent']}; }}
        QWidget#Root[theme="{name}"] QComboBox::drop-down {{ border: none; width: 26px; }}
        QWidget#Root[theme="{name}"] QComboBox::down-arrow {{
            width: 0; height: 0; border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid {v['sub']}; margin-right: 8px; }}
        QWidget#Root[theme="{name}"] QComboBox QAbstractItemView {{
            background-color: {v['card']}; color: {v['text']};
            border: 1px solid {v['brd']}; selection-background-color: {v['hover']};
            selection-color: {v['text']}; outline: none; }}
        QWidget#Root[theme="{name}"] QFrame#Seg {{
            background-color: {v['seg_bg']}; border: none; border-radius: 9px; }}
        QWidget#Root[theme="{name}"] QFrame#Seg > QPushButton {{
            background: transparent; border: none; border-radius: 7px;
            color: {v['sub']}; padding: 7px 20px; font-size: 13px; }}
        QWidget#Root[theme="{name}"] QFrame#Seg > QPushButton:checked {{
            background-color: {v['seg_on']}; color: {v['text']};
            border: 1px solid {v['brd']}; font-weight: 600; }}
        QWidget#Root[theme="{name}"] QFrame#TitleBar {{ background: transparent; border: none; }}
        QWidget#Root[theme="{name}"] QPushButton#TBButton {{
            background: transparent; border: none; border-radius: 7px;
            color: {v['sub']}; font-size: 12px; padding: 0; }}
        QWidget#Root[theme="{name}"] QPushButton#TBButton:hover {{
            background: {v['hover']}; color: {v['text']}; }}
        QWidget#Root[theme="{name}"] QPushButton#TBButton[danger="true"]:hover {{
            background: {v['danger']}; color: #ffffff; }}
        QWidget#Root[theme="{name}"] QLabel#ErrBanner {{
            background: rgba(196,43,28,0.12); color: {v['danger']};
            border: 1px solid {v['danger']}; border-radius: 8px;
            padding: 9px 14px; font-size: 13px; }}
        """)
    return "\n".join(blocks)


class ToggleSwitch(QCheckBox):
    """Переключатель в стиле Windows 11 с плавной анимацией ползунка."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 0.0
        self._anim = QVariantAnimation(self, duration=150,
                                       easingCurve=QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self.toggled.connect(self._animate_to)

    def _on_anim(self, value) -> None:
        self._pos = float(value)
        self.update()

    def _animate_to(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def sizeHint(self) -> QSize:
        return QSize(44, 24)

    def minimumSizeHint(self) -> QSize:
        return QSize(44, 24)

    def hitButton(self, pos) -> bool:
        return self.rect().adjusted(-6, -6, 6, 6).contains(pos)

    def paintEvent(self, event) -> None:
        pal = getattr(self.window(), "pal", LIGHT_PAL)
        dark = getattr(self.window(), "_is_dark", False)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = 44.0, 22.0
        y = (self.height() - h) / 2
        track = QRectF(0, y, w, h)
        checked = self.isChecked()
        if checked:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(pal["accent"]))
            p.drawRoundedRect(track, h / 2, h / 2)
            knob = QColor(pal["accent_text"])
            knob_d = 14.0
        else:
            p.setPen(QColor(pal["brd2"]))
            p.setBrush(QColor("transparent") if dark else QColor(pal["card"]))
            p.drawRoundedRect(track, h / 2, h / 2)
            knob = QColor(pal["knob_off"])
            knob_d = 12.0
        margin = 4.0
        travel = w - 2 * margin - knob_d
        x = margin + self._pos * travel
        p.setPen(Qt.NoPen)
        p.setBrush(knob)
        p.drawEllipse(QPointF(x + knob_d / 2, y + h / 2), knob_d / 2, knob_d / 2)
        p.end()


class TitleBar(QFrame):
    """Тайтлбар: логотип, заголовок, свернуть/закрыть; перетаскивание мышью."""

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.setObjectName("TitleBar")
        self.setFixedHeight(48)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 10, 10, 6)
        layout.setSpacing(10)

        logo = QLabel()
        logo.setPixmap(_pil_to_pixmap(app_icon(20), 20))
        layout.addWidget(logo)
        title = QLabel("Win Theme Switcher")
        title.setObjectName("AppTitle")
        layout.addWidget(title)
        layout.addStretch(1)

        self.btn_min = QPushButton("—")
        self.btn_min.setObjectName("TBButton")
        self.btn_min.setFixedSize(40, 32)
        self.btn_min.clicked.connect(self._minimize)
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("TBButton")
        self.btn_close.setProperty("danger", True)
        self.btn_close.setFixedSize(40, 32)
        self.btn_close.clicked.connect(self._hide)
        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_close)

    def _minimize(self) -> None:
        self.window().showMinimized()

    def _hide(self) -> None:
        self.window().hide()  # в трей; выход — через меню трея

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            handle = self.window().windowHandle()
            if handle:
                handle.startSystemMove()


class SettingsWindow(QWidget):
    def __init__(self, app) -> None:
        super().__init__()
        self.app = app
        self._shown_theme: Optional[str] = None
        self._is_dark = False
        self.pal = LIGHT_PAL

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "assets", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(WINDOW_W, WINDOW_H)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 18)
        self.root = QFrame(objectName="Root")
        outer.addWidget(self.root)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.root.setGraphicsEffect(shadow)

        inner = QVBoxLayout(self.root)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)
        inner.addWidget(TitleBar(self.root))

        body = QWidget()
        inner.addWidget(body)
        self._build_body(body)

        self.setStyleSheet(build_qss())
        self._set_theme(LIGHT)

    # ---------- тема ----------

    def _set_theme(self, theme: str) -> None:
        self._is_dark = theme == DARK
        self.pal = DARK_PAL if self._is_dark else LIGHT_PAL
        self.root.setProperty("theme", theme)
        style = self.style()
        style.unpolish(self.root)
        style.polish(self.root)
        for w in self.findChildren(QWidget):
            style.unpolish(w)
            style.polish(w)
        self._update_orb(theme)

    def _update_orb(self, theme: str) -> None:
        size = 66
        dpr = self.devicePixelRatioF()
        pm = QPixmap(int(size * dpr), int(size * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        grad = QRadialGradient(QPointF(size * 0.36, size * 0.30), size * 0.95)
        if theme == DARK:
            grad.setColorAt(0, QColor("#8f9bff"))
            grad.setColorAt(1, QColor("#4d59c9"))
        else:
            grad.setColorAt(0, QColor("#ffdf7e"))
            grad.setColorAt(1, QColor("#ff9d2e"))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(0, 0, size, size))
        icon = moon_icon(int(size * 0.5)) if theme == DARK else sun_icon(int(size * 0.52))
        img = _pil_to_pixmap(icon)
        p.drawPixmap(int((size - img.width()) / 2), int((size - img.height()) / 2), img)
        p.end()
        self.orb.setPixmap(pm)

    # ---------- построение ----------

    def _build_body(self, body: QWidget) -> None:
        col = QVBoxLayout(body)
        col.setContentsMargins(28, 8, 28, 24)
        col.setSpacing(0)

        # --- герой ---
        hero = QHBoxLayout()
        hero.setSpacing(16)
        self.orb = QLabel()
        self.orb.setFixedSize(66, 66)
        hero.addWidget(self.orb, 0, Qt.AlignVCenter)
        hero_txt = QVBoxLayout()
        hero_txt.setSpacing(4)
        self.hero_title = QLabel("…")
        self.hero_title.setStyleSheet("font-size: 20px; font-weight: 600; border: none;")
        self.hero_status = QLabel("Загрузка…")
        self.hero_status.setObjectName("HeroStatus")
        self.hero_status.setWordWrap(True)
        hero_txt.addWidget(self.hero_title)
        hero_txt.addWidget(self.hero_status)
        hero.addLayout(hero_txt, 1)
        actions = QVBoxLayout()
        actions.setSpacing(8)
        self.btn_light = QPushButton(QIcon(_pil_to_pixmap(sun_icon(16))), "Светлая")
        self.btn_dark = QPushButton(QIcon(_pil_to_pixmap(moon_icon(16))), "Тёмная")
        for b in (self.btn_light, self.btn_dark):
            b.setProperty("ghost", True)
        self.btn_light.clicked.connect(lambda: self.app.set_override(LIGHT))
        self.btn_dark.clicked.connect(lambda: self.app.set_override(DARK))
        actions.addWidget(self.btn_light)
        actions.addWidget(self.btn_dark)
        hero.addLayout(actions)
        col.addLayout(hero)

        # --- режим ---
        col.addSpacing(16)
        col.addWidget(self._sect("РЕЖИМ РАСПИСАНИЯ"))
        col.addSpacing(6)
        seg = QFrame(objectName="Seg")
        seg_l = QHBoxLayout(seg)
        seg_l.setContentsMargins(3, 3, 3, 3)
        seg_l.setSpacing(3)
        self.seg_buttons: dict[str, QPushButton] = {}
        for value, text in ((MODE_FIXED, "По времени"), (MODE_SOLAR, "Солнце"),
                            (MODE_OFF, "Вручную")):
            b = QPushButton(text)
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, v=value: self._on_mode(v))
            seg_l.addWidget(b)
            self.seg_buttons[value] = b
        seg_l.addStretch(1)
        col.addWidget(seg)

        time_validator = QRegularExpressionValidator(r"(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]")

        # карточка фиксированного времени
        self.card_fixed = self._card()
        fx = QGridLayout(self.card_fixed)
        fx.setContentsMargins(20, 14, 20, 16)
        fx.setHorizontalSpacing(24)
        self.var_light_time = QLineEdit("08:00")
        self.var_dark_time = QLineEdit("23:00")
        for edit in (self.var_light_time, self.var_dark_time):
            edit.setValidator(time_validator)
            edit.setFixedWidth(150)
            edit.setAlignment(Qt.AlignCenter)
        self._time_field(fx, 0, 0, "☀  Светлая тема включается в", self.var_light_time)
        self._time_field(fx, 0, 1, "☾  Тёмная тема включается в", self.var_dark_time)
        col.addWidget(self.card_fixed)
        col.addSpacing(10)

        # карточка солнечного режима
        self.card_solar = self._card()
        sv = QGridLayout(self.card_solar)
        sv.setContentsMargins(20, 14, 20, 16)
        sv.setVerticalSpacing(8)
        self.var_lat = QLineEdit()
        self.var_lon = QLineEdit()
        for edit, ph in ((self.var_lat, "55.75"), (self.var_lon, "37.62")):
            edit.setPlaceholderText(ph)
            edit.setFixedWidth(120)
            edit.setAlignment(Qt.AlignCenter)
        self._grid_field(sv, 0, 0, "Широта", self.var_lat)
        self._grid_field(sv, 0, 1, "Долгота", self.var_lon)
        self.btn_geo = QPushButton("Определить по IP")
        self.btn_geo.clicked.connect(self._detect_location)
        sv.addWidget(self.btn_geo, 1, 2, Qt.AlignLeft)
        self.geo_label = QLabel("координаты для расчёта восхода и заката")
        self.geo_label.setProperty("secondary", True)
        sv.addWidget(self.geo_label, 2, 0, 1, 3)
        offs = QHBoxLayout()
        offs.setSpacing(6)
        offs.addWidget(self._sub("Сдвиг:  восход ±"))
        self.var_sunrise_off = QLineEdit("0")
        self.var_sunrise_off.setFixedSize(56, 32)
        self.var_sunrise_off.setAlignment(Qt.AlignCenter)
        self.var_sunrise_off.setValidator(QRegularExpressionValidator(r"-?\d{1,3}"))
        offs.addWidget(self.var_sunrise_off)
        offs.addWidget(self._sub("мин   ·   закат ±"))
        self.var_sunset_off = QLineEdit("0")
        self.var_sunset_off.setFixedSize(56, 32)
        self.var_sunset_off.setAlignment(Qt.AlignCenter)
        self.var_sunset_off.setValidator(QRegularExpressionValidator(r"-?\d{1,3}"))
        offs.addWidget(self.var_sunset_off)
        offs.addWidget(self._sub("мин"))
        offs.addStretch(1)
        sv.addLayout(offs, 3, 0, 1, 3)
        col.addWidget(self.card_solar)
        col.addSpacing(10)

        # карточка ручного режима
        self.card_off = self._card()
        off_l = QVBoxLayout(self.card_off)
        off_l.setContentsMargins(20, 14, 20, 14)
        lbl = QLabel("Расписание отключено: переключайте тему кнопками сверху "
                     "или горячей клавишей.")
        lbl.setProperty("secondary", True)
        lbl.setWordWrap(True)
        off_l.addWidget(lbl)
        col.addWidget(self.card_off)
        col.addSpacing(10)

        # --- применять к ---
        col.addSpacing(12)
        col.addWidget(self._sect("ПРИМЕНЯТЬ К"))
        col.addSpacing(6)
        card_apply = self._card()
        al = QVBoxLayout(card_apply)
        al.setContentsMargins(20, 10, 20, 12)
        al.setSpacing(2)
        self.sw_apps = self._switch_row(al, "Приложения",
                                        "поддерживаемые программы читают системную тему")
        self.sw_system = self._switch_row(al, "Оболочка",
                                          "панель задач, меню Пуск, проводник")
        col.addWidget(card_apply)

        # --- поведение ---
        col.addSpacing(12)
        col.addWidget(self._sect("ПОВЕДЕНИЕ"))
        col.addSpacing(6)
        card_beh = self._card()
        bl = QVBoxLayout(card_beh)
        bl.setContentsMargins(20, 10, 20, 12)
        bl.setSpacing(2)
        self.sw_enforce = self._switch_row(
            bl, "Приоритет расписания",
            "возвращать плановую тему, даже если её поменяли вручную")
        self.sw_autostart = self._switch_row(bl, "Запускать вместе с Windows", None)
        self.sw_minimized = self._switch_row(bl, "Запускать свёрнутым в трей", None)

        hk = QHBoxLayout()
        hk.setSpacing(8)
        self.sw_hotkey = ToggleSwitch()
        self.sw_hotkey.toggled.connect(self._sync_hotkey_state)
        hk.addWidget(self.sw_hotkey)
        hk.addSpacing(8)
        hk.addWidget(self._sub("Горячая клавиша"))
        self.combo_mods = QComboBox()
        self.combo_mods.addItems(_MOD_SETS)
        self.combo_mods.setFixedWidth(135)
        hk.addWidget(self.combo_mods)
        hk.addWidget(self._sub("+"))
        self.combo_key = QComboBox()
        self.combo_key.addItems(_KEYS)
        self.combo_key.setFixedWidth(74)
        hk.addWidget(self.combo_key)
        hk.addStretch(1)
        bl.addLayout(hk)
        col.addWidget(card_beh)
        col.addStretch(1)  # всё свободное место — между карточками и нижней панелью

        # --- низ ---
        col.addSpacing(16)
        self.err_banner = QLabel("")
        self.err_banner.setObjectName("ErrBanner")
        self.err_banner.setWordWrap(True)
        self.err_banner.setVisible(False)
        col.addWidget(self.err_banner)
        foot = QHBoxLayout()
        foot.setSpacing(12)
        self.saved_mark = QLabel("Сохранено ✓")
        self.saved_mark.setStyleSheet("color: #0f7b3d; font-weight: 600; border: none;")
        self.saved_mark.setVisible(False)
        foot.addWidget(self.saved_mark)
        foot.addStretch(1)
        self.btn_save = QPushButton("Сохранить и применить")
        self.btn_save.setObjectName("Accent")
        self.btn_save.clicked.connect(self._save)
        foot.addWidget(self.btn_save)
        col.addLayout(foot)

    def _sect(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("sect", True)
        return lbl

    def _sub(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("secondary", True)
        return lbl

    def _card(self) -> QFrame:
        card = QFrame()
        card.setProperty("card", True)
        return card

    def _time_field(self, grid, row, col, text: str, edit: QLineEdit) -> None:
        wrap = QVBoxLayout()
        wrap.setSpacing(6)
        wrap.addWidget(self._sub(text))
        wrap.addWidget(edit)
        wrap.addStretch(1)
        grid.addLayout(wrap, row, col)

    def _grid_field(self, grid, row, col, text: str, edit: QLineEdit) -> None:
        grid.addWidget(self._sub(text), row, col)
        grid.addWidget(edit, row + 1, col)

    def _switch_row(self, layout, title: str, subtitle: Optional[str]) -> ToggleSwitch:
        row = QHBoxLayout()
        row.setSpacing(14)
        sw = ToggleSwitch()
        txt = QVBoxLayout()
        txt.setSpacing(1)
        txt.addWidget(QLabel(title))
        if subtitle:
            sub = QLabel(subtitle)
            sub.setProperty("secondary", True)
            sub.setStyleSheet("font-size: 11.5px; border: none;")
            txt.addWidget(sub)
        row.addLayout(txt, 1)
        row.addWidget(sw, 0, Qt.AlignVCenter)
        wrap = QFrame()
        wrap.setStyleSheet("border: none; background: transparent;")
        wrap.setLayout(row)
        layout.addWidget(wrap)
        return sw

    # ---------- публичное ----------

    def show_and_center(self) -> None:
        self._load_from(self.app.config)
        self.show()
        geo = self.screen().availableGeometry()
        self.move(geo.center().x() - self.width() // 2,
                  geo.top() + max(24, (geo.height() - self.height()) // 3))
        self.raise_()
        self.activateWindow()

    def refresh_status(self, current: str, override: Optional[str],
                       nxt, hotkey_error: str) -> None:
        """Обновить состояние и тему окна (главный поток)."""
        if self._shown_theme != current:
            self._shown_theme = current
            self._set_theme(current)
        cfg = self.app.config
        now = datetime.now().astimezone()

        self.hero_title.setText(f"Сейчас — {_theme_name(current)} тема")
        lines = []
        if cfg.mode == MODE_OFF:
            lines.append("Расписание выключено: кнопки справа или горячая клавиша")
        elif override:
            when = f" — по расписанию с {nxt.at:%H:%M}" if nxt else ""
            lines.append(f"Включено вручную{when}")
        elif nxt:
            delta_min = max(1, round((nxt.at - now).total_seconds() / 60))
            lines.append(f"Далее: {_theme_name(nxt.theme)} в {nxt.at:%H:%M}"
                         f" · через {_human_delta(delta_min)}")
        if cfg.mode == MODE_SOLAR:
            lines.append("Солнечный режим: время зависит от восхода и заката")
        if hotkey_error:
            lines.append(f"⚠ {hotkey_error}")
        self.hero_status.setText("\n".join(lines))

    # ---------- внутреннее ----------

    def _on_mode(self, value: str) -> None:
        for mode, btn in self.seg_buttons.items():
            btn.setChecked(mode == value)
        self.card_fixed.setVisible(value == MODE_FIXED)
        self.card_solar.setVisible(value == MODE_SOLAR)
        self.card_off.setVisible(value == MODE_OFF)

    def _sync_hotkey_state(self) -> None:
        enabled = self.sw_hotkey.isChecked()
        self.combo_mods.setEnabled(enabled)
        self.combo_key.setEnabled(enabled)

    def _detect_location(self) -> None:
        self.btn_geo.setEnabled(False)
        self.geo_label.setText("Определяем координаты…")

        def worker():
            try:
                lat, lon, city = geoloc.detect_by_ip()
            except Exception as exc:
                self.app.marshal(lambda: (
                    self.geo_label.setText(f"Не удалось: {exc}"),
                    self.btn_geo.setEnabled(True)))
                return

            def apply():
                self.var_lat.setText(f"{lat:.4f}")
                self.var_lon.setText(f"{lon:.4f}")
                self.geo_label.setText(f"≈ {city}" if city else "готово")
                self.btn_geo.setEnabled(True)
            self.app.marshal(apply)

        threading.Thread(target=worker, daemon=True).start()

    def _load_from(self, cfg) -> None:
        for mode, btn in self.seg_buttons.items():
            btn.setChecked(mode == cfg.mode)
        self.var_light_time.setText(cfg.light_time)
        self.var_dark_time.setText(cfg.dark_time)
        self.var_sunrise_off.setText(str(cfg.sunrise_offset))
        self.var_sunset_off.setText(str(cfg.sunset_offset))
        self.var_lat.setText("" if cfg.lat is None else f"{cfg.lat:.4f}")
        self.var_lon.setText("" if cfg.lon is None else f"{cfg.lon:.4f}")
        self.sw_apps.setChecked(cfg.apply_apps)
        self.sw_system.setChecked(cfg.apply_system)
        self.sw_enforce.setChecked(cfg.enforce)
        self.sw_autostart.setChecked(cfg.start_with_windows)
        self.sw_minimized.setChecked(cfg.start_minimized)
        self.sw_hotkey.setChecked(cfg.hotkey_enabled)
        mods, _, key = cfg.hotkey.rpartition("+")
        if mods in _MOD_SETS:
            self.combo_mods.setCurrentText(mods)
        if key.upper() in _KEYS:
            self.combo_key.setCurrentText(key.upper())
        self._on_mode(cfg.mode)
        self._sync_hotkey_state()

    def showEvent(self, event) -> None:
        self._load_from(self.app.config)
        super().showEvent(event)

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()  # крестик сворачивает в трей

    def _collect(self) -> Optional[Config]:
        cfg = Config()
        cfg.mode = next((m for m, b in self.seg_buttons.items() if b.isChecked()), MODE_FIXED)
        lt, dt = self.var_light_time.text().strip(), self.var_dark_time.text().strip()
        if not _TIME_RE.match(lt) or not _TIME_RE.match(dt):
            self._err("Время укажите в формате ЧЧ:ММ, например 08:00")
            return None
        cfg.light_time, cfg.dark_time = lt, dt
        try:
            cfg.sunrise_offset = int(self.var_sunrise_off.text() or 0)
            cfg.sunset_offset = int(self.var_sunset_off.text() or 0)
        except ValueError:
            self._err("Смещение должно быть целым числом минут")
            return None
        lat_s, lon_s = self.var_lat.text().strip(), self.var_lon.text().strip()
        try:
            cfg.lat = float(lat_s) if lat_s else None
            cfg.lon = float(lon_s) if lon_s else None
            if cfg.mode == MODE_SOLAR and (cfg.lat is None or cfg.lon is None):
                raise ValueError
            if cfg.lat is not None and not (-90 <= cfg.lat <= 90 and -180 <= cfg.lon <= 180):
                raise ValueError
        except ValueError:
            self._err("Координаты (обязательны для «Солнце»): широта -90…90, долгота -180…180")
            return None
        cfg.apply_apps = self.sw_apps.isChecked()
        cfg.apply_system = self.sw_system.isChecked()
        if not cfg.apply_apps and not cfg.apply_system:
            self._err("Выберите хотя бы одну цель: приложения или оболочка")
            return None
        cfg.enforce = self.sw_enforce.isChecked()
        cfg.hotkey_enabled = self.sw_hotkey.isChecked()
        cfg.hotkey = f"{self.combo_mods.currentText()}+{self.combo_key.currentText()}".lower()
        cfg.start_with_windows = self.sw_autostart.isChecked()
        cfg.start_minimized = self.sw_minimized.isChecked()
        return cfg

    def _err(self, text: str) -> None:
        self.err_banner.setText(text)
        self.err_banner.setVisible(True)

    def _save(self) -> None:
        cfg = self._collect()
        if cfg is None:
            return
        self.err_banner.setVisible(False)
        self.app.apply_config(cfg)
        self.saved_mark.setVisible(True)
        QTimer.singleShot(2200, lambda: self.saved_mark.setVisible(False))
