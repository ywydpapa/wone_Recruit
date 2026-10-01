# 망분리 배포 전 인터넷 연결 환경에서 1회 실행하여 모델을 미리 받아 둠
# erp와 같은 서버인 경우 TTS_DIR을 erp 모델 경로로 지정하면 별도 다운로드가 필요 없음
import os

from huggingface_hub import snapshot_download

snapshot_download(
    "supertone-oss-archive/supertonic-3",
    revision="aafc6e32416a594460b32413efc49d7fe4ce6d46",
    local_dir=os.getenv("TTS_DIR", "models/supertonic"),
)
print("ok")
