const form = document.getElementById("url-form");
const urlInput = document.getElementById("url-input");
const submitBtn = document.getElementById("submit-btn");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");
const sheetLink = document.getElementById("sheet-link");
const midiLink = document.getElementById("midi-link");
const expiryEl = document.getElementById("expiry");
const progressSection = document.getElementById("progress");
const progressBar = document.getElementById("progress-bar");
const progressLabel = document.getElementById("progress-label");
const previewSection = document.getElementById("preview");
const pdfFrame = document.getElementById("pdf-preview");
const playMidiBtn = document.getElementById("play-midi");
const stopMidiBtn = document.getElementById("stop-midi");
const midiStatus = document.getElementById("midi-status");

const statusClasses = ["info", "success", "error"];
const progressStages = [
    "Downloading audio…",
    "Separating piano stem…",
    "Transcribing to MIDI…",
    "Engraving sheet music…",
];

let progressInterval = null;
let progressStageTimer = null;
let progressPercent = 0;

let midiLoadedUrl = null;
let midiReady = false;
let midiLoading = false;
let midiPlaying = false;
let midiDuration = 0;
let midiStopEvent = null;
let midiParts = [];
let midiSynths = [];

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const rawUrl = urlInput.value.trim();
    if (!rawUrl) {
        setStatus("Please paste a YouTube URL.", "error");
        return;
    }

    setLoading(true);
    setStatus("Processing… this can take a couple of minutes.", "info");
    hideResults();
    resetPreview();
    startProgress();

    try {
        const response = await fetch("/api/process", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({url: rawUrl}),
        });

        const payload = await response.json();
        if (!response.ok) {
            throw new Error(payload.error || "Processing failed");
        }

        sheetLink.href = payload.sheetUrl;
        midiLink.href = payload.midiUrl;
        sheetLink.setAttribute("download", `sheet-${payload.token}.pdf`);
        midiLink.setAttribute("download", `piano-${payload.token}.mid`);
        expiryEl.textContent = `Links expire in ${Math.round(payload.expiresIn / 60)} minutes.`;

        finishProgress(true);
        resultsEl.classList.remove("hidden");
        previewSection.classList.remove("hidden");
        pdfFrame.src = `${payload.sheetUrl}#view=FitH`;
        midiStatus.textContent = "Loading MIDI preview…";
        prepareMidiPreview(payload.midiUrl);

        setStatus("Success! Your files are ready.", "success");
    } catch (error) {
        finishProgress(false);
        setStatus(error.message, "error");
    } finally {
        setLoading(false);
    }
});

playMidiBtn.addEventListener("click", () => {
    startMidiPlayback();
});

stopMidiBtn.addEventListener("click", () => {
    stopMidiPlayback();
});

function startProgress() {
    progressPercent = 5;
    progressBar.style.width = `${progressPercent}%`;
    progressLabel.textContent = progressStages[0];
    progressSection.classList.remove("hidden");

    clearInterval(progressInterval);
    clearInterval(progressStageTimer);

    progressInterval = setInterval(() => {
        const increment = Math.random() * 6 + 2;
        progressPercent = Math.min(progressPercent + increment, 94);
        progressBar.style.width = `${progressPercent}%`;
    }, 750);

    let stageIndex = 0;
    progressStageTimer = setInterval(() => {
        stageIndex = Math.min(stageIndex + 1, progressStages.length - 1);
        progressLabel.textContent = progressStages[stageIndex];
        if (stageIndex === progressStages.length - 1) {
            clearInterval(progressStageTimer);
        }
    }, 4500);
}

function finishProgress(success) {
    clearInterval(progressInterval);
    clearInterval(progressStageTimer);
    progressInterval = null;
    progressStageTimer = null;

    if (success) {
        progressBar.style.width = "100%";
        progressLabel.textContent = "Complete!";
        setTimeout(() => {
            progressSection.classList.add("hidden");
            progressBar.style.width = "0%";
        }, 900);
    } else {
        progressBar.style.width = "0%";
        progressSection.classList.add("hidden");
    }
}

function setStatus(message, level) {
    statusEl.textContent = message;
    statusEl.classList.remove("hidden");
    statusClasses.forEach((cls) => statusEl.classList.remove(cls));
    if (level && statusClasses.includes(level)) {
        statusEl.classList.add(level);
    }
}

function hideResults() {
    resultsEl.classList.add("hidden");
    previewSection.classList.add("hidden");
}

function setLoading(isLoading) {
    submitBtn.disabled = isLoading;
    urlInput.disabled = isLoading;
    submitBtn.textContent = isLoading ? "Processing…" : "Process Video";
}

