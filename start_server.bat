@echo off
REM ---------------------------------------
REM Flask + ngrok 자동 실행 스크립트
REM ---------------------------------------

REM 1. 가상환경 활성화
echo [1] Activating virtual environment...
call venv\Scripts\activate

REM 2. Flask 서버 실행 (새 창에서)
echo [2] Starting Flask server...
start cmd /k "python run.py"

REM 3. 잠시 대기 후 ngrok 실행
timeout /t 3 >nul

REM 4. ngrok 실행 (5000번 포트)
echo [3] Starting ngrok tunnel...
start cmd /k "C:\Users\user\Downloads\ngrok-v3-stable-windows-amd64\ngrok.exe http 5000"

echo ---------------------------------------
echo [INFO] Flask server + ngrok tunnel started
echo [INFO] Use the ngrok URL to connect your frontend
echo ---------------------------------------
pause
