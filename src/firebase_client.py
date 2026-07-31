from datetime import datetime
from .config import FIREBASE_CONFIG, FIREBASE_EMAIL, FIREBASE_PASSWORD

_firebase_db = None
_firebase_ready = False

def init_firebase():
    global _firebase_db, _firebase_ready

    if not FIREBASE_CONFIG.get("apiKey") or FIREBASE_CONFIG.get("apiKey") == "YOUR_API_KEY":
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
