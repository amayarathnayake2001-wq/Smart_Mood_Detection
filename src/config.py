import os

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

# music dir is relative to the root project (one level up from src)
MUSIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "music")
SUPPORTED_EXT = (".mp3", ".wav", ".ogg")

DETECTOR_BACKENDS = ["retinaface", "opencv"]
