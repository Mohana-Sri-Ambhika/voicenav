#!/bin/bash

echo "Starting VoiceNav AI..."

# Create necessary directories
mkdir -p backend/uploads backend/audio_outputs data exports

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r backend/requirements.txt

# Download spaCy model if needed
python -c "import spacy; spacy.load('en_core_web_md')" 2>/dev/null || python -m spacy download en_core_web_md

# Start backend server
echo "Starting backend server..."
cd backend
python app.py &
BACKEND_PID=$!

# Wait a moment
sleep 3

# Open browser
if [[ "$OSTYPE" == "darwin"* ]]; then
    open http://localhost:5000
else
    xdg-open http://localhost:5000
fi

echo "VoiceNav AI is running! Press Ctrl+C to stop."
wait $BACKEND_PID