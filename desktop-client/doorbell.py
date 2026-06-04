import sys
import threading
import time
import websocket

from datetime import datetime
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QUrl
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
    QTextEdit,
    QLabel,
    QSlider,
    QSystemTrayIcon,
    QMenu,
    QStyle
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtGui import QAction, QIcon


ESP_IP = "192.168.1.50"


class Signals(QObject):
    log = pyqtSignal(str)
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    touch_down = pyqtSignal()
    touch_up = pyqtSignal()


signals = Signals()

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class DoorbellApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(
        QIcon(resource_path("assets/icon.ico"))
        )
        self.setWindowTitle("Door Bell Monitor")
        self.resize(750, 550)
        self.setStyleSheet("""
        QWidget {
            background-color: #1e1e1e;
            color: white;
            font-size: 10pt;
        }
        QPushButton {
            background-color: #2d2d2d;
            border: 1px solid #555;
            padding: 8px;
            border-radius: 6px;
        }
        QPushButton:hover {
            background-color: #404040;
        }
        QTextEdit {
            background-color: #111;
            color: #00ff88;
            border: 1px solid #333;
            font-family: Consolas;
            font-size: 11pt;
        }
        QSlider::groove:horizontal {
            height: 6px;
            background: #333;
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            width: 16px;
            background: white;
            margin: -6px 0;
            border-radius: 8px;
        }
        """)

        layout = QVBoxLayout()

        self.status = QLabel("🔴 Disconnected")
        self.status.setStyleSheet("""
            font-size:14pt;
            font-weight:bold;
        """)
        layout.addWidget(self.status)

        buttons_layout = QHBoxLayout()
        self.choose_btn = QPushButton("🎵 Choose Sound")
        self.choose_btn.clicked.connect(self.choose_sound)
        self.clear_btn = QPushButton("🗑 Clear Log")
        self.clear_btn.clicked.connect(self.clear_log)
        buttons_layout.addWidget(self.choose_btn)
        buttons_layout.addWidget(self.clear_btn)
        layout.addLayout(buttons_layout)

        self.volume_label = QLabel("🔊 Volume: 80%")
        layout.addWidget(self.volume_label)

        volume_layout = QHBoxLayout()
        self.mute_btn = QPushButton("🔇")
        self.min_btn = QPushButton("🔉")
        self.max_btn = QPushButton("🔊")
        volume_layout.addWidget(self.mute_btn)
        volume_layout.addWidget(self.min_btn)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(80)
        volume_layout.addWidget(self.volume)
        volume_layout.addWidget(self.max_btn)
        layout.addLayout(volume_layout)

        self.logbox = QTextEdit()
        self.logbox.setReadOnly(True)
        layout.addWidget(self.logbox)

        self.setLayout(layout)

        # ===== Audio =====
        self.audio_output = QAudioOutput()
        self.audio_output.setVolume(0.8)
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)

        self.volume.valueChanged.connect(self.volume_changed)
        self.mute_btn.clicked.connect(lambda: self.volume.setValue(0))
        self.min_btn.clicked.connect(lambda: self.volume.setValue(10))
        self.max_btn.clicked.connect(lambda: self.volume.setValue(100))

        # ===== Signals =====
        signals.log.connect(self.add_log)
        signals.connected.connect(self.on_connected)
        signals.disconnected.connect(self.on_disconnected)
        signals.touch_down.connect(self.on_touch_down)
        signals.touch_up.connect(self.on_touch_up)

        # ===== Tray =====
        self.is_real_exit = False

        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(
            QIcon(resource_path("assets/icon.ico"))
        )

        tray_menu = QMenu()
        show_action = QAction("Open Door Bell", self)
        exit_action = QAction("Exit", self)

        show_action.triggered.connect(self.show_window)
        exit_action.triggered.connect(self.exit_app)

        tray_menu.addAction(show_action)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self.tray_activated)
        self.tray.show()

        # ===== Start WebSocket Thread =====
        threading.Thread(target=self.websocket_loop, daemon=True).start()

    # ====================== Methods ======================

    def clear_log(self):
        self.logbox.clear()

    def volume_changed(self, value):
        self.audio_output.setVolume(value / 100)
        self.volume_label.setText(f"🔊 Volume: {value}%")

    def choose_sound(self):
        file, _ = QFileDialog.getOpenFileName(
            self,
            "Select Sound",
            "",
            "Audio Files (*.mp3 *.wav *.ogg)"
        )
        if file:
            self.player.setSource(QUrl.fromLocalFile(file))
            self.add_log(f"🔊 Loaded sound: {file}")

    def add_log(self, text):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logbox.append(f"[{timestamp}] {text}")
        scrollbar = self.logbox.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()

    def exit_app(self):
        self.is_real_exit = True
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event):
        if not self.is_real_exit:
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "Door Bell Monitor",
                "Still running in system tray",
                QSystemTrayIcon.MessageIcon.Information,
                3000
            )
        else:
            event.accept()

    # ====================== WebSocket Events ======================

    def on_connected(self):
        self.setWindowTitle("🚪 Door Bell Monitor")
        self.status.setStyleSheet("""
            color: #00ff88;
            font-size:14pt;
            font-weight:bold;
        """)
        self.status.setText("🟢 Connected")

    def on_disconnected(self):
        self.setWindowTitle("🚪 Door Bell Monitor [OFFLINE]")
        self.status.setStyleSheet("""
            color: #ff5555;
            font-size:14pt;
            font-weight:bold;
        """)
        self.status.setText("🔴 Disconnected")

    def on_touch_down(self):
        self.add_log("👆 TOUCH START")

        self.tray.showMessage(
            "🚪 Door Bell",
            "Someone is at the door!",
            QSystemTrayIcon.MessageIcon.Information,
            5000
        )

        if self.player.source().isEmpty():
            return

        self.player.setPosition(0)
        self.player.play()

    def on_touch_up(self):
        self.add_log("👇 TOUCH END")
        self.player.stop()

    # ====================== WebSocket Loop ======================

    def websocket_loop(self):
        while True:
            try:
                signals.log.emit("⏳ Connecting...")
                ws = websocket.create_connection(
                    f"ws://{ESP_IP}/ws",
                    timeout=5
                )
                signals.connected.emit()
                signals.log.emit("🟢 Connected to ESP32")

                while True:
                    msg = ws.recv()
                    if msg == "down":
                        signals.touch_down.emit()
                    elif msg == "up":
                        signals.touch_up.emit()
                    elif msg == "ping":
                        pass

            except Exception as e:
                signals.disconnected.emit()
                signals.log.emit(f"🔴 Connection lost: {e}")
                time.sleep(1)


# ====================== Run App ======================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DoorbellApp()
    window.show()
    sys.exit(app.exec())