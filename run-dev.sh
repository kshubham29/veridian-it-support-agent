#!/usr/bin/env bash
# One-command local run: starts the FastAPI backend and the Vite frontend.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "→ Backend: installing dependencies"
cd "$ROOT/backend"
python -m pip install -q -r requirements.txt
echo "→ Backend: starting on http://localhost:8000"
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT

echo "→ Frontend: installing dependencies"
cd "$ROOT/frontend"
npm install
echo "→ Frontend: starting on http://localhost:5173"
npm run dev
