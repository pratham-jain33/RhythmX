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

- Use the `backend` folder as the app root.
- Set the start command to `gunicorn app:app`.
- Configure a persistent build cache because downloading Demucs/Basic Pitch models can take time on each deploy.
- Provision enough disk/time budget. Render's free tier allows 500 MB storage, so the app auto-cleans results after five minutes to stay within limits.
- Install LilyPond during the build step to keep PDF rendering available (e.g., via an `apt` command in a `render-build.sh`).

## Troubleshooting

- **Demucs errors**: Ensure the `piano` two-stem model is available. If not, switch to `--two-stems vocals` or another supported target and adjust the pipeline in `processing.py`.
- **Basic Pitch missing TensorFlow**: The PyPI package pulls TensorFlow automatically; if the install fails on Render, preinstall a CPU wheel.
- **music21 cannot find LilyPond**: Update the LilyPond path as shown above. Without LilyPond you can still return MusicXML (`score.write('musicxml', fp='sheet.musicxml')`).
- **Slow processing**: Demucs and Basic Pitch are CPU-intensive. Consider background job queues for production workloads.


## Tests
No test suite is included in this repository.


## API reference
- `GET /` – Serves the frontend HTML.
- `POST /api/process` – Body: `{ "url": "<YouTube URL>" }`. Returns JSON with `token`, `midiUrl`, `sheetUrl`, `expiresIn`.
- `GET /api/download/<token>/<filename>` – Download the generated `piano.mid` or `sheet.pdf`. Returns 404 if token not found or expired.


## Code example
```javascript
const response = await fetch("/api/process", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({url: "https://www.youtube.com/watch?v=example"}),
});
const data = await response.json();
```


## Screenshots


## Code style
The code follows standard Python PEP 8 conventions with type hints. No specific linting or formatting tools are configured in the repository.


## Build status
No CI workflow is defined. To verify the build, run the installation steps and start the server as shown in the Usage section.


## Usage
```powershell
# Start the server
python app.py
```
Then open `http://127.0.0.1:5000` in a browser, paste a YouTube link, and wait for the results. The UI will display links to the generated MIDI and PDF files.


## Installation
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
(Prerequisites: FFmpeg, LilyPond, Python 3.10+, system packages for Demucs/Basic Pitch.)


## Features
- Accept a YouTube URL via a web UI or API.
- Download the video’s audio and convert it to WAV.
- Separate the piano stem from the rest of the mix using Demucs.
- Transcribe the isolated piano audio to MIDI with Basic Pitch.
- Render printable PDF sheet music via music21/LilyPond.
- Provide temporary download links that expire after five minutes.
- Simple Flask API (`/api/process`, `/api/download/<token>/<file>`).


## Tech stack
- Python 3.10+
- Flask (backend API and static serving)
- yt-dlp (download YouTube audio)
- Demucs (instrument separation)
- Basic Pitch (audio‑to‑MIDI transcription)
- music21 with LilyPond (sheet music rendering)
- FFmpeg (audio conversion)
- Vanilla JavaScript frontend


## Motivation
Full-stack prototype that turns a YouTube performance into isolated piano audio, MIDI, and printable sheet music.

---

*Created with [repo-doctor](https://prathamjain.com/projects/repo-doctor)*
