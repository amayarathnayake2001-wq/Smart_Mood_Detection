import os

# Suppress TensorFlow C++ internal warnings (empty batch, CPU feature info, etc.)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_CPP_MIN_VLOG_LEVEL'] = '0'
import cv2
import json
import time
import logging
import requests
import threading
import numpy as np
from collections import deque, Counter
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

# Validate BEFORE building the URL
_db_url = os.getenv("FIREBASE_DATABASE_URL")
if not _db_url:
    raise ValueError("FIREBASE_DATABASE_URL not found in .env file")
FIREBASE_URL = f"{_db_url}system_status.json"

# Thread-safe lock to protect shared state
state_lock = threading.Lock()

# Shared state between main thread and AI worker thread
shared_state = {
    "latest_frame":     None,
    "current_emotion":  "analyzing...",
    "bounding_box":     None,       # (x, y, w, h)
    "emotion_scores":   {},         # raw scores dict for HUD
    "ema_scores":       {},         # smoothed scores for HUD
    "stable_progress":  0.0,        # 0.0 → 1.0 stability bar
    "running":          True
}

# ─────────────────────────────────────────────
# Accuracy Tuning Constants
# ─────────────────────────────────────────────
CONFIDENCE_THRESHOLD   = 40.0   # Minimum % confidence to accept a prediction
MAJORITY_WINDOW_SIZE   = 7      # Frames kept for majority vote (Improvement #1)
STABLE_DURATION_SECS   = 2.0    # Seconds a mood must persist to be committed (Improvement #2)
MIN_FACE_SIZE_PX       = 60     # Minimum face width/height in pixels (Improvement #4)
BLUR_THRESHOLD         = 40.0   # Laplacian variance below this = too blurry (Improvement #4)
EMA_ALPHA              = 0.3    # EMA weight: 0.1=very smooth, 0.5=reactive (Improvement #5)

EMOTION_LABELS = ['angry', 'disgust', 'fear', 'happy', 'sad', 'surprise', 'neutral']


# ─────────────────────────────────────────────
# Improvement #3 — CLAHE Lighting Normalization
# ─────────────────────────────────────────────
def preprocess_frame(frame: np.ndarray) -> np.ndarray:
    """
    Enhance contrast using CLAHE on the Luminance channel (LAB color space).
    Dramatically improves DeepFace accuracy in dim rooms or backlit conditions.
    """
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l)
    enhanced_lab = cv2.merge([l_enhanced, a, b])
    return cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)


# ─────────────────────────────────────────────
# Improvement #4 — Face Quality Gate
# ─────────────────────────────────────────────
def is_face_quality_ok(frame: np.ndarray, region: dict) -> bool:
    """
    Returns False if the detected face region is too small or too blurry.
    Filtering out low-quality detections prevents garbage-in→garbage-out.
    """
    x, y, w, h = region['x'], region['y'], region['w'], region['h']

    # Gate 1: Face must be large enough to be meaningful
    if w < MIN_FACE_SIZE_PX or h < MIN_FACE_SIZE_PX:
        logger.debug(f"Face too small ({w}x{h}px < {MIN_FACE_SIZE_PX}px), skipping.")
        return False

    # Gate 2: Reject motion-blurred or out-of-focus frames
    face_crop = frame[y:y + h, x:x + w]
    if face_crop.size == 0:
        return False
    gray_crop = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
    blur_score = cv2.Laplacian(gray_crop, cv2.CV_64F).var()
    if blur_score < BLUR_THRESHOLD:
        logger.debug(f"Frame too blurry (Laplacian={blur_score:.1f} < {BLUR_THRESHOLD}), skipping.")
        return False

    return True


# ─────────────────────────────────────────────
# Improvement #6 — Enhanced HUD Drawing
# ─────────────────────────────────────────────
def draw_hud(frame: np.ndarray, emotion: str, confidence: float,
             ema_scores: dict, stable_progress: float) -> np.ndarray:
    """
    Draw a rich HUD overlay:
      - Bounding box label with confidence %
      - Vertical emotion probability bars (EMA smoothed)
      - Stability progress bar (debounce indicator)
    """
    h_frame, w_frame = frame.shape[:2]

    # ── Emotion bars panel (top-left) ──
    panel_x, panel_y = 10, 10
    bar_max_width = 130
    bar_height = 16
    bar_gap = 22

    for i, label in enumerate(EMOTION_LABELS):
        score = ema_scores.get(label, 0.0)
        y_pos = panel_y + i * bar_gap

        # Background track
        cv2.rectangle(frame, (panel_x, y_pos),
                      (panel_x + bar_max_width, y_pos + bar_height),
                      (40, 40, 40), -1)

        # Filled bar
        bar_fill = int(score / 100.0 * bar_max_width)
        is_dominant = (label == emotion)
        color = (50, 220, 100) if is_dominant else (100, 130, 200)
        cv2.rectangle(frame, (panel_x, y_pos),
                      (panel_x + bar_fill, y_pos + bar_height),
                      color, -1)

        # Label + percentage text
        text = f"{label[:3].upper()}  {score:.0f}%"
        cv2.putText(frame, text,
                    (panel_x + bar_max_width + 6, y_pos + 13),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                    (220, 220, 220), 1, cv2.LINE_AA)

    # ── Stability progress bar (bottom of panel) ──
    stab_y = panel_y + len(EMOTION_LABELS) * bar_gap + 8
    stab_fill = int(stable_progress * bar_max_width)
    cv2.rectangle(frame, (panel_x, stab_y),
                  (panel_x + bar_max_width, stab_y + 10), (50, 50, 50), -1)
    stab_color = (0, 200, 255) if stable_progress < 1.0 else (0, 255, 120)
    cv2.rectangle(frame, (panel_x, stab_y),
                  (panel_x + stab_fill, stab_y + 10), stab_color, -1)
    cv2.putText(frame, "STABILITY",
                (panel_x + bar_max_width + 6, stab_y + 9),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 180, 180), 1, cv2.LINE_AA)

    return frame


