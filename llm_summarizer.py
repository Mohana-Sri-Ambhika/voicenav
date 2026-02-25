# backend/llm_summarizer.py - FIXED GROQ API VERSION
import os
import requests
import re
import threading
import time

# Only import nltk if available, but don't depend on it
try:
    from nltk.tokenize import sent_tokenize
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    print("  📝 Note: nltk not installed, using simple fallback")

class LLMSummarizer:
    """
    LLM Summarizer using Groq API (with Grok models) for superior text summarization
    """
    
    def __init__(self, api_key=None):
        print("🤖 Initializing Groq-Powered Summarizer...")
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.is_ready = False
        self.progress = 0
        self.available_models = []
        
        # Show key status (masked)
        if self.api_key:
            masked = self.api_key[:4] + "..." + self.api_key[-4:] if len(self.api_key) > 8 else "***"
            print(f"  🔑 API Key found: {masked}")
        else:
            print("  ❌ No API key found. Set GROQ_API_KEY environment variable.")
        
        # Start validation in background
        threading.Thread(target=self._validate_api, daemon=True).start()
    
    def _validate_api(self):
        """Check API connectivity and list available models"""
        try:
            self.progress = 30
            
            if not self.api_key:
                self.is_ready = False
                self.progress = 0
                return
            
            print("  🔑 Validating Groq API key...")
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                models = response.json().get("data", [])
                self.available_models = [m["id"] for m in models]
                print(f"  ✅ Connected! Available models: {len(self.available_models)}")
                
                # Show first few models
                if self.available_models:
                    print(f"     Models: {', '.join(self.available_models[:3])}...")
                
                self.is_ready = True
                self.progress = 100
            else:
                print(f"  ❌ API error: {response.status_code}")
                print(f"     Response: {response.text[:200]}")
                self.is_ready = False
                
        except Exception as e:
            print(f"  ⚠️ Connection issue: {e}")
            self.is_ready = False
    
    def summarize(self, text, max_length=None, min_length=None, style="detailed", model=None):
        """
        Generate summary using Groq API
        """
        # Handle None or empty input
        if not text or not isinstance(text, str):
            return ""
        
        text = text.strip()
        if len(text) < 50:
            return text
        
        # Clean text
        text = self._clean_text(text)
        word_count = len(text.split())
        print(f"\n  📊 Input: {word_count} words")
        
        # Auto-calculate lengths
        if max_length is None:
            if style == "brief":
                max_length = max(60, min(200, int(word_count * 0.15)))
            elif style == "detailed":
                max_length = max(150, min(500, int(word_count * 0.3)))
            else:  # normal
                max_length = max(100, min(300, int(word_count * 0.2)))
        
        if min_length is None:
            min_length = max(30, int(max_length * 0.4))
        
        print(f"  🎯 Target: {min_length}-{max_length} words ({style})")
        
        # Use API if ready
        if self.is_ready:
            return self._summarize_via_api(text, max_length, min_length, style, model)
        
        # Fallback
        print("  ⚠️ API not ready, using fallback")
        return self._fallback_summary(text, max_length)
    
    def _summarize_via_api(self, text, max_length, min_length, style, model=None):
        """Call Groq API for summarization"""
        
        # Select appropriate model
        if not model:
            # Try to find best available model
            preferred_models = [
                "mixtral-8x7b-32768",  # Fast, reliable, widely available
                "llama3-70b-8192",      # Good quality
                "llama3-8b-8192",       # Lightweight
                "gemma-7b-it"           # Fallback
            ]
            
            # Use any available model from preferred list
            for preferred in preferred_models:
                if preferred in self.available_models:
                    model = preferred
                    break
            
            # If none of preferred found, use first available
            if not model and self.available_models:
                model = self.available_models[0]
            else:
                model = "mixtral-8x7b-32768"  # Default
        
        print(f"  🚀 Using model: {model}")
        
        # Truncate text if too long (most models have ~8K context)
        if len(text) > 15000:
            text = text[:15000] + "..."
        
        # Style-specific instructions
        style_prompts = {
            "brief": "Create a VERY concise summary in 3-4 sentences. Focus only on the most essential points.",
            "normal": "Create a balanced summary covering the main topics and key details in 5-7 sentences.",
            "detailed": "Create a comprehensive summary covering all important aspects and nuances."
        }
        
        # Build prompt
        prompt = f"""{style_prompts[style]}

TEXT TO SUMMARIZE:
{text}

SUMMARY (approximately {min_length}-{max_length} words, factual and clear):"""
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a precise, factual summarization assistant. Create clear, accurate summaries."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": max_length * 2,
                "top_p": 0.9
            }
            
            print("  ⏳ Calling Groq API...")
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                summary = result["choices"][0]["message"]["content"].strip()
                
                # Clean up
                summary = re.sub(r'^SUMMARY:?\s*', '', summary, flags=re.IGNORECASE)
                summary = re.sub(r'^"|"$', '', summary)
                
                # If summary is too short, note it
                summary_words = len(summary.split())
                print(f"  ✅ Generated: {summary_words} words")
                
                if summary_words < 20:
                    print("  ⚠️ Summary very short, might need adjustment")
                
                return summary
            else:
                print(f"  ❌ API error {response.status_code}")
                print(f"     {response.text[:200]}")
                return self._fallback_summary(text, max_length)
                
        except Exception as e:
            print(f"  ❌ API call failed: {e}")
            return self._fallback_summary(text, max_length)
    
    def _fallback_summary(self, text, target_length=200):
        """Simple fallback when API unavailable"""
        try:
            # Simple sentence splitting if nltk not available
            if NLTK_AVAILABLE:
                sentences = sent_tokenize(text)
            else:
                # Simple fallback splitting
                sentences = re.split(r'[.!?]+', text)
                sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
            
            if len(sentences) <= 3:
                return ' '.join(sentences)
            
            # Take first few sentences
            result = []
            word_count = 0
            
            for sent in sentences[:5]:
                words = sent.split()
                if word_count + len(words) <= target_length:
                    result.append(sent)
                    word_count += len(words)
                else:
                    break
            
            return '. '.join(result) + '.'
            
        except Exception as e:
            print(f"Fallback error: {e}")
            return text[:500] + "..."
    
    def _clean_text(self, text):
        """Clean text for better processing"""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def is_ready_status(self):
        return self.is_ready
    
    def get_progress(self):
        return self.progress


