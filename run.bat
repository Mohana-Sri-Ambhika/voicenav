@echo off
echo Starting VoiceNav AI...

mkdir backend\uploads 2>nul
mkdir backend\audio_outputs 2>nul
mkdir data 2>nul
mkdir exports 2>nul

if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Installing dependencies...
pip install --upgrade pip
pip install -r backend\requirements.txt

python -c "import spacy; spacy.load('en_core_web_md')" 2>nul
if errorlevel 1 (
    python -m spacy download en_core_web_md
)

echo Starting backend server...
cd backend
start /B python app.py

timeout /t 3

start http://localhost:5000

echo VoiceNav AI is running!
echo Press any key to stop...
pause >nul

taskkill /F /IM python.exe