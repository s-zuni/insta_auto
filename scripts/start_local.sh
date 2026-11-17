#!/usr/bin/env bash
# macOS/Linux 고객용 원클릭 실행기. 사용: chmod +x scripts/start_local.sh && ./scripts/start_local.sh
set -euo pipefail
cd "$(dirname "$0")/.."

command -v python3 >/dev/null || { echo "[오류] Python 3.11+ 필요"; exit 1; }
command -v node    >/dev/null || { echo "[오류] Node.js 20+ 필요"; exit 1; }
command -v ffmpeg  >/dev/null || echo "[경고] FFmpeg 없음 → 영상 생성 비활성화 (brew install ffmpeg)"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "[안내] .env 를 만들었습니다. API 키를 입력한 뒤 다시 실행하세요."
  exit 0
fi

if [ ! -d apps/agent/.venv ]; then
  python3 -m venv apps/agent/.venv
  apps/agent/.venv/bin/python -m pip install -q -r apps/agent/requirements.txt
  apps/agent/.venv/bin/python -m playwright install chromium || true
fi

if [ ! -f apps/web/.env.local ]; then
  printf 'NEXT_PUBLIC_APP_MODE=local\nNEXT_PUBLIC_AGENT_URL=http://127.0.0.1:8787\n' > apps/web/.env.local
fi
[ -d apps/web/node_modules ] || (cd apps/web && npm install --no-audit --no-fund)
[ -d apps/web/.next ] || (cd apps/web && npm run build)

apps/agent/.venv/bin/python -m uvicorn apps.agent.main:app --host 127.0.0.1 --port 8787 &
AGENT_PID=$!
(cd apps/web && npm run start) &
WEB_PID=$!
trap 'kill $AGENT_PID $WEB_PID 2>/dev/null || true' EXIT INT TERM

sleep 6
if command -v open >/dev/null; then open http://localhost:3000; elif command -v xdg-open >/dev/null; then xdg-open http://localhost:3000; fi
echo "실행 중입니다. 종료: Ctrl+C"
wait
