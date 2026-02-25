# backend/tts_engine.py
from gtts import gTTS
import os
import uuid
import re

class TTSEngine:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        print("🔊 TTS ready")
    
    def text_to_speech(self, text, name):
        try:
            clean = re.sub(r'[*#`]', '', text)
            clean = re.sub(r'\s+', ' ', clean).strip()
            
            if not clean:
                clean = "No text"
            
            if len(clean) > 5000:
                clean = clean[:5000] + "..."
            
            filename = f"{name}_{uuid.uuid4()}.mp3"
            filepath = os.path.join(self.output_dir, filename)
            
            tts = gTTS(text=clean, lang='en')
            tts.save(filepath)
            
            return filename
        except Exception as e:
            print(f"TTS error: {e}")
            return None