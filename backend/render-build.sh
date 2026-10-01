#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ffmpeg lilypond
rm -rf /var/lib/apt/lists/*

python -m pip install --upgrade pip
pip install -r requirements.txt
