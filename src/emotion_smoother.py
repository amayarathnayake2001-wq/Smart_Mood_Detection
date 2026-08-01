import time
import collections
from .config import SMOOTHING_WINDOW, MIN_CONFIDENCE, STABILITY_SECONDS

class EmotionSmoother:
    def __init__(self):
        self.buffer = collections.deque(maxlen=SMOOTHING_WINDOW)
        self.stable_emotion = None
        self.candidate_emotion = None
        self.candidate_since = None

    def add_reading(self, emotion: str, confidence: float):
        if confidence < MIN_CONFIDENCE:
            return  # discard low-confidence noise
        self.buffer.append((emotion, confidence))

    def reset(self):
        self.buffer.clear()
        self.stable_emotion = None
        self.candidate_emotion = None
        self.candidate_since = None

    def _majority(self):
        if not self.buffer:
            return None, 0.0
        weights = collections.defaultdict(float)
        counts = collections.defaultdict(int)
        for e, c in self.buffer:
            weights[e] += c
            counts[e] += 1
        best = max(weights, key=lambda e: weights[e])
        avg_conf = weights[best] / counts[best]
        return best, avg_conf

    def update(self):
        """Call once per loop iteration. Returns (stable_emotion, confidence, changed)."""
        majority_emotion, avg_conf = self._majority()
        if majority_emotion is None:
            return self.stable_emotion, 0.0, False

        now = time.time()
        if majority_emotion != self.candidate_emotion:
            self.candidate_emotion = majority_emotion
            self.candidate_since = now

        held_long_enough = (now - self.candidate_since) >= STABILITY_SECONDS
        changed = False
        if held_long_enough and self.stable_emotion != majority_emotion:
            self.stable_emotion = majority_emotion
            changed = True

        return self.stable_emotion, avg_conf, changed
