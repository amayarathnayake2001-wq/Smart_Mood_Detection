import os
import time
import random
import threading
import collections
from datetime import datetime


import cv2
import pygame
from deepface import DeepFace



#CONFIG

# How many recent frame-level predictions to keep for the majority-vote smoother.
SMOOTHING_WINDOW = 15

# Minimum confidence (0-100) a single-frame prediction needs to be counted at all.
MIN_CONFIDENCE = 40.0

# Emotion must be the stable 
STABILITY_SECONDS = 4.0

# Minimum time a track must play 
MIN_TRACK_PLAY_SECONDS = 20.0

# Run DeepFace analysis every N frames
ANALYZE_EVERY_N_FRAMES = 5


CAPTURE_WIDTH = 640
CAPTURE_HEIGHT = 480

# --- Firebase Realtime Database config ---

FIREBASE_CONFIG = {
    "apiKey": "AIzaSyCOp9ePhh_GUALCxYxnjFEk052MsXiXoUE",
  "authDomain": "mood-detection-eb7e1.firebaseapp.com",
  "databaseURL": "https://mood-detection-eb7e1-default-rtdb.asia-southeast1.firebasedatabase.app",
  "projectId": "mood-detection-eb7e1",
  "storageBucket": "mood-detection-eb7e1.firebasestorage.app",
  "messagingSenderId": "1004650169541",
  "appId": "1:1004650169541:web:4a089999a645188d175cac"
}


FIREBASE_EMAIL = ""
FIREBASE_PASSWORD = ""


EMOTIONS = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]

MUSIC_DIR = os.path.join(os.path.dirname(__file__), "music")
SUPPORTED_EXT = (".mp3", ".wav", ".ogg")


DETECTOR_BACKENDS = ["retinaface", "opencv"]


#FIREBASE  

_firebase_db = None
_firebase_ready = False


def init_firebase():
    
    global _firebase_db, _firebase_ready

    if FIREBASE_CONFIG.get("apiKey") == "AIzaSyCOp9ePhh_GUALCxYxnjFEk052MsXiXoUE":
        print("[FIREBASE] Config not filled in — running in local-only mode.")
        return

    try:
        import pyrebase
    except ImportError:
        print("[FIREBASE] pyrebase4 not installed (pip install pyrebase4) — "
              "running in local-only mode.")
        return

    try:
        app = pyrebase.initialize_app(FIREBASE_CONFIG)
        _firebase_db = app.database()
        if FIREBASE_EMAIL and FIREBASE_PASSWORD:
            auth = app.auth()
            auth.sign_in_with_email_and_password(FIREBASE_EMAIL, FIREBASE_PASSWORD)
        _firebase_ready = True
        print("[FIREBASE] Connected.")
    except Exception as e:
        print(f"[FIREBASE] Connection failed, running in local-only mode: {e}")


def read_environment() -> dict:
    
    if not _firebase_ready:
        return {}
    try:
        state = _firebase_db.child("current_state").get().val() or {}
        return {
            "temperature": state.get("temperature"),
            "humidity": state.get("humidity"),
            "light": state.get("light"),
            "noise": state.get("noise"),
        }
    except Exception as e:
        print(f"[FIREBASE] Could not read environment: {e}")
        return {}


def get_auto_mode() -> bool:
    
    if not _firebase_ready:
        return True
    try:
        val = _firebase_db.child("controls").child("auto_mode").get().val()
        return True if val is None else bool(val)
    except Exception:
        return True


def push_to_firebase(emotion: str, confidence: float):
    
    env = read_environment()
    timestamp = datetime.now().isoformat()

    if not _firebase_ready:
        print(f"[FIREBASE-OFFLINE] {timestamp} | emotion={emotion} "
              f"confidence={confidence:.1f}% env={env}")
        return

    try:
        _firebase_db.child("current_state").update({
            "emotion": emotion,
            "emotion_confidence": round(confidence, 1),
            "now_playing": emotion,
            "last_updated": timestamp,
        })
        _firebase_db.child("mood_history").push({
            "emotion": emotion,
            "confidence": round(confidence, 1),
            "timestamp": timestamp,
            **env,
        })
    except Exception as e:
        print(f"[FIREBASE] Write failed: {e}")


#MUSIC PLAYER

