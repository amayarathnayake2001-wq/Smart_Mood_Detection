import unittest

from src.firebase_client import _merge_sensor_data


class FirebaseMappingTests(unittest.TestCase):
    def test_maps_actual_sensor_data_schema(self):
        result = _merge_sensor_data(
            {"emotion": "neutral"},
            {
                "climate": {"temperature_c": 22.3, "humidity_pct": 45.3},
                "light": {"analog_level": 120, "digital_trigger": False},
                "sound": {"analog_level": 450, "digital_trigger": True},
                "timestamp": 1052891,
            },
        )

        self.assertEqual(result["temperature"], 22.3)
        self.assertEqual(result["humidity"], 45.3)
        self.assertEqual(result["light"], 120)
        self.assertEqual(result["noise"], 450)
        self.assertFalse(result["light_trigger"])
        self.assertTrue(result["sound_trigger"])
        self.assertEqual(result["sensor_timestamp"], 1052891)
        self.assertEqual(result["emotion"], "neutral")


if __name__ == "__main__":
    unittest.main()
