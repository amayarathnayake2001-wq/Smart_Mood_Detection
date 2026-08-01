import unittest
from unittest.mock import patch

from src.emotion_smoother import EmotionSmoother


class EmotionSmootherTests(unittest.TestCase):
    def test_low_confidence_reading_is_ignored(self):
        smoother = EmotionSmoother()
        smoother.add_reading("happy", 10.0)
        self.assertEqual(list(smoother.buffer), [])

    def test_candidate_becomes_stable_after_required_time(self):
        smoother = EmotionSmoother()
        smoother.add_reading("happy", 90.0)

        with patch("src.emotion_smoother.time.time", return_value=100.0):
            stable, _, changed = smoother.update()
        self.assertIsNone(stable)
        self.assertFalse(changed)

        with patch("src.emotion_smoother.time.time", return_value=105.0):
            stable, confidence, changed = smoother.update()
        self.assertEqual(stable, "happy")
        self.assertEqual(confidence, 90.0)
        self.assertTrue(changed)

    def test_reset_clears_session_state(self):
        smoother = EmotionSmoother()
        smoother.add_reading("sad", 80.0)
        smoother.candidate_emotion = "sad"
        smoother.candidate_since = 1.0
        smoother.stable_emotion = "sad"

        smoother.reset()

        self.assertEqual(list(smoother.buffer), [])
        self.assertIsNone(smoother.candidate_emotion)
        self.assertIsNone(smoother.candidate_since)
        self.assertIsNone(smoother.stable_emotion)


if __name__ == "__main__":
    unittest.main()
