#!/bin/bash
# 폐쇄망 대응을 위해 헤드마우스용 mediapipe tasks-vision과 얼굴 모델을 로컬에 저장함
set -eu
DEST=static/vendor/mediapipe
MODEL_URL=https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task
TMP=$(mktemp -d)
mkdir -p "$DEST/wasm"

npm pack @mediapipe/tasks-vision@1.0.1 --pack-destination "$TMP"
tar -xzf "$TMP"/mediapipe-tasks-vision-1.0.1.tgz -C "$TMP"

cp "$TMP/package/vision_bundle.mjs" "$DEST/"
cp "$TMP"/package/wasm/* "$DEST/wasm/"
curl -fsSL "$MODEL_URL" -o "$DEST/face_landmarker.task"

rm -rf "$TMP"
echo "헤드마우스 자산을 $DEST 에 복사했습니다"
