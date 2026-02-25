# backend/tts_engine.py - ENGLISH VOICES ONLY
from gtts import gTTS
import os
import uuid
import re

class TTSEngine:
    """Text-to-Speech engine with English voice profiles only"""
    
    def __init__(self, output_dir="audio_outputs"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # ===== ENGLISH VOICE PROFILES ONLY =====
        self.voice_profiles = {
            # American English
            'default': {
                'lang': 'en',
                'tld': 'com',
                'slow': False,
                'description': 'American English (Default)',
                'accent': 'American'
            },
            'us': {
                'lang': 'en',
                'tld': 'com',
                'slow': False,
                'description': 'American English',
                'accent': 'American'
            },
            
            # British English
            'uk': {
                'lang': 'en',
                'tld': 'co.uk',
                'slow': False,
                'description': 'British English',
                'accent': 'British'
            },
            'british': {
                'lang': 'en',
                'tld': 'co.uk',
                'slow': False,
                'description': 'British English',
                'accent': 'British'
            },
            
            # Australian English
            'australia': {
                'lang': 'en',
                'tld': 'com.au',
                'slow': False,
                'description': 'Australian English',
                'accent': 'Australian'
            },
            'aussie': {
                'lang': 'en',
                'tld': 'com.au',
                'slow': False,
                'description': 'Australian English',
                'accent': 'Australian'
            },
            
            # Indian English
            'india': {
                'lang': 'en',
                'tld': 'co.in',
                'slow': False,
                'description': 'Indian English',
                'accent': 'Indian'
            },
            
            # South African English
            'south_africa': {
                'lang': 'en',
                'tld': 'co.za',
                'slow': False,
                'description': 'South African English',
                'accent': 'South African'
            },
            
            # Irish English
            'ireland': {
                'lang': 'en',
                'tld': 'ie',
                'slow': False,
                'description': 'Irish English',
                'accent': 'Irish'
            },
            
            # Canadian English
            'canada': {
                'lang': 'en',
                'tld': 'ca',
                'slow': False,
                'description': 'Canadian English',
                'accent': 'Canadian'
            },
            
            # New Zealand English
            'new_zealand': {
                'lang': 'en',
                'tld': 'co.nz',
                'slow': False,
                'description': 'New Zealand English',
                'accent': 'New Zealand'
            },
            
            # Speed variants
            'slow': {
                'lang': 'en',
                'tld': 'com',
                'slow': True,
                'description': 'Slow American English',
                'accent': 'American'
            },
            'very_slow': {
                'lang': 'en',
                'tld': 'com',
                'slow': True,
                'description': 'Very Slow American English',
                'accent': 'American'
            },
            'uk_slow': {
                'lang': 'en',
                'tld': 'co.uk',
                'slow': True,
                'description': 'Slow British English',
                'accent': 'British'
            }
        }
        
        # Current voice profile
        self.current_profile = 'default'
        
        print(f"🔊 TTS Engine initialized with {len(self.voice_profiles)} English voice profiles")
        print("   Available accents: American, British, Australian, Indian, South African, Irish, Canadian, New Zealand")
    
    def text_to_speech(self, text, name_prefix="audio", profile=None):
        """
        Convert text to speech using specified voice profile
        """
        try:
            # Use specified profile or current
            profile_name = profile if profile else self.current_profile
            
            # Get profile settings
            if profile_name in self.voice_profiles:
                profile_settings = self.voice_profiles[profile_name]
            else:
                # Fallback to default
                profile_settings = self.voice_profiles['default']
                profile_name = 'default'
                print(f"⚠️ Profile '{profile}' not found, using default")
            
            # Clean text
            clean = re.sub(r'[*#`]', '', text)
            clean = re.sub(r'\s+', ' ', clean).strip()
            
            if not clean:
                clean = "No text to read"
            
            # Truncate if too long
            if len(clean) > 500:
                clean = clean[:500] + "..."
            
            # Generate filename with profile info
            filename = f"{name_prefix}_{profile_name}_{uuid.uuid4()}.mp3"
            filepath = os.path.join(self.output_dir, filename)
            
            # Generate speech with selected profile
            tts = gTTS(
                text=clean,
                lang=profile_settings['lang'],
                tld=profile_settings['tld'],
                slow=profile_settings['slow']
            )
            tts.save(filepath)
            
            print(f"✅ Audio created: {filename} (voice: {profile_settings['description']})")
            return filename
            
        except Exception as e:
            print(f"❌ TTS error: {e}")
            return None
    
    def set_voice_profile(self, profile_name):
        """Change current voice profile"""
        if profile_name in self.voice_profiles:
            self.current_profile = profile_name
            return {
                'success': True,
                'profile': profile_name,
                'description': self.voice_profiles[profile_name]['description'],
                'accent': self.voice_profiles[profile_name]['accent']
            }
        return {
            'success': False,
            'error': f"Profile '{profile_name}' not found"
        }
    
    def get_current_profile(self):
        """Get current voice profile info"""
        profile = self.current_profile
        return {
            'name': profile,
            'description': self.voice_profiles[profile]['description'],
            'accent': self.voice_profiles[profile]['accent']
        }
    
    def get_all_profiles(self):
        """Get all available voice profiles"""
        profiles = []
        for name, settings in self.voice_profiles.items():
            profiles.append({
                'name': name,
                'description': settings['description'],
                'accent': settings['accent']
            })
        return profiles
    
    def preview_voice(self, profile_name, text="Hello, this is a voice preview."):
        """Generate a preview of a voice profile"""
        return self.text_to_speech(text, "preview", profile_name)
    
    def get_profiles_by_accent(self, accent):
        """Get all profiles with a specific accent"""
        profiles = []
        for name, settings in self.voice_profiles.items():
            if settings['accent'].lower() == accent.lower():
                profiles.append({
                    'name': name,
                    'description': settings['description']
                })
        return profiles
