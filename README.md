# AI Module — Emotion Detection & Adaptive Music Playback

Your part of the Ambient Therapy System: detect facial emotion via webcam, and
automatically play music that matches it.

## 1. Setup on a New PC

To run this project on a new PC, follow these steps:

1. **Clone or Copy the Project**
   Copy the project files (do not copy the `venv` or `mood_env` folders as they are machine-specific).

2. **Create a Virtual Environment**
   ```bash
   python -m venv venv
   ```

3. **Activate the Environment**
   - Windows: `.\venv\Scripts\activate`
   - Mac/Linux: `source venv/bin/activate`

4. **Install Requirements**
   ```bash
   pip install -r requirements.txt
   # To fix TensorFlow/Keras compatibility issues:
   pip install tf-keras
   ```

First run will auto-download DeepFace's pretrained emotion model (~5-10MB) and the RetinaFace detector weights — needs internet the first time only.

## 2. Add music

Drop `.mp3`/`.wav`/`.ogg` files into these folders (already created) — one per
DeepFace's native emotion label, used directly with no collapsing:

```
music/
  angry/
  disgust/
  fear/
  happy/
  sad/
  surprise/
  neutral/
```

A few tracks per folder is enough — the player picks randomly from whichever
folder matches the stabilized emotion. `disgust` and `surprise` are the two
that are easy to forget — make sure they have at least one track too, or the
system will just log a "no tracks found" warning and skip playback when it
lands on those.

## 3. Run

```bash
python main.py
```

### Desktop dashboard

The desktop application reads sensor values from Firebase only. It does not
connect to the ESP32 REST API directly.

```bash
python desktop_app.py
```

The first desktop build includes:

- live camera and stabilized emotion detection;
- Firebase temperature, humidity, light, and noise cards;
- Firebase connection and camera status;
- automatic/manual music mode;
- play/pause, next, stop, and volume controls; and
- clean background-worker shutdown.

A webcam window opens showing:
- **Live** — the raw per-frame DeepFace reading (noisy, updates fast)
- **Stable** — the smoothed emotion the system has actually locked onto
- **Playing** — which music category is currently active

Press `q` to quit.

## 4. Architecture

The project has a modular architecture:
- **`main.py`**: The entry point and main video loop.
- **`src/config.py`**: All global constants and Firebase configuration.
- **`src/firebase_client.py`**: Firebase logic.
- **`src/music_player.py`**: Music playback using PyGame.
- **`src/emotion_smoother.py`**: A rolling window majority vote system to stabilize predictions.
- **`src/analysis_worker.py`**: A background thread for DeepFace analysis to avoid freezing the video feed.

### Tuning knobs (in `src/config.py`)
| Constant | Effect |
|---|---|
| `SMOOTHING_WINDOW` | Larger = smoother but slower to react |
| `MIN_CONFIDENCE` | Raise to ignore uncertain DeepFace calls |
| `STABILITY_SECONDS` | How long an emotion must persist before acting |
| `MIN_TRACK_PLAY_SECONDS` | Minimum time before a song can change |
| `ANALYZE_EVERY_N_FRAMES` | Lower = more responsive, more CPU |

### If accuracy is still shaky in testing
- Test in even, front-facing lighting first — this is the single biggest
  factor for facial emotion models.
- DeepFace's default model (trained on FER2013) is weakest at
  telling **fear vs. surprise** and **sad vs. neutral** apart.
