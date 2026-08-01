from datetime import datetime
import threading
from .config import FIREBASE_CONFIG, FIREBASE_EMAIL, FIREBASE_PASSWORD

_firebase_db = None
_firebase_ready = False
_firebase_lock = threading.RLock()

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
        return True
    except Exception as e:
        _firebase_ready = False
        print(f"[FIREBASE] Connection failed, running in local-only mode: {e}")
        return False

def is_firebase_ready() -> bool:
    return _firebase_ready

def _merge_sensor_data(state: dict, sensor_data: dict) -> dict:
    """Normalize the ESP32 Firebase schema for desktop consumers."""
    merged = dict(state or {})
    sensor_data = sensor_data or {}
    climate = sensor_data.get("climate") or {}
    light = sensor_data.get("light") or {}
    sound = sensor_data.get("sound") or {}

    merged["temperature"] = climate.get(
        "temperature_c", merged.get("temperature")
    )
    merged["humidity"] = climate.get("humidity_pct", merged.get("humidity"))
    merged["light"] = light.get("analog_level", merged.get("light"))
    merged["noise"] = sound.get("analog_level", merged.get("noise"))
    merged["light_trigger"] = light.get("digital_trigger")
    merged["sound_trigger"] = sound.get("digital_trigger")
    merged["sensor_timestamp"] = sensor_data.get("timestamp")
    return merged

def read_current_state() -> dict:
    if not _firebase_ready:
        return {}
    try:
        with _firebase_lock:
            state = _firebase_db.child("current_state").get().val() or {}
            sensor_data = _firebase_db.child("sensorData").get().val() or {}
        return _merge_sensor_data(state, sensor_data)
    except Exception as e:
        print(f"[FIREBASE] Could not read current state: {e}")
        return {}

def read_environment() -> dict:
    state = read_current_state()
    return {
        "temperature": state.get("temperature"),
        "humidity": state.get("humidity"),
        "light": state.get("light"),
        "noise": state.get("noise"),
    }

def get_auto_mode() -> bool:
    if not _firebase_ready:
        return True
    try:
        with _firebase_lock:
            val = _firebase_db.child("controls").child("auto_mode").get().val()
        return True if val is None else bool(val)
    except Exception:
        return True

def set_auto_mode(enabled: bool) -> bool:
    if not _firebase_ready:
        return False
    try:
        with _firebase_lock:
            _firebase_db.child("controls").child("auto_mode").set(bool(enabled))
        return True
    except Exception as e:
        print(f"[FIREBASE] Could not update auto mode: {e}")
        return False

def push_to_firebase(emotion: str, confidence: float):
    env = read_environment()
    timestamp = datetime.now().isoformat()

    if not _firebase_ready:
        print(f"[FIREBASE-OFFLINE] {timestamp} | emotion={emotion} "
              f"confidence={confidence:.1f}% env={env}")
        return

    try:
        with _firebase_lock:
            _firebase_db.child("current_state").update({
                "emotion": emotion,
                "emotion_confidence": round(confidence, 1),
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

def update_playback_state(emotion: str | None, track: str | None, playing: bool):
    if not _firebase_ready:
        return False
    try:
        with _firebase_lock:
            _firebase_db.child("current_state").child("now_playing").set({
                "emotion": emotion,
                "track": track,
                "playing": bool(playing),
                "updated_at": datetime.now().isoformat(),
            })
        return True
    except Exception as e:
        print(f"[FIREBASE] Could not update playback state: {e}")
        return False
