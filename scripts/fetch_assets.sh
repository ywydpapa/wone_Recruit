#!/bin/bash
# 새 서버 배포 전 인터넷 연결 환경에서 1회 실행함. 브라우저 자산과 STT/TTS 모델을 일괄 다운로드함
set -eu
cd "$(dirname "$0")/.."
PY=.venv/bin/python

bash scripts/fetch_vad.sh
bash scripts/fetch_headmouse.sh
$PY scripts/fetch_tts.py
# huggingface 캐시에 저장해 두면 이후 오프라인에서도 로드 가능함
$PY -c "import os; from faster_whisper import download_model; print(download_model(os.getenv('STT_MODEL', 'small')))"
echo "모든 자산 준비 완료"
