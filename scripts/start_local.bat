@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0\.."
title insta_auto 로컬 실행기

echo [1/5] 필수 프로그램 확인...
where python >nul 2>nul || (echo [오류] Python 3.11+ 이 필요합니다. https://www.python.org & pause & exit /b 1)
where node   >nul 2>nul || (echo [오류] Node.js 20+ 이 필요합니다. https://nodejs.org & pause & exit /b 1)
where ffmpeg >nul 2>nul || echo [경고] FFmpeg 가 없습니다. 영상 생성이 비활성화됩니다. (winget install Gyan.FFmpeg)

if not exist .env (
  copy .env.example .env >nul
  echo [안내] .env 파일을 만들었습니다. API 키를 입력한 뒤 다시 실행하세요.
  notepad .env
  pause & exit /b 0
)

echo [2/5] Agent 환경 준비...
if not exist apps\agent\.venv (
  python -m venv apps\agent\.venv || (echo [오류] venv 생성 실패 & pause & exit /b 1)
  apps\agent\.venv\Scripts\python -m pip install -q -r apps\agent\requirements.txt || (echo [오류] 패키지 설치 실패 & pause & exit /b 1)
  apps\agent\.venv\Scripts\python -m playwright install chromium >nul 2>nul
)

echo [3/5] Web 환경 준비...
if not exist apps\web\.env.local (
  > apps\web\.env.local echo NEXT_PUBLIC_APP_MODE=local
  >> apps\web\.env.local echo NEXT_PUBLIC_AGENT_URL=http://127.0.0.1:8787
)
if not exist apps\web\node_modules ( pushd apps\web & call npm install --no-audit --no-fund & popd )
if not exist apps\web\.next ( pushd apps\web & call npm run build & popd )

echo [4/5] Agent / Web 기동...
start "insta_auto Agent" cmd /k "apps\agent\.venv\Scripts\python -m uvicorn apps.agent.main:app --host 127.0.0.1 --port 8787"
start "insta_auto Web"   cmd /k "cd apps\web && npm run start"

echo [5/5] 브라우저 열기 (약 6초 후)...
timeout /t 6 /nobreak >nul
start http://localhost:3000
echo.
echo 종료하려면 열린 "insta_auto Agent" / "insta_auto Web" 창을 닫으세요.
endlocal
