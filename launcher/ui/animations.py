import time

from PyQt6.QtCore import QPropertyAnimation, QVariantAnimation, QEasingCurve
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QProgressBar
from PyQt6.QtGui import QColor

from launcher.config import LauncherConfig
from launcher.theme import resolve_theme

_theme_cache = {"mode": None, "at": 0.0}
_THEME_TTL = 5.0


def theme_is_dark() -> bool:
    now = time.monotonic()
    if _theme_cache["mode"] is None or now - _theme_cache["at"] > _THEME_TTL:
        try:
            mode = LauncherConfig.load().theme_mode
        except Exception:
            mode = "system"
        _theme_cache["mode"] = resolve_theme(mode)
        _theme_cache["at"] = now
    return _theme_cache["mode"] == "dark"


def _fade_effect(widget):
    effect = widget.graphicsEffect()
    if isinstance(effect, QGraphicsOpacityEffect):
        return effect
    if effect is None:
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        return effect
    return None


def _keep(parent, name, anim):
    if hasattr(parent, name) and getattr(parent, name) is not None:
        getattr(parent, name).stop()
    setattr(parent, name, anim)


def fade_in(widget, duration=250):
    widget.show()
    effect = _fade_effect(widget)
    if effect is None:
        return None
    effect.setOpacity(0.0)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def done():
        effect.deleteLater()

    anim.finished.connect(done)
    _keep(widget, "_fade_in_anim", anim)
    anim.start()
    return anim


def fade_out(widget, duration=220, on_finished=None):
    effect = _fade_effect(widget)
    if effect is None:
        if on_finished:
            on_finished()
        return None
    effect.setOpacity(1.0)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)
    anim.setEasingCurve(QEasingCurve.Type.InCubic)

    def done():
        effect.deleteLater()
        if on_finished:
            on_finished()

    anim.finished.connect(done)
    _keep(widget, "_fade_out_anim", anim)
    anim.start()
    return anim


def fade_in_window(widget, duration=250):
    anim = QPropertyAnimation(widget, b"windowOpacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def done():
        widget.setWindowOpacity(1.0)

    anim.finished.connect(done)
    _keep(widget, "_win_fade_in_anim", anim)
    anim.start()
    return anim


def _shadow_color(alpha=None):
    if theme_is_dark():
        return QColor(0, 0, 0, alpha if alpha is not None else 130)
    return QColor(70, 70, 90, alpha if alpha is not None else 80)


def attach_shadow(widget, blur=18, offset=(0, 6), alpha=None):
    effect = widget.graphicsEffect()
    if isinstance(effect, QGraphicsDropShadowEffect):
        effect.setBlurRadius(blur)
        effect.setOffset(offset[0], offset[1])
        effect.setColor(_shadow_color(alpha))
        return effect
    if effect is not None:
        effect.deleteLater()
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(offset[0], offset[1])
    effect.setColor(_shadow_color(alpha))
    widget.setGraphicsEffect(effect)
    return effect


def animate_shadow(widget, blur, dy, duration=220, duration_back=0):
    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsDropShadowEffect):
        return
    anim = QVariantAnimation(widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    start_blur = effect.blurRadius()
    start_dy = effect.yOffset()

    def on_tick(t):
        effect.setBlurRadius(start_blur + (blur - start_blur) * t)
        effect.setOffset(0, start_dy + (dy - start_dy) * t)

    def on_done():
        effect.setBlurRadius(blur)
        effect.setOffset(0, dy)
        setattr(widget, "_shadow_anim", None)

    anim.valueChanged.connect(on_tick)
    anim.finished.connect(on_done)
    _keep(widget, "_shadow_anim", anim)
    anim.start()
    return anim


def reveal(widget, duration=280):
    if widget.isVisible():
        fade_in(widget, duration=duration)
        return
    widget.setMaximumHeight(0)
    widget.show()
    natural = max(1, widget.sizeHint().height())
    anim = QPropertyAnimation(widget, b"maximumHeight", widget)
    anim.setDuration(duration)
    anim.setStartValue(0)
    anim.setEndValue(natural)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def done():
        widget.setMaximumHeight(16777215)

    anim.finished.connect(done)
    _keep(widget, "_reveal_anim", anim)
    anim.start()
    fade_in(widget, duration=duration)


def collapse(widget, duration=220, on_finished=None):
    if not widget.isVisible():
        if on_finished:
            on_finished()
        return
    start = max(0, widget.height())
    anim = QPropertyAnimation(widget, b"maximumHeight", widget)
    anim.setDuration(duration)
    anim.setStartValue(start)
    anim.setEndValue(0)
    anim.setEasingCurve(QEasingCurve.Type.InCubic)

    def done():
        widget.hide()
        widget.setMaximumHeight(16777215)
        if on_finished:
            on_finished()

    anim.finished.connect(done)
    _keep(widget, "_collapse_anim", anim)
    anim.start()
    fade_out(widget, duration=duration)


def slide_down(widget, duration=360):
    if widget.height() > 0 and widget.maximumHeight() != 0:
        return
    widget.setMaximumHeight(0)
    widget.show()
    natural = max(1, widget.sizeHint().height())
    anim = QPropertyAnimation(widget, b"maximumHeight", widget)
    anim.setDuration(duration)
    anim.setStartValue(0)
    anim.setEndValue(natural)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def done():
        widget.setMaximumHeight(16777215)

    anim.finished.connect(done)
    _keep(widget, "_slide_down_anim", anim)
    anim.start()


class SmoothProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value_anim = None

    def setValue(self, value):
        value = int(value)
        if self.value() == value:
            return
        if self._value_anim is not None:
            self._value_anim.stop()
            self._value_anim = None
        anim = QVariantAnimation(self)
        anim.setDuration(200)
        anim.setStartValue(self.value())
        anim.setEndValue(value)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(lambda v: QProgressBar.setValue(self, int(v)))
        anim.finished.connect(lambda: setattr(self, "_value_anim", None))
        self._value_anim = anim
        anim.start()
