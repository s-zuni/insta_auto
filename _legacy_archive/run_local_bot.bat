@echo off
chcp 65001 > nul
title MBTI x 사주 릴스 텔레그램 봇 (로컬 실행기)
cd /d "%~dp0"
echo ================================================================
echo  🚀 MBTI x 사주 인스타/유튜브 자동화 텔레그램 봇 로컬 가동 중
echo  - 텔레그램에서 /generate 또는 /topic 명령어를 전송하세요.
echo  - 창을 닫으면 봇이 종료됩니다. (백그라운드 유지 권장)
echo ================================================================
echo.
.venv\Scripts\python.exe telegram_bot.py
pause

