import threading
import time
import sys
import os

# Ensure the src directory is in the python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.ambient_audio_actuator import AmbientAudioEngine
from src.emotion_pipeline_firebase import main as start_camera

def start_actuator():
    print("[System] Initializing Ambient Audio Actuator...")
    engine = AmbientAudioEngine()
    engine.run()

if __name__ == "__main__":
    print("="*50)
    print("Starting Smart Mood Detection System...")
    print("="*50)
    
    # Start the audio actuator in a background thread
    actuator_thread = threading.Thread(target=start_actuator, daemon=True)
    actuator_thread.start()
    
    # Give the actuator a second to connect to Firebase
    time.sleep(1)
    
    print("[System] Initializing Camera Pipeline...")
    # Start the OpenCV camera pipeline in the main thread
    # Note: OpenCV GUI (cv2.imshow) MUST run in the main thread on Windows
    start_camera()
