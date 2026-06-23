#!/usr/bin/env bash
# Stage the Wave-1 recognition artefacts onto the prod host's data volume.
#
# The recognizer's model + index are *data*, mounted from the host (../apps/api/data → /app/data)
# so they ship without baking a 100MB+ blob into the image. This copies the three artefacts to the
# host data dir under the names the API expects, fixes the perms gotcha (the container runs as a
# non-root uid that must be able to read them), and then tells you to redeploy the *code* — the
# embedding provider is new code, so the image still needs a rebuild (deploy/deploy.sh).
#
# Usage:  scripts/deploy_recognition.sh root@HOST [/remote/data/dir]
# Run from apps/api after a successful full build (data/image_index.full.{json,f16.npy}) and export
# (data/recognition_model.onnx).
set -euo pipefail

HOST="${1:?usage: deploy_recognition.sh user@host [remote_data_dir]}"
REMOTE_DIR="${2:-/root/holofy/apps/api/data}"
SSH_KEY="${HOLOFY_SSH_KEY:-$HOME/.ssh/ovh}"
SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=no"
SCP="scp -i $SSH_KEY -o StrictHostKeyChecking=no"

MODEL="data/recognition_model.onnx"
INDEX="data/image_index.full.json"
VECS="data/image_index.full.f16.npy"

for f in "$MODEL" "$INDEX" "$VECS"; do
  [ -f "$f" ] || { echo "missing artefact: $f — run the export + full build first" >&2; exit 1; }
done

echo "→ staging recognition artefacts to $HOST:$REMOTE_DIR"
# Upload to temp names first, then move into place atomically, so a running API never reads a
# half-written index. The API picks the new files up on its next restart (below).
$SSH "$HOST" "mkdir -p $REMOTE_DIR"
$SCP "$MODEL" "$HOST:$REMOTE_DIR/recognition_model.onnx.new"
$SCP "$INDEX" "$HOST:$REMOTE_DIR/image_index.json.new"
$SCP "$VECS"  "$HOST:$REMOTE_DIR/image_index.f16.npy.new"

# Move into place + perms. 0644 so the container's non-root uid can read; the dir itself must be
# traversable (the perm gotcha that has silently broken index pickups before).
$SSH "$HOST" "set -e; cd $REMOTE_DIR; \
  mv -f recognition_model.onnx.new recognition_model.onnx; \
  mv -f image_index.json.new image_index.json; \
  mv -f image_index.f16.npy.new image_index.f16.npy; \
  chmod 0644 recognition_model.onnx image_index.json image_index.f16.npy; \
  chmod 0755 . ; \
  ls -lh recognition_model.onnx image_index.json image_index.f16.npy"

cat <<'NEXT'

✓ artefacts staged.

The embedding provider is NEW CODE, so finish the deploy by rebuilding the image and restarting:

    cd ../../deploy && ./deploy.sh        # rebuilds the API image with the new code, restarts

After restart, verify the embedding path is live (look for "recognition.recognize embedding" in
logs on the next scan, and that GET /health is 200). A scan that names the right card end-to-end
is the real check.
NEXT
