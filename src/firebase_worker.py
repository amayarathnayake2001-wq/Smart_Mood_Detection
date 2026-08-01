import time

from PySide6.QtCore import QThread, Signal

from .firebase_client import (
    get_auto_mode,
    init_firebase,
    is_firebase_ready,
    read_current_state,
)


class FirebaseWorker(QThread):
    state_received = Signal(dict)
    connection_changed = Signal(bool, str)

    def __init__(self, poll_seconds: float = 2.0, parent=None):
        super().__init__(parent)
        self.poll_seconds = poll_seconds
        self._running = True
        self._last_connection = None

    def run(self):
        if not is_firebase_ready():
            init_firebase()

        while self._running:
            ready = is_firebase_ready()
            state = read_current_state() if ready else {}
            connected = bool(ready and state)

            if connected != self._last_connection:
                message = "Connected" if connected else "Offline / waiting for data"
                self.connection_changed.emit(connected, message)
                self._last_connection = connected

            if state:
                state["_auto_mode"] = get_auto_mode()
                self.state_received.emit(state)

            steps = max(1, int(self.poll_seconds * 10))
            for _ in range(steps):
                if not self._running:
                    break
                time.sleep(0.1)

    def stop(self):
        self._running = False
        self.wait(3000)
