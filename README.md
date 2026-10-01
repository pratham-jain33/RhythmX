# RhythmX

Full-stack prototype that turns a YouTube performance into isolated piano audio, MIDI, and printable sheet music.

## Prerequisites

- Python 3.10+
- FFmpeg in your PATH (required by `yt-dlp`)
- LilyPond installed and configured for `music21`
- System packages to run Demucs/Basic Pitch (`torch`, `tensorflow` can be heavy; CPU-only wheels are sufficient for initial tests)

On Windows you can download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html) and add the `bin` folder to your PATH. LilyPond installers are available at [lilypond.org](https://lilypond.org/download.html). After installing LilyPond run the snippet below once to point `music21` at the executable:

```python
from music21 import environment
us = environment.UserSettings()
us['lilypondPath'] = r'C:\\Program Files\\LilyPond\\usr\\bin\\lilypond.exe'
```

## Local Development

1. **Install dependencies**

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. **Run the server**

   ```powershell
   python app.py
   ```

   Flask serves both the API and the static frontend at `http://127.0.0.1:5000`.

3. **Use the web UI**

   Open the URL above, paste a YouTube link, and wait for processing to finish. Processing pulls audio, isolates the piano stem with Demucs, converts the stem to MIDI via Basic Pitch, and renders sheet music with music21. Links remain active for five minutes before the backend deletes the temporary files.

## Deployment Notes (Render)

This repository includes ready-to-use Render config:

- `/home/runner/work/RhythmX/RhythmX/render.yaml`
- `/home/runner/work/RhythmX/RhythmX/backend/render-build.sh`

### What the config does

- Deploys only `/home/runner/work/RhythmX/RhythmX/backend` as the web service root.
- Uses `gunicorn app:app` as the start command.
- Installs Python dependencies from `requirements.txt`.
- Installs system packages required by the pipeline: **FFmpeg** and **LilyPond**.
- Sets cache environment variables (`PIP_CACHE_DIR`, `XDG_CACHE_HOME`, `TORCH_HOME`, `HF_HOME`, `BASIC_PITCH_CACHE_DIR`) so model and package downloads can be reused through Render's build cache.

### Render setup checklist

1. In Render, create a new **Blueprint** service from this repository (or apply `render.yaml` to an existing service).
2. Confirm the service runtime is Python with `rootDir: backend`.
3. Keep the default build command from the blueprint (`./render-build.sh`) and start command (`gunicorn app:app`).
4. Use a plan with enough CPU and disk for Demucs + TensorFlow + model downloads (free tier is usually too constrained for reliable processing).
5. Keep build cache enabled so subsequent deploys reuse model/package artifacts.

### Live verification

1. Open the deployed URL.
2. Check health endpoint: `GET /health` returns `{"status":"ok"}`.
3. Submit a valid YouTube URL in the web UI.
4. Confirm successful output links for:
   - `piano.mid`
   - `sheet.pdf`
5. Download both files and confirm they open correctly.

## Troubleshooting

- **Demucs errors**: Ensure the `piano` two-stem model is available. If not, switch to `--two-stems vocals` or another supported target and adjust the pipeline in `processing.py`.
- **Basic Pitch missing TensorFlow**: The PyPI package pulls TensorFlow automatically; if the install fails on Render, preinstall a CPU wheel.
- **music21 cannot find LilyPond**: Update the LilyPond path as shown above. Without LilyPond you can still return MusicXML (`score.write('musicxml', fp='sheet.musicxml')`).
- **Slow processing**: Demucs and Basic Pitch are CPU-intensive. Consider background job queues for production workloads.
