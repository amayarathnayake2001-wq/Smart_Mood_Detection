class MusicPlayer:
    def __init__(self, music_dir: str):
        pygame.mixer.init()
        self.music_dir = music_dir
        self.current_emotion = None
        self.track_started_at = 0.0

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
        self.track_started_at = time.time()
        print(f"[MUSIC] Now playing '{track}' for emotion: {emotion}")

    def can_switch(self) -> bool:
        return (time.time() - self.track_started_at) >= MIN_TRACK_PLAY_SECONDS

    def maybe_switch(self, emotion: str):
        if emotion == self.current_emotion:
            return
        if self.current_emotion is not None and not self.can_switch():
            return  # too soon, let current track keep playing
        self.play(emotion)
