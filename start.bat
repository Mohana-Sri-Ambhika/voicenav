@echo off
echo Starting VoiceNav AI...

echo Starting Backend Server...
start cmd /k "cd backend && conda activate voicenav && python app.py"

timeout /t 3

echo Starting Frontend Server...
start cmd /k "cd frontend && python -m http.server 8000"

timeout /t 2

echo Opening Browser...
start http://localhost:8000

echo.
echo VoiceNav AI is running!
echo Backend: http://localhost:5000
echo Frontend: http://localhost:8000
echo.
echo Press any key to stop all servers...
pause >nul
taskkill /f /im python.exe