import logging
import shutil
import threading
import time
import uuid
from pathlib import Path
import os

from flask import Flask, abort, jsonify, request, send_from_directory

from processing import ProcessingError, process_youtube_url

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

EXPIRATION_SECONDS = int(os.getenv("RESULT_EXPIRATION_SECONDS", "300"))

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="/static")

_active_results: dict[str, dict] = {}
_results_lock = threading.Lock()


def _schedule_cleanup(token: str) -> None:
    def _cleanup() -> None:
        with _results_lock:
            entry = _active_results.pop(token, None)
        if entry:
            shutil.rmtree(entry["dir"], ignore_errors=True)
            LOGGER.info("Cleaned up artifacts for token %s", token)

    timer = threading.Timer(EXPIRATION_SECONDS, _cleanup)
    timer.daemon = True
    timer.start()


@app.route("/")
def index() -> str:
    return send_from_directory(str(FRONTEND_DIR), "index.html")


@app.route("/api/process", methods=["POST"])
def process_route():
    payload = request.get_json(silent=True) or {}
    url = (payload.get("url") or "").strip()
    if not url:
        return jsonify({"error": "YouTube URL is required."}), 400

    token = uuid.uuid4().hex
    work_dir = RESULTS_DIR / token
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        outputs = process_youtube_url(url, work_dir)
    except ProcessingError as exc:  # known pipeline error
        shutil.rmtree(work_dir, ignore_errors=True)
        return jsonify({"error": str(exc)}), 400
    except Exception:  # noqa: BLE001
        LOGGER.exception("Unhandled processing failure")
        shutil.rmtree(work_dir, ignore_errors=True)
        return jsonify({"error": "Unexpected server error. Check logs."}), 500

    expires_at = time.time() + EXPIRATION_SECONDS
    with _results_lock:
        _active_results[token] = {"dir": work_dir, "expires": expires_at}

    _schedule_cleanup(token)

    return jsonify(
        {
            "token": token,
            "midiUrl": f"/api/download/{token}/piano.mid",
            "sheetUrl": f"/api/download/{token}/sheet.pdf",
            "expiresIn": EXPIRATION_SECONDS,
        }
    )


def _resolve_secure_path(base_dir: Path, filename: str) -> Path:
    candidate = (base_dir / filename).resolve()
    if not str(candidate).startswith(str(base_dir.resolve())):
        raise ValueError("Invalid path")
    return candidate


@app.route("/api/download/<token>/<path:filename>")
def download_route(token: str, filename: str):
    with _results_lock:
        entry = _active_results.get(token)
    if not entry:
        abort(404)

    if time.time() > entry["expires"]:
        with _results_lock:
            _active_results.pop(token, None)
        shutil.rmtree(entry["dir"], ignore_errors=True)
        abort(410)

    try:
        file_path = _resolve_secure_path(entry["dir"], filename)
    except ValueError:
        abort(400)

    if not file_path.exists():
        abort(404)

    relative = file_path.relative_to(entry["dir"])
    return send_from_directory(str(entry["dir"]), str(relative), as_attachment=False)


@app.route("/health", methods=["GET"])
def health_route():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
