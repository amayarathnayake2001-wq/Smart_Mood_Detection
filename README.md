# AI Module — Emotion Detection & Adaptive Music Playback

Your part of the Ambient Therapy System: detect facial emotion via webcam, and
automatically play music that matches it.

## 1. Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

First run will auto-download DeepFace's pretrained emotion model (~5-10MB) and
the RetinaFace detector weights — needs internet the first time only.

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
python emotion_music_system.py
```

A webcam window opens showing:
- **Live** — the raw per-frame DeepFace reading (noisy, updates fast)
- **Stable** — the smoothed emotion the system has actually locked onto
- **Playing** — which music category is currently active

Press `q` to quit.

## 4. Why this is more accurate than a naive "detect → play" loop

A single-frame emotion call is genuinely unreliable — blinking, talking, or a
half-second frown can flip the label. Three layers fix that:

1. **Better face detector**: `retinaface` backend (falls back to `opencv`
   automatically if RetinaFace isn't installed/working on your machine) —
   handles off-angle faces and uneven lighting much better than the default
   Haar cascade.
2. **Rolling majority vote**: the last 15 analyzed frames are pooled; the
   system only trusts the emotion that's actually the *majority*, weighted by
   DeepFace's own confidence score. A single stray "angry" frame in a run of
   "neutral" frames gets outvoted.
3. **Stability + debounce timers**: a majority emotion has to hold for 4
   seconds before it's acted on, and a track won't be swapped for at least 20
   seconds after starting. This is what keeps the whole thing feeling like
   ambient therapy instead of a flickering slideshow.

### Tuning knobs (top of `emotion_music_system.py`)
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
  telling **fear vs. surprise** and **sad vs. neutral** apart — this is a
  known limitation of the underlying dataset, not your integration. Since
  we now act on all 7 raw labels directly (no folding into broader
  categories), expect occasional confusion specifically between those pairs
  — worth naming as a known limitation in your evaluation section.
- If you have time budget, DeepFace also supports swapping the model
  (`DeepFace.build_model("Emotion")` uses a Facial Expression CNN by
  default) — an ensemble of two backends and averaging their confidence is a
  reasonable stretch goal for your report's "future work" section.

## 5. Connecting to Firebase (for your teammate's dashboard)

Every time the stabilized emotion changes, `push_to_firebase()` is called.
Right now it just prints. Replace its body with your Firebase write, e.g.
using `pyrebase4`:

```python
import pyrebase
firebase = pyrebase.initialize_app(your_config_dict)
db = firebase.database()

def push_to_firebase(emotion, confidence, env_context=None):
    db.child("mood_history").push({
        "emotion": emotion,
        "confidence": confidence,
        "timestamp": datetime.utcnow().isoformat(),
        **(env_context or {}),
    })
```

## 6. Switching to Spotify instead of local files (optional, later)

If you decide streaming is worth the added complexity (OAuth setup, active
internet, a Spotify Premium account for playback control via
`spotipy` + the Web Playback SDK), the swap only touches `MusicPlayer`:
keep `EmotionSmoother` and the detection loop exactly as-is, and replace
`MusicPlayer.play()` with a call to `sp.start_playback(uris=[track_uri])`
using per-emotion playlist IDs instead of folders. Local files are the safer
choice for your live demo/prototype since they need zero network dependency.