class MusicPlayer:
    def __init__(self, music_dir: str):
        pygame.mixer.init()
        self.music_dir = music_dir
        self.current_emotion = None
        self.track_started_at = 0.0

    def _tracks_for(self, emotion: str):
        folder = os.path.join(self.music_dir, emotion)
        if not os.path.isdir(folder):
            return []
        return [f for f in os.listdir(folder) if f.lower().endswith(SUPPORTED_EXT)]

    def play(self, emotion: str):
        tracks = self._tracks_for(emotion)
        if not tracks:
            print(f"[MUSIC] No tracks found for '{emotion}' in {self.music_dir}/{emotion}/ "
                  f"— add some .mp3/.wav files there.")
            return
        track = random.choice(tracks)
        path = os.path.join(self.music_dir, emotion, track)
        pygame.mixer.music.load(path)
        pygame.mixer.music.play(fade_ms=1500)
        self.current_emotion = emotion
        self.track_started_at = time.time()
        print(f"[MUSIC] Now playing '{track}' for emotion: {emotion}")

    def can_switch(self) -> bool:
        return (time.time() - self.track_started_at) >= MIN_TRACK_PLAY_SECONDS

    def maybe_switch(self, emotion: str):
        if emotion == self.current_emotion:
            return
        if self.current_emotion is not None and not self.can_switch():
            return  # too soon, let current track keep playing
        self.play(emotion)


#EMOTION SMOOTHING LOGIC 

class EmotionSmoother:


    def __init__(self):
        self.buffer = collections.deque(maxlen=SMOOTHING_WINDOW)
        self.stable_emotion = None
        self.candidate_emotion = None
        self.candidate_since = None

    def add_reading(self, emotion: str, confidence: float):
        if confidence < MIN_CONFIDENCE:
            return  # discard low-confidence noise
        self.buffer.append((emotion, confidence))

    def _majority(self):
        if not self.buffer:
            return None, 0.0
        weights = collections.defaultdict(float)
        counts = collections.defaultdict(int)
        for e, c in self.buffer:
            weights[e] += c
            counts[e] += 1
        best = max(weights, key=lambda e: weights[e])
        avg_conf = weights[best] / counts[best]
        return best, avg_conf

    def update(self):
        """Call once per loop iteration. Returns (stable_emotion, confidence, changed)."""
        majority_emotion, avg_conf = self._majority()
        if majority_emotion is None:
            return self.stable_emotion, 0.0, False

        now = time.time()
        if majority_emotion != self.candidate_emotion:
            self.candidate_emotion = majority_emotion
            self.candidate_since = now

        held_long_enough = (now - self.candidate_since) >= STABILITY_SECONDS
        changed = False
        if held_long_enough and self.stable_emotion != majority_emotion:
            self.stable_emotion = majority_emotion
            changed = True

        return self.stable_emotion, avg_conf, changed


# ANALYSIS WORKER 

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


# MAIN LOOP 

def pick_working_backend():
    for backend in DETECTOR_BACKENDS:
        try:
            DeepFace.analyze(
                img_path=cv2_dummy_frame(),
                actions=["emotion"],
                detector_backend=backend,
                enforce_detection=False,
                silent=True,
            )
            print(f"[INIT] Using face detector backend: {backend}")
            return backend
        except Exception:
            continue
    print("[INIT] Falling back to 'opencv' backend.")
    return "opencv"


def cv2_dummy_frame():
    import numpy as np
    return (255 * __import__("numpy").random.rand(48, 48, 3)).astype("uint8")


def run():
    init_firebase()
    backend = pick_working_backend()
    player = MusicPlayer(MUSIC_DIR)
    smoother = EmotionSmoother()
    worker = AnalysisWorker(backend)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_HEIGHT)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam. Check camera permissions/index.")

    frame_count = 0
    last_label = "warming up..."

    print("[RUN] Starting detection loop. Press 'q' to quit.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            # Hand every Nth frame to the background worker. This call
            # returns instantly — the display loop below never waits on it.
            frame_count += 1
            if frame_count % ANALYZE_EVERY_N_FRAMES == 0:
                worker.submit(frame)

            emotion, confidence, last_label = worker.get_latest()
            if emotion is not None:
                smoother.add_reading(emotion, confidence)

            stable_emotion, avg_conf, changed = smoother.update()
            if changed and stable_emotion is not None:
                print(f"[EMOTION] Stabilized on '{stable_emotion}' ({avg_conf:.1f}% avg confidence)")
                push_to_firebase(stable_emotion, avg_conf)
                if get_auto_mode():
                    player.maybe_switch(stable_emotion)
                else:
                    print("[MUSIC] Skipped auto-switch — mobile app has auto_mode off.")

            # HUD overlay
            cv2.putText(frame, f"Live: {last_label}", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(frame, f"Stable: {stable_emotion or '...'}", (10, 55),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)
            cv2.putText(frame, f"Playing: {player.current_emotion or '-'}", (10, 85),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 0), 2)
            cv2.imshow("Smart Mood Detection - AI Module", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        worker.stop()
        cap.release()
        cv2.destroyAllWindows()
        pygame.mixer.quit()


if __name__ == "__main__":
    run()