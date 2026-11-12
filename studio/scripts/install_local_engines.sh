#!/usr/bin/env bash
# Optional: free/local engines. Run on a machine with ffmpeg + (ideally) an NVIDIA GPU.
set -e
echo "== Cairo-TTS (Egyptian Arabic, zero-shot cloning, CPU or GPU) =="
pip install cairo-tts
echo "== Wav2Lip (lip-sync, works on CPU) =="
sudo mkdir -p /opt && cd /opt
[ -d Wav2Lip ] || git clone https://github.com/Rudrabha/Wav2Lip.git
cd Wav2Lip && pip install -r requirements.txt
mkdir -p checkpoints
echo ">> Download wav2lip_gan.pth into /opt/Wav2Lip/checkpoints/ (link in the Wav2Lip README),"
echo "   and s3fd.pth into /opt/Wav2Lip/face_detection/detection/sfd/"
echo "== LatentSync (best quality, needs ~8GB VRAM) =="
cd /opt && ([ -d LatentSync ] || git clone https://github.com/bytedance/LatentSync.git)
echo ">> Follow /opt/LatentSync/README.md (setup_env.sh downloads the checkpoints)"
echo
echo "Then in .env:  TTS_ENGINE=cairo  LIPSYNC_ENGINE=wav2lip  WAV2LIP_DIR=/opt/Wav2Lip  WAV2LIP_CHECKPOINT=/opt/Wav2Lip/checkpoints/wav2lip_gan.pth"
