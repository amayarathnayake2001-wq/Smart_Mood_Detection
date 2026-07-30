import os
import cv2
import json
import time
import logging
import requests
import threading
from dotenv import load_dotenv
from deepface import DeepFace

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Fix #2: Validate BEFORE building the URL to avoid cryptic crashes
_db_url = os.getenv("FIREBASE_DATABASE_URL")
if not _db_url:
    raise ValueError("FIREBASE_DATABASE_URL not found in .env file")
FIREBASE_URL = f"{_db_url}system_status.json"

# Fix #1: Thread-safe lock to protect shared state between main and AI threads
state_lock = threading.Lock()

# Shared state between threads
shared_state = {
    "latest_frame": None,
    "current_emotion": "analyzing...",
    "bounding_box": None,  # (x, y, w, h)
    "running": True
}

# Fix #8: Minimum confidence threshold — ignore low-confidence detections
CONFIDENCE_THRESHOLD = 55.0


def ai_worker():
    """Background thread for DeepFace analysis and Firebase updates."""
    last_logged_emotion = ""
    logger.info("AI Background worker started.")

    while shared_state["running"]:
        # Fix #1: Read frame safely with lock
        with state_lock:
            frame = shared_state["latest_frame"]

        if frame is None:
            time.sleep(0.1)
            continue

        try:
            analysis = DeepFace.analyze(
                frame,
                actions=['emotion'],
                enforce_detection=False,
                detector_backend='mtcnn'
            )
            if isinstance(analysis, list):
                analysis = analysis[0]

            dominant_emotion = analysis['dominant_emotion']
            confidence = analysis['emotion'][dominant_emotion]
            region = analysis['region']

            # Fix #8: Skip low-confidence detections to prevent mood flickering
            if confidence < CONFIDENCE_THRESHOLD:
                logger.debug(f"Skipping low-confidence detection: {dominant_emotion} ({confidence:.1f}%)")
                time.sleep(0.5)
                continue

            # Fix #1: Write to shared state safely with lock
            with state_lock:
                shared_state["bounding_box"] = (region['x'], region['y'], region['w'], region['h'])
                shared_state["current_emotion"] = dominant_emotion

            # Sync to Firebase only when emotion changes
            if dominant_emotion != last_logged_emotion:
                logger.info(f"Syncing new mood to cloud: {dominant_emotion} (confidence: {confidence:.1f}%)")
                payload = json.dumps({"current_emotion": dominant_emotion})
                requests.patch(FIREBASE_URL, data=payload, timeout=5)
                last_logged_emotion = dominant_emotion

        except requests.exceptions.RequestException as e:
            logger.error(f"Firebase network error: {e}")
        except Exception as e:
            logger.warning(f"DeepFace error: {e}")

        # Cap AI inferences to ~2 FPS to save CPU
        time.sleep(0.5)


def main():
    # Fix #7: Use CAP_DSHOW on Windows to avoid MSMF errors
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        logger.error("Could not open laptop camera.")
        return

    # Start AI thread
    ai_thread = threading.Thread(target=ai_worker, daemon=True)
    ai_thread.start()

    logger.info("Camera initialized successfully! Starting video window...")

    while True:
        ret, frame = cap.read()
        if not ret:
            logger.error("Failed to grab frame.")
            break

        # Fix #1: Read shared state safely with lock
        with state_lock:
            emotion = shared_state["current_emotion"]
            bbox = shared_state["bounding_box"]

        # Share a copy of the latest frame for the AI thread
        with state_lock:
            shared_state["latest_frame"] = frame.copy()

        if bbox is not None:
            x, y, w, h = bbox
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, f"Mood: {emotion.upper()}", (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        cv2.imshow('AI Mood Detection (Firebase Active)', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    logger.info("Shutting down camera pipeline...")
    with state_lock:
        shared_state["running"] = False
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()