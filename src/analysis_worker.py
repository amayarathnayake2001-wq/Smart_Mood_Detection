import time
import threading
from deepface import DeepFace

class AnalysisWorker:
    def __init__(self, backend: str):
        self.backend = backend
        self._lock = threading.Lock()
        self._latest_frame = None
        self._latest_result = (None, 0.0, "warming up...")  # (emotion, confidence, label)
        self._busy = False
        self._stop = False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def submit(self, frame):
        """Hand a new frame to the worker. Non-blocking; drops the frame if worker is busy."""
        if self._busy:
            return
        with self._lock:
            self._latest_frame = frame.copy()

    def get_latest(self):
        with self._lock:
            return self._latest_result

    def _loop(self):
        while not self._stop:
            with self._lock:
                frame = self._latest_frame
                self._latest_frame = None
            if frame is None:
                time.sleep(0.01)
                continue

            self._busy = True
            try:
                results = DeepFace.analyze(
                    img_path=frame,
                    actions=["emotion"],
                    detector_backend=self.backend,
                    enforce_detection=False,
                    silent=True,
                )
                result = results[0] if isinstance(results, list) else results
                raw_emotion = result["dominant_emotion"]
                confidence = float(result["emotion"][raw_emotion])
                label = f"{raw_emotion} ({confidence:.0f}%)"
                with self._lock:
                    self._latest_result = (raw_emotion, confidence, label)
            except Exception as e:
                with self._lock:
                    self._latest_result = (None, 0.0, f"detection error: {e}")
            finally:
                self._busy = False

    def stop(self):
        self._stop = True
