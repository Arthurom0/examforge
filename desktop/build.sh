#!/usr/bin/env bash
# Builds the ExamForge desktop app.
#   macOS:  ./desktop/build.sh        -> desktop/release/ExamForge-<version>-<arch>.dmg
#   Linux:  ./desktop/build.sh linux  -> desktop/release/ExamForge-<version>.AppImage (used for testing)
# The bundled engine is built for the machine's own CPU (Apple Silicon or Intel).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
TARGET=${1:-mac}

echo "==> Python environment"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install -q -r backend/requirements.txt "pyinstaller>=6.10"

echo "==> Frontend build"
(cd frontend && { [ -d node_modules ] || npm install; } && npm run build)

echo "==> Bundling the Python engine (PyInstaller)"
rm -rf backend/build backend/dist
(cd backend && ../.venv/bin/pyinstaller \
  --name examforge-server \
  --onedir --noconfirm --clean --log-level WARN \
  --paths . \
  --collect-submodules app \
  --collect-submodules uvicorn \
  --collect-all pymupdf \
  --collect-data anthropic \
  app/desktop_server.py)

echo "==> Smoke test of the bundled engine"
PORT=8799
TMPD=$(mktemp -d)
EXAMFORGE_DATA_DIR="$TMPD" EXAMFORGE_ENV_FILE="$TMPD/.env" EXAMFORGE_STATIC_DIR="$ROOT/frontend/dist" \
  backend/dist/examforge-server/examforge-server --port $PORT >"$TMPD/engine.log" 2>&1 &
PID=$!
ok=0
for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null; then ok=1; break; fi
  sleep 0.5
done
kill $PID 2>/dev/null || true
if [ $ok != 1 ]; then echo "Engine failed to start:"; cat "$TMPD/engine.log"; exit 1; fi
echo "    engine OK"

echo "==> Packaging the app (electron-builder)"
cd desktop
[ -d node_modules ] || npm install
if [ "$TARGET" = "linux" ]; then
  npx electron-builder --linux AppImage
else
  npx electron-builder --mac dmg
fi
echo
echo "Done. Output:"
ls -1 "$ROOT/desktop/release" | grep -Ei '\.(dmg|AppImage)$' | sed "s|^|  $ROOT/desktop/release/|"
