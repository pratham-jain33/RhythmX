import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from basic_pitch.inference import predict_and_save
from basic_pitch import ICASSP_2022_MODEL_PATH
import music21
from music21 import instrument
import yt_dlp

LOGGER = logging.getLogger(__name__)


class ProcessingError(Exception):
    """Raised when the audio processing pipeline cannot complete."""


def download_audio(url: str, work_dir: Path) -> Path:
    """Download and convert the YouTube audio track to WAV using yt-dlp."""
    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / "source"
    output_template = f"{target}.%(ext)s"
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
        except yt_dlp.DownloadError as exc:
            raise ProcessingError("Failed to download audio from YouTube") from exc

    wav_path = target.with_suffix(".wav")
    if not wav_path.exists():
        raise ProcessingError("yt-dlp did not produce the expected WAV file")

    LOGGER.info("Downloaded audio to %s", wav_path)
    return wav_path


def isolate_piano(audio_path: Path, work_dir: Path, model: str = "htdemucs") -> Path:
    """Run Demucs two-stem vocals separation and treat the no-vocals stem as the piano track."""
    demucs_root = work_dir / "demucs"
    demucs_root.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "demucs",
        "--two-stems",
        "vocals",
        "--mp3",
        "-n",
        model,
        "--out",
        str(demucs_root),
        str(audio_path),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        LOGGER.error("Demucs stderr: %s", exc.stderr.decode("utf-8", "ignore") if exc.stderr else "")
        raise ProcessingError("Demucs failed to isolate instrumental stem. Check Demucs installation.") from exc

    track_dir = demucs_root / model / audio_path.stem
    if not track_dir.exists():
        raise ProcessingError("Demucs output folder missing. Verify the selected model name.")

    mp3_path = track_dir / "no_vocals.mp3"
    if not mp3_path.exists():
        raise ProcessingError("Demucs did not create the no_vocals.mp3 stem as expected.")

    piano_path = work_dir / "piano.wav"
    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(mp3_path),
        str(piano_path),
    ]

    try:
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        LOGGER.error("ffmpeg stderr: %s", exc.stderr.decode("utf-8", "ignore") if exc.stderr else "")
        raise ProcessingError("Failed to convert Demucs output to WAV. Ensure FFmpeg is installed.") from exc

    LOGGER.info("Isolated instrumental track at %s", piano_path)
    return piano_path


def transcribe_to_midi(audio_path: Path, work_dir: Path) -> Path:
    """Use Basic Pitch to convert audio to MIDI."""
    midi_root = work_dir / "basic_pitch"
    midi_root.mkdir(parents=True, exist_ok=True)

    predict_and_save(
        audio_path_list=[str(audio_path)],
        output_directory=str(midi_root),
        save_midi=True,
        sonify_midi=False,
        save_model_outputs=False,
        save_notes=False,
        model_or_model_path=ICASSP_2022_MODEL_PATH,
        onset_threshold=0.35,
        frame_threshold=0.35,
        minimum_note_length=60.0,
    )

    base_name = audio_path.stem
    expected = midi_root / f"{base_name}.mid"
    midi_files = list(midi_root.glob("*.mid"))

    target = expected if expected.exists() else (midi_files[-1] if midi_files else None)
    if target is None:
        raise ProcessingError("Basic Pitch did not create a MIDI file")

    midi_path = work_dir / "piano.mid"
    shutil.copy(target, midi_path)
    LOGGER.info("Generated MIDI at %s", midi_path)
    return midi_path


def midi_to_sheet(midi_path: Path, work_dir: Path) -> Path:
    """Render sheet music as PDF using music21/LilyPond."""
    score = music21.converter.parse(str(midi_path))
    # Encourage piano staff layout to avoid empty LilyPond output.
    score.insert(0, instrument.Piano())
    condensed = score.chordify()
    condensed.makeNotation(inPlace=True)

    lily_dir = work_dir / "lilypond"
    lily_dir.mkdir(parents=True, exist_ok=True)
    ly_path = lily_dir / "piano.ly"

    try:
        condensed.write("lilypond", fp=str(ly_path))
    except Exception as exc:  # noqa: BLE001
        raise ProcessingError(
            "Failed to write LilyPond source file. Ensure music21 is configured correctly."
        ) from exc

    if not ly_path.exists():
        raise ProcessingError("Music21 did not produce a LilyPond source file.")

    lilypond_cmd = _resolve_lilypond_command()
    output_base = lily_dir / "piano_render"

    try:
        subprocess.run(
            lilypond_cmd
            + [
                "--loglevel=ERROR",
                "--pdf",
                "-o",
                str(output_base),
                str(ly_path),
            ],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        LOGGER.error("LilyPond stderr: %s", exc.stderr.decode("utf-8", "ignore") if exc.stderr else "")
        raise ProcessingError(
            "LilyPond failed to engrave the sheet music. Verify LilyPond installation and settings."
        ) from exc

    generated_pdf = output_base.with_suffix(".pdf")
    if not generated_pdf.exists():
        raise ProcessingError("LilyPond did not generate a PDF output.")

    sheet_path = work_dir / "sheet.pdf"
    shutil.copy(generated_pdf, sheet_path)

    if sheet_path.stat().st_size < 2048:
        raise ProcessingError("Sheet music PDF appears empty. Check LilyPond installation and input MIDI quality.")

    LOGGER.info("Rendered sheet music at %s", sheet_path)
    return sheet_path


def _resolve_lilypond_command() -> list[str]:
    """Determine how to invoke LilyPond based on environment configuration."""
    env_path = os.getenv("LILYPOND_PATH")
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return [str(candidate)]

    return ["lilypond"]


def process_youtube_url(url: str, output_dir: Path) -> dict:
    """Run the full pipeline and return generated artifacts."""
    audio_path = download_audio(url, output_dir)
    piano_path = isolate_piano(audio_path, output_dir)
    midi_path = transcribe_to_midi(piano_path, output_dir)
    sheet_path = midi_to_sheet(midi_path, output_dir)

    return {
        "audio": audio_path,
        "piano": piano_path,
        "midi": midi_path,
        "sheet": sheet_path,
    }
