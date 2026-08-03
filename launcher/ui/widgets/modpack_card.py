from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QMenu
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QVariantAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QColor

from launcher.ui.animations import fade_in, attach_shadow, animate_shadow, theme_is_dark


HOST_MARGINS = (8, 6, 8, 16)
HOST_MARGINS_LIFT = (8, 2, 8, 20)


class _ShadowButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._base_blur = 12
        self._base_dy = 3
        attach_shadow(self, blur=self._base_blur, offset=(0, self._base_dy))

    def enterEvent(self, event):
        super().enterEvent(event)
        animate_shadow(self, 22, 7, duration=200)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        animate_shadow(self, self._base_blur, self._base_dy, duration=200)


class ModpackCard(QFrame):
    install_clicked = pyqtSignal(object)
    play_clicked = pyqtSignal(object)
    connect_clicked = pyqtSignal(object, object)
    settings_clicked = pyqtSignal(object)
    delete_clicked = pyqtSignal(object)

    def __init__(self, modpack: dict, installed: bool = False, game_running: bool = False, host=None):
        super().__init__(host)
        self.modpack = modpack
        self.host = host
        self._installed = installed
        self._game_running = game_running
        self._servers = []
        self._hover_anim = None
        self._lift_anim = None
        self._hover_border = QColor(44, 44, 44)
        self._reveal_anim = None

        self.setObjectName("ModpackCard")
        self._shadow_base_blur = 16
        self._shadow_base_dy = 5
        self._shadow_hover_blur = 30
        self._shadow_hover_dy = 12
        attach_shadow(self, blur=self._shadow_base_blur, offset=(0, self._shadow_base_dy))
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(16, 14, 16, 14)

        header = QHBoxLayout()
        header.setSpacing(12)
        icon = QLabel(modpack.get("name", "?")[0].upper(), self)
        icon.setObjectName("ModpackIcon")
        icon.setFixedSize(40, 40)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(icon)

        info = QVBoxLayout()
        info.setSpacing(2)
        name = QLabel(modpack.get("name", "Unknown"), self)
        name.setObjectName("ModpackName")
        info.addWidget(name)

        mc = modpack.get("mc_version", "")
        loader = modpack.get("loader", "")
        lv = modpack.get("loader_version", "")
        meta_parts = [f"v{modpack.get('version', '?')}"]
        if mc:
            meta_parts.append(f"MC {mc}")
        if loader:
            meta_parts.append(f"{loader} {lv or ''}")
        meta_parts.append(f"{modpack.get('file_count', 0)} files")
        meta_label = QLabel("  |  ".join(meta_parts), self)
        meta_label.setObjectName("ModpackMeta")
        info.addWidget(meta_label)
        header.addLayout(info, 1)
        layout.addLayout(header)

        if modpack.get("description"):
            desc = QLabel(modpack["description"], self)
            desc.setObjectName("ModpackDesc")
            desc.setWordWrap(True)
            desc.setMaximumHeight(40)
            layout.addWidget(desc)

        self.servers_container = QVBoxLayout()
        self.servers_container.setSpacing(0)
        self.servers_container.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.servers_container)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.setContentsMargins(0, 8, 0, 0)

        self.primary_btn = _ShadowButton(self)
        self.primary_btn.clicked.connect(self._on_primary_clicked)
        btn_row.addWidget(self.primary_btn)

        self.menu_btn = QPushButton("⋮", self)
        self.menu_btn.setObjectName("CardMenuButton")
        self.menu = QMenu(self)
        self.menu_btn.setMenu(self.menu)
        btn_row.addWidget(self.menu_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._update_primary(installed)
        self._build_menu(installed)

    @staticmethod
    def _repolish(widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _on_primary_clicked(self):
        if self._installed:
            self.play_clicked.emit(self.modpack)
        else:
            self.install_clicked.emit(self.modpack)

    def animate_in(self, delay=0):
        target = self.host or self

        def run():
            target.setMaximumHeight(0)
            natural = max(1, target.sizeHint().height())
            anim = QPropertyAnimation(target, b"maximumHeight", target)
            anim.setDuration(320)
            anim.setStartValue(0)
            anim.setEndValue(natural)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            def done():
                target.setMaximumHeight(16777215)

            anim.finished.connect(done)
            self._reveal_anim = anim
            anim.start()
            fade_in(target, duration=320)
            animate_shadow(self, self._shadow_base_blur, self._shadow_base_dy, duration=360)

        if delay:
            QTimer.singleShot(delay, run)
        else:
            run()

    def enterEvent(self, event):
        super().enterEvent(event)
        self._animate_hover(True)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._animate_hover(False)

    def _card_stylesheet(self, bg, border):
        return (
            "QFrame#ModpackCard {"
            f" background: {bg.name(QColor.NameFormat.HexRgb)};"
            f" border: 1px solid {border.name(QColor.NameFormat.HexRgb)};"
            " border-radius: 8px;"
            " padding: 4px;"
            "}"
        )

    def _hover_colors(self):
        if theme_is_dark():
            return (
                QColor("#1E1E1E"),
                QColor("#272727"),
                QColor(44, 44, 44),
                QColor(187, 134, 252, 190),
            )
        return (
            QColor("#FFFFFF"),
            QColor("#F0EAF5"),
            QColor("#E4E0E8"),
            QColor(98, 0, 238, 150),
        )

    def _animate_hover(self, hovered):
        bg_n, bg_h, brd_n, brd_h = self._hover_colors()
        start = bg_n if hovered else bg_h
        end = bg_h if hovered else bg_n
        self._hover_border = brd_h if hovered else brd_n
        if self._hover_anim is not None:
            self._hover_anim.stop()
            self._hover_anim = None
        anim = QVariantAnimation(self)
        anim.setDuration(200)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(self._on_hover_color)
        anim.finished.connect(lambda: setattr(self, "_hover_anim", None))
        self._hover_anim = anim
        anim.start()
        if hovered:
            animate_shadow(self, self._shadow_hover_blur, self._shadow_hover_dy, duration=260)
        else:
            animate_shadow(self, self._shadow_base_blur, self._shadow_base_dy, duration=260)
        self._animate_lift(hovered)

    def _animate_lift(self, hovered):
        host = self.host
        if host is None:
            return
        lay = host.layout()
        if lay is None:
            return
        target = HOST_MARGINS_LIFT if hovered else HOST_MARGINS
        m = lay.contentsMargins()
        start = (m.left(), m.top(), m.right(), m.bottom())
        if self._lift_anim is not None:
            self._lift_anim.stop()
            self._lift_anim = None
        anim = QVariantAnimation(host)
        anim.setDuration(200)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def on_tick(t):
            l = round(start[0] + (target[0] - start[0]) * t)
            tp = round(start[1] + (target[1] - start[1]) * t)
            r = round(start[2] + (target[2] - start[2]) * t)
            b = round(start[3] + (target[3] - start[3]) * t)
            lay.setContentsMargins(l, tp, r, b)

        def on_done():
            lay.setContentsMargins(*target)
            setattr(self, "_lift_anim", None)

        anim.valueChanged.connect(on_tick)
        anim.finished.connect(on_done)
        self._lift_anim = anim
        anim.start()

    def _on_hover_color(self, color):
        self.setStyleSheet(self._card_stylesheet(color, self._hover_border))

    def _update_primary(self, installed: bool):
        self.primary_btn.setText("Play" if installed else "Install")
        self.primary_btn.setObjectName("PlayButton" if installed else "InstallButton")
        self.primary_btn.setEnabled(not self._game_running if installed else True)
        self._repolish(self.primary_btn)

    def _build_menu(self, installed: bool):
        self.menu.clear()
        self.menu.addAction("Settings", lambda: self.settings_clicked.emit(self.modpack))
        if installed:
            self.menu.addAction("Reinstall", lambda: self.install_clicked.emit(self.modpack))
            self.menu.addAction("Delete", lambda: self.delete_clicked.emit(self.modpack))

    def set_installed(self, installed: bool, game_running: bool = False):
        self._installed = installed
        self._game_running = game_running
        self._update_primary(installed)
        self._build_menu(installed)
        if self._servers:
            self.set_servers(self._servers)

    def set_servers(self, servers: list):
        self._servers = servers or []
        while self.servers_container.count():
            item = self.servers_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        if not self._servers:
            return

        header = QLabel("Servers", self)
        header.setObjectName("ServerHeader")
        self.servers_container.addWidget(header)

        for s in self._servers:
            row = QWidget(self)
            row.setObjectName("ServerRow")
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 4, 0, 4)
            h.setSpacing(8)

            label = QLabel(self._server_text(s), row)
            label.setObjectName("ServerLabel")
            label.setProperty("status", self._server_status(s))
            self._repolish(label)
            h.addWidget(label, 1)

            banned = bool(s.get("banned"))
            btn = QPushButton("Banned" if banned else "Connect", row)
            btn.setObjectName("ServerButton")
            can_connect = bool(s.get("online")) and not self._game_running and not banned
            btn.setEnabled(can_connect)
            btn.clicked.connect(lambda checked=False, srv=s: self.connect_clicked.emit(self.modpack, srv))
            h.addWidget(btn)
            self.servers_container.addWidget(row)
            fade_in(row, duration=240)

    def _server_text(self, s: dict) -> str:
        name = s.get("name") or "Server"
        if s.get("banned"):
            text = f"{name}: BANNED"
            expires = s.get("ban_expires")
            if expires:
                text += f" (until {expires})"
            return text
        if s.get("running") and not s.get("online"):
            return f"{name}: starting..."
        if s.get("online"):
            parts = [f"{name}: Online"]
            ping = s.get("latency_ms")
            if ping is not None:
                parts.append(f"{ping} ms")
            po = s.get("players_online")
            pm = s.get("players_max")
            if po is not None:
                parts.append(f"{po}/{pm} players")
            ver = s.get("version")
            if ver:
                parts.append(ver)
            return "  |  ".join(parts)
        return f"{name}: Offline"

    def _server_status(self, s: dict) -> str:
        if s.get("banned"):
            return "banned"
        if s.get("running") and not s.get("online"):
            return "starting"
        if s.get("online"):
            return "online"
        return "offline"
