import os
import json
import time
import random
import logging
import requests
import webbrowser
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

BASE_URL = os.getenv("FIREBASE_DATABASE_URL")
if not BASE_URL:
    raise ValueError("FIREBASE_DATABASE_URL not found in .env file")

# Path to the local playlist file
PLAYLIST_JSON_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'playlist_data.json')

# Fix #9: Cooldown in seconds before the same URL can be opened again
TRACK_COOLDOWN_SECONDS = 120


class AmbientAudioEngine:
    def __init__(self):
        self.last_played_mood = ""
        # Fix #9: Track last opened URL and time to prevent browser tab spam
        self.last_opened_url = ""
        self.last_open_time = 0

    def get_firebase_node(self, node_name):
        try:
            response = requests.get(f"{BASE_URL}{node_name}.json", timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Error fetching Firebase node '{node_name}': {e}")
        return None

    def load_local_playlists(self):
        """Load playlists from the local JSON file."""
        try:
            with open(PLAYLIST_JSON_PATH, 'r') as f:
                data = json.load(f)
                return data.get("playlists")
        except Exception as e:
            logger.error(f"Error loading local playlist file: {e}")
            return None

    def play_track(self, track_url, title, artist):
        now = time.time()

        # Fix #9: Don't re-open same URL within the cooldown period
        if track_url == self.last_opened_url and (now - self.last_open_time) < TRACK_COOLDOWN_SECONDS:
            logger.info(f"Skipping '{title}' — already opened recently (cooldown active).")
            return

        self.last_opened_url = track_url
        self.last_open_time = now

        logger.info(f"[ACTUATING] Opening YouTube: '{title}' by {artist}")
        logger.info(f"URL: {track_url}")
        webbrowser.open(track_url)

    def run(self):
        logger.info("Ambient Audio Actuator Engine started.")
        logger.info("Monitoring Firebase for mood transitions...\n")

        # Fix #5 (mood mapping): "angry" now maps directly to the "angry" playlist.
        # "fear" still maps to "anxious" for calming therapy.
        mood_mapping = {
            "happy": "happy",
            "sad": "sad",
            "angry": "angry",
            "fear": "anxious",
            "neutral": "happy",
            "surprise": "happy",
            "disgust": "anxious",
        }

        while True:
            status_data = self.get_firebase_node("system_status")

            if status_data and "current_emotion" in status_data:
                detected_mood = status_data["current_emotion"].lower()
                target_mood = mood_mapping.get(detected_mood, detected_mood)

                if target_mood != self.last_played_mood:
                    logger.info(f"Mood shift detected: {detected_mood.upper()} → playing '{target_mood}' playlist")
                    self.last_played_mood = target_mood

                    playlists = self.load_local_playlists()

                    if playlists and target_mood in playlists:
                        playlist = playlists[target_mood]

                        # Fix #6: Randomly pick a track instead of always track_1
                        track_key = random.choice(list(playlist.keys()))
                        track = playlist[track_key]
                        logger.info(f"Selected track: {track_key}")

                        self.play_track(track["url"], track["title"], track["artist"])
                    else:
                        logger.warning(f"No playlist matching '{target_mood}' found in playlist_data.json.")

            # 2-second polling window
            time.sleep(2)


if __name__ == "__main__":
    engine = AmbientAudioEngine()
    engine.run()