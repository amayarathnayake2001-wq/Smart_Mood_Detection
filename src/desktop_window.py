from datetime import datetime
import threading

import cv2
import pygame
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .analysis_worker import AnalysisWorker
from .config import (
    ANALYZE_EVERY_N_FRAMES,
    CAPTURE_HEIGHT,
    CAPTURE_WIDTH,
    DETECTOR_BACKENDS,
    MUSIC_DIR,
)
from .emotion_smoother import EmotionSmoother
from .firebase_client import (
    push_to_firebase,
    set_auto_mode,
    update_playback_state,
)
from .firebase_worker import FirebaseWorker
from .music_player import MusicPlayer


class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "--", parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        layout = QVBoxLayout(self)
        title_label = QLabel(title)
        title_label.setObjectName("metricTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("metricValue")
        layout.addWidget(title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str):
        self.value_label.setText(value)


class DashboardWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Mood Detection")
        self.resize(1240, 780)

        self.capture = None
        self.analysis_worker = None
        self.frame_number = 0
        self.last_result_id = -1
        self.session_running = False
        self.smoother = EmotionSmoother()
        self.player = MusicPlayer(MUSIC_DIR)

        self.camera_timer = QTimer(self)
        self.camera_timer.timeout.connect(self._update_camera)
        self.player_timer = QTimer(self)
        self.player_timer.timeout.connect(self._update_player)
        self.player_timer.start(1000)

        self.firebase_worker = FirebaseWorker(parent=self)
        self.firebase_worker.state_received.connect(self._apply_firebase_state)
        self.firebase_worker.connection_changed.connect(self._firebase_connection_changed)

        self._build_ui()
        self._apply_styles()
        self.firebase_worker.start()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(24, 20, 24, 20)
        main.setSpacing(16)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Smart Mood Detection")
        title.setObjectName("appTitle")
        subtitle = QLabel("AI emotion analysis and Firebase sensor dashboard")
        subtitle.setObjectName("subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()

        self.firebase_status = QLabel("● Firebase connecting")
        self.firebase_status.setObjectName("statusOffline")
        self.camera_status = QLabel("● Camera stopped")
        self.camera_status.setObjectName("statusOffline")
        header.addWidget(self.firebase_status)
        header.addWidget(self.camera_status)
        main.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(18)

        camera_panel = QFrame()
        camera_panel.setObjectName("panel")
        camera_layout = QVBoxLayout(camera_panel)
        section_title = QLabel("Live emotion session")
        section_title.setObjectName("sectionTitle")
        camera_layout.addWidget(section_title)

        self.camera_view = QLabel("Select Start Session to enable the camera")
        self.camera_view.setAlignment(Qt.AlignCenter)
        self.camera_view.setMinimumSize(640, 480)
        self.camera_view.setObjectName("cameraView")
        camera_layout.addWidget(self.camera_view, 1)

        detection_row = QHBoxLayout()
        self.live_emotion = QLabel("Live: --")
        self.stable_emotion = QLabel("Stable: --")
        self.confidence = QLabel("Confidence: --")
        detection_row.addWidget(self.live_emotion)
        detection_row.addWidget(self.stable_emotion)
        detection_row.addWidget(self.confidence)
        camera_layout.addLayout(detection_row)

        controls = QHBoxLayout()
        self.session_button = QPushButton("Start Session")
        self.session_button.clicked.connect(self._toggle_session)
        self.auto_mode = QCheckBox("Automatic music")
        self.auto_mode.setChecked(True)
        self.auto_mode.toggled.connect(self._set_auto_mode)
        controls.addWidget(self.session_button)
        controls.addWidget(self.auto_mode)
        controls.addStretch()
        camera_layout.addLayout(controls)
        content.addWidget(camera_panel, 3)

        sidebar = QVBoxLayout()
        sensor_panel = QFrame()
        sensor_panel.setObjectName("panel")
        sensor_layout = QVBoxLayout(sensor_panel)
        sensor_title = QLabel("Firebase sensor data")
        sensor_title.setObjectName("sectionTitle")
        sensor_layout.addWidget(sensor_title)

        sensor_grid = QGridLayout()
        self.temperature_card = MetricCard("Temperature")
        self.humidity_card = MetricCard("Humidity")
        self.light_card = MetricCard("Light level")
        self.noise_card = MetricCard("Noise level")
        sensor_grid.addWidget(self.temperature_card, 0, 0)
        sensor_grid.addWidget(self.humidity_card, 0, 1)
        sensor_grid.addWidget(self.light_card, 1, 0)
        sensor_grid.addWidget(self.noise_card, 1, 1)
        sensor_layout.addLayout(sensor_grid)
        self.sensor_updated = QLabel("Last update: waiting for Firebase")
        self.sensor_updated.setObjectName("subtitle")
        sensor_layout.addWidget(self.sensor_updated)
        sidebar.addWidget(sensor_panel)

        music_panel = QFrame()
        music_panel.setObjectName("panel")
        music_layout = QVBoxLayout(music_panel)
        music_title = QLabel("Music player")
        music_title.setObjectName("sectionTitle")
        self.track_label = QLabel("No track playing")
        self.track_label.setWordWrap(True)
        music_layout.addWidget(music_title)
        music_layout.addWidget(self.track_label)

        player_buttons = QHBoxLayout()
        pause_button = QPushButton("Play / Pause")
        pause_button.clicked.connect(self.player.toggle_pause)
        next_button = QPushButton("Next")
        next_button.clicked.connect(self._next_track)
        stop_button = QPushButton("Stop")
        stop_button.clicked.connect(self._stop_music)
        player_buttons.addWidget(pause_button)
        player_buttons.addWidget(next_button)
        player_buttons.addWidget(stop_button)
        music_layout.addLayout(player_buttons)

        volume_row = QHBoxLayout()
        volume_row.addWidget(QLabel("Volume"))
        volume = QSlider(Qt.Horizontal)
        volume.setRange(0, 100)
        volume.setValue(70)
        volume.valueChanged.connect(lambda value: self.player.set_volume(value / 100))
        volume_row.addWidget(volume)
        music_layout.addLayout(volume_row)
        sidebar.addWidget(music_panel)
        sidebar.addStretch()
        content.addLayout(sidebar, 2)
        main.addLayout(content, 1)

    def _apply_styles(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #0f172a; color: #e2e8f0; }
            #appTitle { font-size: 28px; font-weight: 700; }
            #subtitle { color: #94a3b8; }
            #sectionTitle { font-size: 17px; font-weight: 650; margin-bottom: 6px; }
            #panel {
                background: #172033;
                border: 1px solid #27344d;
                border-radius: 14px;
            }
            #cameraView {
                background: #080d18;
                border: 1px solid #334155;
                border-radius: 10px;
                color: #64748b;
            }
            #metricCard {
                background: #111b2e;
                border: 1px solid #2b3a55;
                border-radius: 10px;
                min-height: 82px;
            }
            #metricTitle { color: #94a3b8; font-size: 12px; }
            #metricValue { font-size: 22px; font-weight: 700; color: #67e8f9; }
            #statusOnline { color: #4ade80; padding: 7px; }
            #statusOffline { color: #fbbf24; padding: 7px; }
            QPushButton {
                background: #2563eb;
                border: none;
                border-radius: 7px;
                padding: 9px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: #3b82f6; }
            QCheckBox { spacing: 8px; }
        """)

    def _toggle_session(self):
        if self.session_running:
            self._stop_session()
        else:
            self._start_session()

    def _start_session(self):
        self.capture = cv2.VideoCapture(0)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_WIDTH)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_HEIGHT)
        if not self.capture.isOpened():
            self.capture.release()
            self.capture = None
            QMessageBox.critical(self, "Camera error", "Could not open the webcam.")
            return

        self.smoother.reset()
        self.analysis_worker = AnalysisWorker(DETECTOR_BACKENDS[0])
        self.frame_number = 0
        self.last_result_id = -1
        self.session_running = True
        self.session_button.setText("Stop Session")
        self.camera_status.setText("● Camera active")
        self.camera_status.setObjectName("statusOnline")
        self.camera_status.style().unpolish(self.camera_status)
        self.camera_status.style().polish(self.camera_status)
        self.camera_timer.start(30)

    def _stop_session(self):
        self.camera_timer.stop()
        if self.analysis_worker:
            self.analysis_worker.stop()
            self.analysis_worker = None
        if self.capture:
            self.capture.release()
            self.capture = None
        self.session_running = False
        self.session_button.setText("Start Session")
        self.camera_status.setText("● Camera stopped")
        self.camera_status.setObjectName("statusOffline")
        self.camera_status.style().unpolish(self.camera_status)
        self.camera_status.style().polish(self.camera_status)
        self.camera_view.clear()
        self.camera_view.setText("Select Start Session to enable the camera")

    def _update_camera(self):
        if not self.capture or not self.analysis_worker:
            return
        ok, frame = self.capture.read()
        if not ok:
            self._stop_session()
            QMessageBox.warning(self, "Camera error", "The camera stream was interrupted.")
            return

        self.frame_number += 1
        if self.frame_number % ANALYZE_EVERY_N_FRAMES == 0:
            self.analysis_worker.submit(frame)

        result_id, emotion, confidence, label = self.analysis_worker.get_latest_with_id()
        self.live_emotion.setText(f"Live: {label}")
        if result_id != self.last_result_id:
            self.last_result_id = result_id
            if emotion:
                self.smoother.add_reading(emotion, confidence)

        stable, avg_confidence, changed = self.smoother.update()
        self.stable_emotion.setText(f"Stable: {stable or '--'}")
        self.confidence.setText(
            f"Confidence: {avg_confidence:.1f}%" if stable else "Confidence: --"
        )

        if changed and stable:
            self._firebase_write(push_to_firebase, stable, avg_confidence)
            if self.auto_mode.isChecked():
                track = self.player.maybe_switch(stable)
                if track:
                    self._publish_playback()

        # Mirror only the preview so it behaves like a normal front-facing
        # camera. Emotion analysis above still receives the original frame.
        preview_frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        image = QImage(rgb.data, width, height, channels * width, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(image).scaled(
            self.camera_view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.camera_view.setPixmap(pixmap)

    def _apply_firebase_state(self, state: dict):
        self.temperature_card.set_value(self._format_number(state.get("temperature"), "°C"))
        self.humidity_card.set_value(self._format_number(state.get("humidity"), "%"))
        self.light_card.set_value(self._format_number(state.get("light"), ""))
        self.noise_card.set_value(self._format_number(state.get("noise"), ""))
        sensor_timestamp = state.get("sensor_timestamp")
        if sensor_timestamp is not None:
            self.sensor_updated.setText(f"Device timestamp: {sensor_timestamp} ms")
        else:
            timestamp = state.get("sensor_updated_at") or state.get("last_updated")
            self.sensor_updated.setText(
                f"Last update: {timestamp or datetime.now().isoformat(timespec='seconds')}"
            )

        firebase_auto = state.get("_auto_mode")
        if firebase_auto is not None and firebase_auto != self.auto_mode.isChecked():
            self.auto_mode.blockSignals(True)
            self.auto_mode.setChecked(bool(firebase_auto))
            self.auto_mode.blockSignals(False)

    def _firebase_connection_changed(self, connected: bool, message: str):
        self.firebase_status.setText(f"● Firebase {message.lower()}")
        self.firebase_status.setObjectName("statusOnline" if connected else "statusOffline")
        self.firebase_status.style().unpolish(self.firebase_status)
        self.firebase_status.style().polish(self.firebase_status)

    def _set_auto_mode(self, enabled: bool):
        self._firebase_write(set_auto_mode, enabled)

    def _update_player(self):
        track = self.player.continue_playlist_if_finished()
        if track:
            self._publish_playback()
        self.track_label.setText(self.player.current_track or "No track playing")

    def _next_track(self):
        if self.player.next_track():
            self._publish_playback()

    def _stop_music(self):
        self.player.stop()
        self._firebase_write(
            update_playback_state,
            self.player.current_emotion,
            self.player.current_track,
            False,
        )

    def _publish_playback(self):
        self.track_label.setText(self.player.current_track or "No track playing")
        self._firebase_write(
            update_playback_state,
            self.player.current_emotion,
            self.player.current_track,
            self.player.is_playing(),
        )

    @staticmethod
    def _firebase_write(function, *args):
        threading.Thread(target=function, args=args, daemon=True).start()

    @staticmethod
    def _format_number(value, suffix: str):
        if value is None:
            return "--"
        try:
            return f"{float(value):.1f}{suffix}"
        except (TypeError, ValueError):
            return f"{value}{suffix}"

    def closeEvent(self, event: QCloseEvent):
        self._stop_session()
        self.player_timer.stop()
        self.player.stop()
        self.firebase_worker.stop()
        pygame.mixer.quit()
        event.accept()
