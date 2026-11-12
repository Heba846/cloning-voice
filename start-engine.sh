#!/usr/bin/env bash
# Sawtak engine for macOS/Linux:  ./start-engine.sh   (add --no-tunnel for local-only)
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "First run: installing (10-20 minutes, one time only)..."
  python3 -m venv .venv
  . .venv/bin/activate
  python -m pip install --upgrade pip
  if command -v nvidia-smi >/dev/null; then
    pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cu124
  elif [ "$(uname)" = "Darwin" ]; then
    pip install torch torchaudio torchvision
  else
    pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cpu
  fi
  pip install -r engine/requirements.txt
else
  . .venv/bin/activate
fi
exec python -m engine.run "$@"
