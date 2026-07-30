"""
Model Pre-Downloader for Smart Mood Detection
==============================================
Run this script ONCE to pre-download all required DeepFace models
to the local cache (~/.deepface/weights/).

After running this, the main system will start instantly without
downloading anything on every run.
"""

import os

# Suppress TensorFlow noise during download
os.environ['TF_CPP_MIN_LOG_LEVEL']      = '3'
os.environ['TF_CPP_MIN_VLOG_LEVEL']     = '0'
os.environ['TF_ENABLE_ONEDNN_OPTS']     = '0'

import numpy as np

print("=" * 55)
print("  Smart Mood Detection - Model Pre-Downloader")
print("=" * 55)
print()

from deepface import DeepFace

# Use a dummy blank image to trigger model downloads via analyze()
# DeepFace caches all models on first use automatically
dummy_img = np.zeros((200, 200, 3), dtype=np.uint8)

# ── Step 1: Emotion model + RetinaFace (single analyze call) ──
print("[1/1] Downloading Emotion model + RetinaFace detector...")
print("      This may take a few minutes on first run...")
print()
try:
    DeepFace.analyze(
        dummy_img,
        actions=['emotion'],
        enforce_detection=False,
        detector_backend='retinaface',
        silent=False
    )
    print()
    print("      [OK] All models downloaded successfully.")
except Exception as e:
    print(f"      [NOTE] Got expected warning (no face in dummy image): {type(e).__name__}")
    print("      [OK] Models should still be cached.")

# ── Summary ────────────────────────────────────────────
weights_dir = os.path.join(os.path.expanduser("~"), ".deepface", "weights")
print()
print("=" * 55)
print("  Cached model files:")
if os.path.exists(weights_dir):
    all_ok = True
    for f in os.listdir(weights_dir):
        size_mb = os.path.getsize(os.path.join(weights_dir, f)) / (1024 * 1024)
        if f.endswith(".part"):
            status = "[INCOMPLETE]"
            all_ok = False
        else:
            status = "[OK]"
        print(f"  {status}  {f}  ({size_mb:.1f} MB)")

    print()
    if all_ok:
        print("  All models are ready!")
        print("  You can now run main.py without internet.")
    else:
        print("  WARNING: Some models are incomplete. Re-run this script.")
else:
    print("  Weights folder not found - something went wrong.")
print("=" * 55)
