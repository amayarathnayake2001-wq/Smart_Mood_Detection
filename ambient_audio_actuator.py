import os
import sys

USER_SCRIPT_PATH = r"C:\Users\USER\AppData\Roaming\Python\Python311\Scripts"
if USER_SCRIPT_PATH not in os.environ["PATH"]:
    os.environ["PATH"] += os.pathsep + USER_SCRIPT_PATH

import vlc
import time
import requests
import json 

BASE_URL = "https://mood-detection-eb7e1-default-rtdb.asia-southeast1.firebasedatabase.app/"

class AmbientAudioEngine:
    def __init__(self):
        self.current_player = None
        self.last_played_mood = ""

    def get_firebase_node(self, node_name):
        try:
            # Appending .json to the node name as required by Firebase REST API
            response = requests.get(f"{BASE_URL}{node_name}.json")
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error fetching data from node '{node_name}': {e}")
        return None

    def play_track(self, track_url, title, artist):
        import webbrowser
        
        print(f"\n[ACTUATING VISUAL THERAPY] Opening YouTube: '{title}' by {artist}")
        print(f"URL: {track_url}")
        
        # This opens the YouTube track link directly in your default web browser tab
        webbrowser.open(track_url)

    def run(self):
        print("Starting Ambient Audio Actuator Engine...")
        print("Monitoring Firebase console data transitions...\n")
        
        while True:
            # 1. Read the system_status node updated by your camera pipeline
            status_data = self.get_firebase_node("system_status")
            
            if status_data and "current_emotion" in status_data:
                detected_mood = status_data["current_emotion"].lower()
                
                # Maps standard DeepFace classifications to your playlist nodes [cite: 89, 105]
                mood_mapping = {
                    "happy": "happy",
                    "sad": "sad",
                    "angry": "anxious", 
                    "fear": "anxious",
                    "neutral": "happy",    
                    "surprise": "happy"
                }
                
                target_mood = mood_mapping.get(detected_mood, detected_mood)

                # 2. Trigger actuation loop only if the mood status shifts
                if target_mood != self.last_played_mood:
                    print(f"\n[MOOD CHANGE] Detected shift to: {target_mood.upper()}")
                    
                    # 3. Read specific playlist node directly from your tree structure
                    playlists = self.get_firebase_node("playlists")
                    
                    if playlists and target_mood in playlists:
                        playlist = playlists[target_mood]
                        # Grab the first available track object (e.g., track_1)
                        first_track_key = list(playlist.keys())[0]
                        track = playlist[first_track_key]
                        
                        # 4. Stream audio from URL
                        self.play_track(track["url"], track["title"], track["artist"])
                        self.last_played_mood = target_mood
                    else:
                        print(f"Alert: No playlist matching '{target_mood}' configured in console tree.")
            
            # 2-second polling window to match a low-latency database sync [cite: 119]
            time.sleep(2)

if __name__ == "__main__":
    engine = AmbientAudioEngine()
    engine.run()