# ================== TEST ==================
if __name__ == "__main__":
    print("="*60)
    print("TESTING GROQ SUMMARIZATION")
    print("="*60)
    
    # Get API key from environment
    api_key = os.environ.get("GROQ_API_KEY")
    
    if not api_key:
        print("\n❌ No GROQ_API_KEY found in environment variables")
        print("📝 Set it with: set GROQ_API_KEY=gsk_your_key_here")
        exit(1)
    
    # Initialize
    llm = LLMSummarizer(api_key=api_key)
    
    # Wait for validation
    print("\n⏳ Waiting for API validation...")
    timeout = 15
    start = time.time()
    while not llm.is_ready_status() and time.time() - start < timeout:
        print(f"  Progress: {llm.get_progress()}%")
        time.sleep(1)
    
    # Test text about Athena
    test_text = """
    Athena or Athene, often given the epithet Pallas, is an ancient Greek goddess associated with wisdom, warfare, and handicraft who was later syncretized with the Roman goddess Minerva. Athena was regarded as the patron and protectress of various cities across Greece, particularly the city of Athens, from which she most likely received her name. The Parthenon on the Athenian Acropolis is dedicated to her, along with numerous other temples and monuments. Her main festival in Athens was the Panathenaia, which was celebrated during the month of Hekatombaion in midsummer and was the most important festival on the Athenian calendar. 
    
    In one archaic Attic myth, Hephaestus tried and failed to rape her, resulting in Gaia giving birth to Erichthonius, an important Athenian founding hero whom Athena raised. She was the patron goddess of heroic endeavor; she was believed to have aided the heroes Perseus, Heracles, Bellerophon, and Jason. Since the Renaissance, Athena has become an international symbol of wisdom, the arts, and classical learning. Western artists and allegorists have often used Athena as a symbol of freedom and democracy.
    """
    
    print(f"\n📝 Original text: {len(test_text.split())} words")
    print(f"📝 Preview: {test_text[:150]}...\n")
    
    if llm.is_ready_status():
        print("="*60)
        print("GROQ-GENERATED SUMMARIES")
        print("="*60)
        
        # Test different styles
        for style in ["brief", "normal", "detailed"]:
            print(f"\n🔍 {style.upper()} SUMMARY:")
            summary = llm.summarize(test_text, style=style)
            print(f"📋 ({len(summary.split())} words)")
            print(f"📋 {summary}")
            print("-"*50)
    else:
        print("\n⚠️ API not available. Using fallback:")
        summary = llm._fallback_summary(test_text, 150)
        print(f"📋 {summary}")
    
    print("\n" + "="*60)
    print("✅ Test complete")
    print("="*60)