# ─────────────────────────────────────────────
# AI Worker Thread
# ─────────────────────────────────────────────
def ai_worker():
    """
    Background thread: runs DeepFace analysis at ~2 FPS.
    Applies all 5 accuracy improvements before committing a mood change.
    """
    last_synced_emotion = ""

    # Improvement #1 — Temporal majority voting window
    emotion_window = deque(maxlen=MAJORITY_WINDOW_SIZE)

    # Improvement #2 — Stable mood timer state
    candidate_emotion = ""
    candidate_start_time = 0.0

    # Improvement #5 — EMA score state (start uniform across all emotions)
    ema_scores = {label: 100.0 / len(EMOTION_LABELS) for label in EMOTION_LABELS}

    logger.info("AI Background worker started.")

    while shared_state["running"]:

        # Read latest frame safely
        with state_lock:
            frame = shared_state["latest_frame"]

        if frame is None:
            time.sleep(0.1)
            continue

        try:
            # Improvement #3 — CLAHE preprocessing before analysis
            processed = preprocess_frame(frame)

            analysis = DeepFace.analyze(
                processed,
                actions=['emotion'],
                enforce_detection=False,
                detector_backend='yunet'  # Fast OpenCV-native detector, no TF overhead
            )
            if isinstance(analysis, list):
                analysis = analysis[0]

            raw_emotion   = analysis['dominant_emotion']
            raw_scores    = analysis['emotion']          # dict: {emotion: float}
            region        = analysis['region']
            confidence    = raw_scores[raw_emotion]

            # Improvement #4 — Face quality gate
            if not is_face_quality_ok(frame, region):
                time.sleep(0.5)
                continue

            # Confidence gate (already in place)
            if confidence < CONFIDENCE_THRESHOLD:
                logger.debug(f"Low confidence: {raw_emotion} ({confidence:.1f}%), skipping.")
                time.sleep(0.5)
                continue

            # Improvement #5 — Update EMA scores
            for label in EMOTION_LABELS:
                new_val = raw_scores.get(label, 0.0)
                ema_scores[label] = EMA_ALPHA * new_val + (1 - EMA_ALPHA) * ema_scores[label]

            # Improvement #1 — Add to majority voting window
            emotion_window.append(raw_emotion)
            majority_emotion = Counter(emotion_window).most_common(1)[0][0]

            # Improvement #2 — Stable mood timer (debounce)
            if majority_emotion != candidate_emotion:
                candidate_emotion  = majority_emotion
                candidate_start_time = time.time()

            elapsed        = time.time() - candidate_start_time
            progress       = min(elapsed / STABLE_DURATION_SECS, 1.0)
            stable_emotion = candidate_emotion if elapsed >= STABLE_DURATION_SECS else None

            # Write display data to shared state
            with state_lock:
                shared_state["bounding_box"]    = (region['x'], region['y'], region['w'], region['h'])
                shared_state["emotion_scores"]  = raw_scores
                shared_state["ema_scores"]      = dict(ema_scores)
                shared_state["stable_progress"] = progress
                # Always show candidate emotion (even before stable commit) so HUD is not blank
                shared_state["current_emotion"] = stable_emotion if stable_emotion else f"{candidate_emotion} (detecting...)"

            # Sync stable emotion to Firebase only when it changes
            if stable_emotion and stable_emotion != last_synced_emotion:
                logger.info(
                    f"Stable mood confirmed: {stable_emotion.upper()} "
                    f"(majority over {MAJORITY_WINDOW_SIZE} frames, "
                    f"held for {STABLE_DURATION_SECS}s, confidence={confidence:.1f}%)"
                )
                payload = json.dumps({"current_emotion": stable_emotion})
                requests.patch(FIREBASE_URL, data=payload, timeout=5)
                last_synced_emotion = stable_emotion

        except requests.exceptions.RequestException as e:
            logger.error(f"Firebase network error: {e}")
        except Exception as e:
            logger.warning(f"DeepFace error: {e}")

        # ~2 FPS AI inference cap
        time.sleep(0.5)


# ─────────────────────────────────────────────
# Main Camera Loop
# ─────────────────────────────────────────────
def main():
    # CAP_DSHOW on Windows prevents MSMF driver errors
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        logger.error("Could not open laptop camera.")
        return

    ai_thread = threading.Thread(target=ai_worker, daemon=True)
    ai_thread.start()
    logger.info("Camera initialized. Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            logger.error("Failed to grab frame.")
            break

        # Push latest frame to AI worker
        with state_lock:
            shared_state["latest_frame"] = frame.copy()

        # Read display data safely
        with state_lock:
            emotion        = shared_state["current_emotion"]
            bbox           = shared_state["bounding_box"]
            ema_scores     = shared_state["ema_scores"]
            stable_prog    = shared_state["stable_progress"]
            confidence     = shared_state["emotion_scores"].get(emotion, 0.0)

        # Draw bounding box and mood label
        if bbox is not None:
            x, y, w, h = bbox
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 230, 100), 2)
            label_text = f"{emotion.upper()}  {confidence:.0f}%"
            cv2.putText(frame, label_text, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 230, 100), 2, cv2.LINE_AA)

        # Improvement #6 — Draw rich HUD
        if ema_scores:
            frame = draw_hud(frame, emotion, confidence, ema_scores, stable_prog)

        cv2.imshow('AI Mood Detection — Enhanced', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    logger.info("Shutting down...")
    with state_lock:
        shared_state["running"] = False
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()