function resetPreview() {
    pdfFrame.src = "about:blank";
    midiStatus.textContent = "Load a MIDI file to preview.";
    playMidiBtn.disabled = true;
    stopMidiBtn.disabled = true;
    midiLoadedUrl = null;
    midiReady = false;
    midiLoading = false;
    midiPlaying = false;
    midiDuration = 0;
    if (midiStopEvent && window.Tone && Tone.Transport) {
        Tone.Transport.clear(midiStopEvent);
    }
    midiStopEvent = null;
    disposeMidiResources();
    if (window.Tone && Tone.Transport) {
        Tone.Transport.stop();
        Tone.Transport.cancel();
        Tone.Transport.position = 0;
    }
}

async function prepareMidiPreview(url) {
    if (!window.Tone || !window.Midi) {
        midiStatus.textContent = "Preview libraries failed to load.";
        return;
    }

    midiLoading = true;
    playMidiBtn.disabled = true;
    stopMidiBtn.disabled = true;
    disposeMidiResources();
    Tone.Transport.stop();
    Tone.Transport.cancel();
    Tone.Transport.position = 0;

    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error("Unable to load MIDI preview.");
        }

        const buffer = await response.arrayBuffer();
        const midi = new Midi(buffer);

        const tracksWithNotes = midi.tracks.filter((track) => track.notes.length);
        if (!tracksWithNotes.length) {
            midiStatus.textContent = "No notes detected in MIDI.";
            midiReady = false;
            return;
        }

        if (midi.header.tempos.length) {
            Tone.Transport.bpm.value = midi.header.tempos[0].bpm;
        } else {
            Tone.Transport.bpm.value = 120;
        }

        if (midi.header.timeSignatures.length) {
            const [numerator, denominator] = midi.header.timeSignatures[0].timeSignature;
            Tone.Transport.timeSignature = [numerator, denominator];
        } else {
            Tone.Transport.timeSignature = [4, 4];
        }

        midiDuration = midi.duration || tracksWithNotes.reduce((max, track) => Math.max(max, track.duration), 0);

        tracksWithNotes.forEach((track) => {
            const synth = new Tone.PolySynth(Tone.Synth).toDestination();
            midiSynths.push(synth);

            const events = track.notes.map((note) => ({
                time: note.time,
                note: note.name,
                duration: note.duration,
                velocity: note.velocity,
            }));

            const part = new Tone.Part((time, value) => {
                synth.triggerAttackRelease(value.note, value.duration, time, value.velocity);
            }, events).start(0);

            part.loop = false;
            midiParts.push(part);
        });

        midiLoadedUrl = url;
        midiReady = true;
        midiStatus.textContent = "Ready to play.";
        playMidiBtn.disabled = false;
    } catch (error) {
        midiReady = false;
        midiStatus.textContent = error.message || "Unable to load MIDI preview.";
    } finally {
        midiLoading = false;
    }
}

async function startMidiPlayback() {
    if (midiLoading) {
        return;
    }

    if (!midiReady || midiLoadedUrl !== midiLink.href) {
        await prepareMidiPreview(midiLink.href);
    }

    if (!midiReady) {
        return;
    }

    try {
        await Tone.start();
    } catch (error) {
        midiStatus.textContent = "Audio context failed to start.";
        return;
    }

    Tone.Transport.stop();
    Tone.Transport.position = 0;
    midiParts.forEach((part) => part.start(0));

    if (midiStopEvent !== null) {
        Tone.Transport.clear(midiStopEvent);
    }

    midiStopEvent = Tone.Transport.scheduleOnce(() => {
        stopMidiPlayback(false);
    }, midiDuration + 0.2);

    midiPlaying = true;
    playMidiBtn.disabled = true;
    stopMidiBtn.disabled = false;
    midiStatus.textContent = "Playing…";
    Tone.Transport.start();
}

function stopMidiPlayback(userInitiated = true) {
    if (!window.Tone || !Tone.Transport) {
        return;
    }

    Tone.Transport.stop();
    Tone.Transport.position = 0;

    if (midiStopEvent !== null) {
        Tone.Transport.clear(midiStopEvent);
        midiStopEvent = null;
    }

    midiPlaying = false;
    playMidiBtn.disabled = !midiReady;
    stopMidiBtn.disabled = true;
    midiStatus.textContent = userInitiated ? "Stopped." : "Playback finished.";
}

function disposeMidiResources() {
    midiParts.forEach((part) => part.dispose());
    midiSynths.forEach((synth) => synth.dispose());
    midiParts = [];
    midiSynths = [];
}
