import os
import time
import random
import pygame
from .config import SUPPORTED_EXT, MIN_TRACK_PLAY_SECONDS

class MusicPlayer:
    def __init__(self, music_dir: str):
        pygame.mixer.init()
        self.music_dir = music_dir
        self.current_emotion = None
        self.current_track = None
        self.track_started_at = 0.0
        self.volume = 0.7
        self.paused = False
        self.stopped = True
        pygame.mixer.music.set_volume(self.volume)

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
        self.current_track = track
        self.track_started_at = time.time()
        self.paused = False
        self.stopped = False
        print(f"[MUSIC] Now playing '{track}' for emotion: {emotion}")
        return track

    def can_switch(self) -> bool:
        return (time.time() - self.track_started_at) >= MIN_TRACK_PLAY_SECONDS

    def maybe_switch(self, emotion: str):
        if emotion == self.current_emotion:
            return
        if self.current_emotion is not None and not self.can_switch():
            return  # too soon, let current track keep playing
        return self.play(emotion)

    def toggle_pause(self):
        if self.paused:
            pygame.mixer.music.unpause()
            self.paused = False
            self.stopped = False
            return "playing"
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()
            self.paused = True
            return "paused"
        if self.current_emotion:
            self.play(self.current_emotion)
            return "playing"
        return "stopped"

    def stop(self):
        pygame.mixer.music.stop()
        self.paused = False
        self.stopped = True

    def next_track(self):
        if self.current_emotion:
            return self.play(self.current_emotion)
        return None

    def set_volume(self, value: float):
        self.volume = max(0.0, min(1.0, value))
        pygame.mixer.music.set_volume(self.volume)

    def is_playing(self) -> bool:
        return pygame.mixer.music.get_busy() and not self.paused

    def continue_playlist_if_finished(self):
        """Keep the current emotion playlist running after a track ends."""
        if (
            self.current_emotion
            and self.current_track
            and not self.paused
            and not self.stopped
            and not self.is_playing()
        ):
            return self.play(self.current_emotion)
        return None
