import cv2
import pygame
from deepface import DeepFace

from src.config import DETECTOR_BACKENDS, MUSIC_DIR, CAPTURE_WIDTH, CAPTURE_HEIGHT, ANALYZE_EVERY_N_FRAMES
from src.firebase_client import init_firebase, push_to_firebase, get_auto_mode
from src.music_player import MusicPlayer
from src.emotion_smoother import EmotionSmoother
from src.analysis_worker import AnalysisWorker

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
