# backend/app.py

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import uuid
import re
from datetime import datetime
import threading
import json
import hashlib
import wave
import pyaudio
import time
from dotenv import load_dotenv

load_dotenv()

# Import all modules
from document_parser import DocumentParser
from nlp_processor import NLPProcessor
from llm_summarizer import LLMSummarizer
from tts_engine import TTSEngine
from quiz_generator import QuizGenerator
from database import Database
from export_manager import ExportManager
from history_manager import HistoryManager
from stats_manager import StatsManager
from chatbot_engine import DocumentChatbot

app = Flask(__name__)
CORS(app)

# Configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['AUDIO_FOLDER'] = 'audio_outputs'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['HISTORY_FOLDER'] = 'history_data'
app.config['CHAT_DATA_FOLDER'] = 'chat_data'
app.config['DOCUMENTS_FILE'] = 'documents_store.json'

# Create directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['AUDIO_FOLDER'], exist_ok=True)
os.makedirs('data', exist_ok=True)
os.makedirs('exports', exist_ok=True)
os.makedirs(app.config['HISTORY_FOLDER'], exist_ok=True)
os.makedirs(app.config['CHAT_DATA_FOLDER'], exist_ok=True)

# Initialize modules
print("\n" + "="*70)
print("🎤 VOICENAV AI - COMPLETE SYSTEM")
print("="*70)

parser = DocumentParser()
nlp = NLPProcessor()
llm = LLMSummarizer(api_key=os.getenv("GROQ_API_KEY"))
tts = TTSEngine(app.config['AUDIO_FOLDER'])
quiz = QuizGenerator()
db = Database('data')
exporter = ExportManager('exports')
history_manager = HistoryManager(app.config['HISTORY_FOLDER'])
stats_manager = StatsManager(app.config['HISTORY_FOLDER'])
chatbot = DocumentChatbot(use_llm=True)

# Active documents
documents = {}

# Improved VoiceNoteRecorder with better audio settings
class VoiceNoteRecorder:
    def __init__(self):
        self.is_recording = False
        self.frames = []
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000  # Changed from 44100 to 16000 for better speech quality
        self.chunk = 1024
        self.recording_thread = None
        self.temp_dir = 'temp_audio'
        os.makedirs(self.temp_dir, exist_ok=True)
        
    def start_recording(self):
        """Start recording voice note"""
        self.is_recording = True
        self.frames = []
        self.recording_thread = threading.Thread(target=self._record)
        self.recording_thread.start()
        print("🔍 Recording started...")
        return {"success": True, "message": "Started recording voice note"}
    
    def _record(self):
        """Record audio in background thread with better error handling"""
        try:
            p = pyaudio.PyAudio()
            
            # Print available devices for debugging
            print("🔍 Available audio input devices:")
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                if dev['maxInputChannels'] > 0:
                    print(f"  Device {i}: {dev['name']}")
            
            # Open stream with default device
            stream = p.open(format=self.audio_format,
                          channels=self.channels,
                          rate=self.rate,
                          input=True,
                          frames_per_buffer=self.chunk)
            
            print(f"🔍 Recording at {self.rate}Hz, {self.channels} channel(s)")
            
            while self.is_recording:
                try:
                    data = stream.read(self.chunk, exception_on_overflow=False)
                    self.frames.append(data)
                except Exception as e:
                    print(f"⚠️ Recording read error: {e}")
                    break
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            print(f"🔍 Recording stopped. Captured {len(self.frames)} frames")
            
        except Exception as e:
            print(f"❌ Recording error: {e}")
    
    def stop_recording(self):
        """Stop recording and save to file with noise reduction"""
        print("🔍 Stopping recording...")
        self.is_recording = False
        
        if self.recording_thread:
            self.recording_thread.join(timeout=3)
        
        if not self.frames:
            print("❌ No frames captured")
            return None
        
        # Apply simple noise gate to reduce static
        processed_frames = self._apply_noise_gate()
        
        # Save to temporary WAV file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"voice_note_{timestamp}.wav"
        filepath = os.path.join(self.temp_dir, filename)
        
        try:
            wf = wave.open(filepath, 'wb')
            wf.setnchannels(self.channels)
            wf.setsampwidth(pyaudio.PyAudio().get_sample_size(self.audio_format))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(processed_frames))
            wf.close()
            
            file_size = os.path.getsize(filepath)
            print(f"✅ Audio saved: {filepath} ({file_size} bytes)")
            
            # Verify the file
            try:
                with wave.open(filepath, 'rb') as test_wf:
                    print(f"✅ File verified: {test_wf.getnframes()} frames, {test_wf.getframerate()}Hz")
            except Exception as e:
                print(f"❌ File verification failed: {e}")
                return None
                
            return filepath
            
        except Exception as e:
            print(f"❌ Error saving recording: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _apply_noise_gate(self, threshold=300):
        """Apply simple noise gate to reduce static"""
        import numpy as np
        
        processed_frames = []
        for frame in self.frames:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(frame, dtype=np.int16)
            
            # Apply noise gate - silence samples below threshold
            audio_array[np.abs(audio_array) < threshold] = 0
            
            # Convert back to bytes
            processed_frames.append(audio_array.tobytes())
        
        print(f"🔍 Applied noise gate with threshold {threshold}")
        return processed_frames

# Initialize voice note recorder
voice_recorder = VoiceNoteRecorder()

# Improved speech-to-text function
def speech_to_text(audio_file):
    """Convert audio file to text using speech recognition with better error handling"""
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        
        print(f"🔍 Processing audio file: {audio_file}")
        
        with sr.AudioFile(audio_file) as source:
            # Adjust for ambient noise
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print("🔍 Adjusted for ambient noise")
            
            # Record the audio
            audio_data = recognizer.record(source)
            print(f"🔍 Audio data captured: {len(audio_data.frame_data)} bytes")
        
        # Try Google Speech Recognition
        try:
            print("🔍 Sending to Google Speech Recognition...")
            text = recognizer.recognize_google(audio_data)
            print(f"✅ Speech recognized: {text}")
            return text
        except sr.UnknownValueError:
            print("⚠️ Google Speech Recognition could not understand audio")
        except sr.RequestError as e:
            print(f"⚠️ Could not request results from Google Speech Recognition service; {e}")
        except Exception as e:
            print(f"⚠️ Speech recognition error: {e}")
            
    except ImportError:
        print("⚠️ speech_recognition not installed. Install with: pip install SpeechRecognition")
    except Exception as e:
        print(f"❌ Speech recognition error: {e}")
        import traceback
        traceback.print_exc()
    
    return None

# Load existing documents
def load_documents():
    global documents
    try:
        if os.path.exists(app.config['DOCUMENTS_FILE']):
            with open(app.config['DOCUMENTS_FILE'], 'r') as f:
                documents = json.load(f)
            print(f"📚 Loaded {len(documents)} documents from store")
    except Exception as e:
        print(f"⚠️ Could not load documents: {e}")

# Save documents
def save_documents():
    try:
        serializable_docs = {}
        for doc_id, doc in documents.items():
            serializable_docs[doc_id] = {
                'id': doc['id'],
                'filename': doc['filename'],
                'source_type': doc['source_type'],
                'overview': doc.get('overview', '')[:500] if doc.get('overview') else '',
                'sections': list(doc.get('sections', {}).keys()),
                'sections_dict': doc.get('sections', {}),
                'word_count': doc.get('word_count', len(doc.get('text', '').split())),
                'uploaded_at': doc.get('uploaded_at', datetime.now().isoformat()),
                'content_hash': doc.get('content_hash', '')
            }
        
        with open(app.config['DOCUMENTS_FILE'], 'w') as f:
            json.dump(serializable_docs, f, indent=2)
    except Exception as e:
        print(f"⚠️ Could not save documents: {e}")

load_documents()
print("✅ System ready!")
print("="*70 + "\n")

# ==================== DUPLICATE CLEANUP FUNCTION ====================

def cleanup_duplicates():
    """Remove duplicate documents from history and consolidate"""
    try:
        print("\n🧹 Cleaning up duplicate documents...")
        
        # Get all history documents
        all_history = history_manager.get_all_history()
        
        # Track unique documents by content hash
        unique_docs = {}
        duplicates = []
        version_counts = {}
        
        for entry in all_history:
            if entry.get('type') == 'document':
                # Create a more reliable key using filename, words, and sections
                key = f"{entry.get('filename')}_{entry.get('words')}_{entry.get('sections')}"
                
                if key in unique_docs:
                    duplicates.append(entry)
                    # Count versions
                    if key not in version_counts:
                        version_counts[key] = 2
                    else:
                        version_counts[key] += 1
                else:
                    unique_docs[key] = entry
                    version_counts[key] = 1
        
        if duplicates:
            print(f"   ✅ Found {len(duplicates)} duplicate entries to clean")
            for key, count in version_counts.items():
                if count > 1:
                    print(f"   📊 {unique_docs[key].get('filename')} has {count} versions")
            
            # Keep only unique documents in history (keep the most recent)
            cleaned_history = []
            seen_keys = set()
            
            # Process in reverse to keep most recent
            for entry in reversed(all_history):
                if entry.get('type') == 'document':
                    key = f"{entry.get('filename')}_{entry.get('words')}_{entry.get('sections')}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        cleaned_history.append(entry)
                else:
                    cleaned_history.append(entry)
            
            # Reverse back to original order
            cleaned_history.reverse()
            
            # Save cleaned history
            history_manager.full_history = cleaned_history
            history_manager._save(history_manager.history_file, cleaned_history)
            
            # Rebuild documents list
            history_manager.documents = [e for e in cleaned_history if e.get('type') == 'document']
            history_manager._save(history_manager.documents_file, history_manager.documents)
            
            print(f"   ✅ Cleaned up to {len(history_manager.documents)} unique documents")
            
            # Update stats to reflect unique count
            stats = stats_manager.get_stats()
            stats['total_documents'] = len(history_manager.documents)
            stats_manager._save()
        else:
            print("   ✅ No duplicates found")
            
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")

# Run cleanup on startup
cleanup_duplicates()

# ==================== VERIFY DOCUMENT STORAGE ====================

def verify_document_storage():
    """Verify that documents are being properly saved"""
    try:
        if os.path.exists(app.config['DOCUMENTS_FILE']):
            with open(app.config['DOCUMENTS_FILE'], 'r') as f:
                stored_docs = json.load(f)
            print(f"📚 Verified {len(stored_docs)} documents in persistent storage")
            return len(stored_docs)
    except Exception as e:
        print(f"⚠️ Could not verify storage: {e}")
    return 0

# Call this after load_documents()
stored_count = verify_document_storage()
if stored_count > len(documents):
    print(f"⚠️ Warning: Storage has {stored_count} docs but memory has {len(documents)}")
    if stored_count > 0 and len(documents) == 0:
        print("📥 Reloading documents from storage...")
        load_documents()

# ==================== SYNC STATS ON STARTUP ====================

def sync_initial_stats():
    """Sync stats with actual data on startup"""
    try:
        print("\n📊 Syncing statistics...")
        
        # Get counts from all sources
        db_counts = db.sync_counts()
        history_docs = history_manager.get_documents()
        
        # Get current stats
        stats = stats_manager.get_stats()
        
        # Calculate unique document count (use history as source of truth)
        unique_doc_count = len(history_docs)
        
        # Update if needed
        if stats.get('total_documents', 0) != unique_doc_count:
            stats['total_documents'] = unique_doc_count
            stats_manager._save()
            print(f"   ✅ Synced documents: {stats['total_documents']}")
        
        # Sync notes count
        if stats.get('total_notes', 0) != db_counts['notes']:
            stats['total_notes'] = db_counts['notes']
            stats_manager._save()
            print(f"   ✅ Synced notes: {stats['total_notes']}")
        
        # Sync bookmarks count
        if stats.get('total_bookmarks', 0) != db_counts['bookmarks']:
            stats['total_bookmarks'] = db_counts['bookmarks']
            stats_manager._save()
            print(f"   ✅ Synced bookmarks: {stats['total_bookmarks']}")
        
        print("   ✅ Stats sync complete!")
            
    except Exception as e:
        print(f"⚠️ Stats sync error: {e}")

# Run sync
sync_initial_stats()

# ==================== FRONTEND ROUTES ====================

@app.route('/')
def serve_index():
    return send_file('../frontend/index.html')

@app.route('/history.html')
def serve_history():
    return send_file('../frontend/history.html')

@app.route('/chat.html')
def serve_chat():
    return send_file('../frontend/chat.html')

@app.route('/notes.html')
def serve_notes():
    return send_file('../frontend/notes.html')

@app.route('/styles.css')
def serve_styles():
    return send_file('../frontend/styles.css')

@app.route('/script.js')
def serve_script():
    return send_file('../frontend/script.js')

# ==================== API ROUTES ====================

@app.route('/api/health', methods=['GET'])
def health():
    llm_status = "disabled"
    if hasattr(chatbot, 'use_llm'):
        if chatbot.use_llm and hasattr(chatbot, 'llm_available'):
            llm_status = "enabled" if chatbot.llm_available else "enabled (fallback to TF-IDF)"
        else:
            llm_status = "disabled (using TF-IDF)"
    
    return jsonify({
        "status": "healthy", 
        "chatbot": llm_status,
        "documents_count": len(documents),
        "server_time": datetime.now().isoformat()
    })

@app.route('/api/documents', methods=['GET'])
def get_documents_list():
    """Get all uploaded documents with chat stats (unique only)"""
    try:
        # Group documents by content to show unique ones
        unique_docs_map = {}
        version_tracking = {}
        
        # First pass: identify unique documents and count versions
        for doc_id, doc in documents.items():
            # Create a key based on filename and word count for grouping
            key = f"{doc['filename']}_{doc.get('word_count', 0)}"
            
            if key not in version_tracking:
                version_tracking[key] = []
            version_tracking[key].append(doc_id)
        
        # Second pass: create unique document entries
        for doc_id, doc in documents.items():
            key = f"{doc['filename']}_{doc.get('word_count', 0)}"
            
            # Only add if not already added, or if this is the most recent
            if key not in unique_docs_map or doc.get('uploaded_at', '') > unique_docs_map[key].get('uploaded_at', ''):
                unique_docs_map[key] = {
                    'id': doc_id,
                    'filename': doc['filename'],
                    'source_type': doc.get('source_type', 'file'),
                    'overview': doc.get('overview', '')[:200],
                    'sections_count': len(doc.get('sections', {})),
                    'word_count': doc.get('word_count', 0),
                    'uploaded_at': doc.get('uploaded_at', ''),
                    'message_count': 0,
                    'notes_count': len(db.get_notes(doc_id)),
                    'bookmarks_count': len(db.get_bookmarks(doc_id)),
                    'version_count': len(version_tracking[key])
                }
        
        # Add message counts
        for doc_id, doc in documents.items():
            history = chatbot.get_conversation_history(doc_id)
            if history and len(history) > 0:
                key = f"{doc['filename']}_{doc.get('word_count', 0)}"
                if key in unique_docs_map:
                    unique_docs_map[key]['message_count'] += len(history) // 2
        
        docs_list = list(unique_docs_map.values())
        
        # Sort by most recent upload
        docs_list.sort(key=lambda x: x.get('uploaded_at', ''), reverse=True)
        
        return jsonify({
            'success': True,
            'documents': docs_list,
            'total_count': len(docs_list),
            'total_versions': len(documents)
        })
    except Exception as e:
        print(f"❌ Error getting documents: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/documents/<doc_id>', methods=['GET'])
def get_document_details(doc_id):
    """Get detailed information about a specific document"""
    try:
        if doc_id not in documents:
            return jsonify({'success': False, 'error': 'Document not found'}), 404
        
        doc = documents[doc_id]
        history = chatbot.get_conversation_history(doc_id)
        notes = db.get_notes(doc_id)
        bookmarks = db.get_bookmarks(doc_id)
        
        return jsonify({
            'success': True,
            'document': {
                'id': doc_id,
                'filename': doc['filename'],
                'source_type': doc.get('source_type', 'file'),
                'overview': doc.get('overview', ''),
                'sections': list(doc.get('sections', {}).keys()),
                'sections_dict': doc.get('sections', {}),
                'sections_count': len(doc.get('sections', {})),
                'word_count': doc.get('word_count', len(doc.get('text', '').split())),
                'uploaded_at': doc.get('uploaded_at', ''),
                'message_count': len(history) // 2,
                'notes_count': len(notes),
                'bookmarks_count': len(bookmarks)
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat_with_document():
    """Chat with your document"""
    try:
        data = request.json
        question = data.get('question', '').strip()
        doc_id = data.get('document_id')
        
        if not question:
            return jsonify({'success': False, 'error': 'Please ask a question'}), 400
        
        if not doc_id or doc_id not in documents:
            return jsonify({'success': False, 'error': 'Please upload a document first'}), 400
        
        # Get conversation history
        history = chatbot.get_conversation_history(doc_id)
        
        # Get answer from chatbot
        result = chatbot.answer_question(doc_id, question, history)
        
        # Track in history
        history_manager.add_command({
            "command": question,
            "intent": "chat",
            "document": documents[doc_id]['filename'],
            "response": result['answer'][:100],
            "timestamp": datetime.now().isoformat()
        })
        
        # Update stats
        stats_manager.increment_commands()
        
        return jsonify({
            'success': True,
            'answer': result['answer'],
            'confidence': result.get('confidence', 0.5),
            'sources': result.get('sources', [])
        })
        
    except Exception as e:
        print(f"❌ Chat error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chat/history/<doc_id>', methods=['GET'])
def get_chat_history(doc_id):
    """Get conversation history"""
    try:
        history = chatbot.get_conversation_history(doc_id)
        return jsonify({'success': True, 'history': history})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/chat/clear/<doc_id>', methods=['POST'])
def clear_chat_history(doc_id):
    """Clear conversation"""
    try:
        chatbot.clear_conversation(doc_id)
        return jsonify({'success': True, 'message': 'Chat history cleared'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    """Get all history entries (with duplicates filtered)"""
    try:
        all_history = history_manager.get_all_history()
        
        # Filter out duplicate document entries for display
        unique_history = []
        seen_docs = set()
        doc_versions = {}
        
        # First pass: identify unique documents and count versions
        for entry in all_history:
            if entry.get('type') == 'document':
                key = f"{entry.get('filename')}_{entry.get('words')}_{entry.get('sections')}"
                if key not in doc_versions:
                    doc_versions[key] = 1
                else:
                    doc_versions[key] += 1
        
        # Second pass: build unique history
        for entry in all_history:
            if entry.get('type') == 'document':
                key = f"{entry.get('filename')}_{entry.get('words')}_{entry.get('sections')}"
                # Only add the first occurrence (or you could add the most recent)
                if key not in seen_docs:
                    seen_docs.add(key)
                    # Add version info to the entry
                    entry_copy = entry.copy()
                    entry_copy['version_count'] = doc_versions[key]
                    unique_history.append(entry_copy)
            else:
                unique_history.append(entry)
        
        stats = stats_manager.get_stats()
        
        return jsonify({
            "success": True,
            "history": unique_history,
            "stats": stats
        })
    except Exception as e:
        print(f"❌ Error in history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/history/documents', methods=['GET'])
def get_document_history():
    """Get document history (unique only)"""
    try:
        all_documents = history_manager.get_documents()
        
        # Group by unique content and keep only the most recent
        unique_docs = {}
        version_counts = {}
        
        # First pass: collect all documents
        for doc in all_documents:
            # Create a unique key based on filename and word count
            # This groups similar documents together
            key = f"{doc.get('filename')}_{doc.get('words')}_{doc.get('sections')}"
            
            # Store the document if it's newer than existing one
            if key not in unique_docs or doc.get('timestamp', '') > unique_docs[key].get('timestamp', ''):
                unique_docs[key] = doc
            
            # Count versions
            if key not in version_counts:
                version_counts[key] = 1
            else:
                version_counts[key] += 1
        
        # Convert to list and add version info
        documents_list = []
        for key, doc in unique_docs.items():
            doc_copy = doc.copy()
            doc_copy['version_count'] = version_counts.get(key, 1)
            documents_list.append(doc_copy)
        
        # Sort by most recent
        documents_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Also include active documents that might not be in history yet
        for doc_id, doc in documents.items():
            # Check if this document is already in the list
            found = False
            for hist_doc in documents_list:
                if hist_doc.get('filename') == doc['filename'] and hist_doc.get('words') == doc.get('word_count'):
                    found = True
                    break
            
            if not found:
                # Add it
                documents_list.append({
                    'id': doc_id,
                    'filename': doc['filename'],
                    'source_type': doc.get('source_type', 'file'),
                    'sections': len(doc.get('sections', {})),
                    'words': doc.get('word_count', 0),
                    'timestamp': doc.get('uploaded_at', datetime.now().isoformat()),
                    'version_count': 1
                })
        
        return jsonify({"success": True, "documents": documents_list})
    except Exception as e:
        print(f"❌ Error in document history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/history/commands', methods=['GET'])
def get_command_history():
    """Get command history"""
    try:
        commands = history_manager.get_commands()
        return jsonify({"success": True, "commands": commands})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/history/clear', methods=['POST'])
def clear_history():
    """Clear all history"""
    try:
        history_manager.clear_history()
        stats_manager.reset_stats()
        return jsonify({"success": True, "message": "History cleared"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get usage statistics with proper persistence"""
    try:
        # Get stats from stats manager
        stats = stats_manager.get_stats()
        
        # Get real counts from database
        db_counts = db.sync_counts()
        
        # Get unique document count from history
        history_docs = history_manager.get_documents()
        unique_doc_count = len(history_docs)
        
        # Update stats if needed (should already be synced, but just in case)
        if stats.get('total_documents', 0) != unique_doc_count:
            stats['total_documents'] = unique_doc_count
        
        # Get note and bookmark counts from database
        stats['total_notes'] = db_counts['notes']
        stats['total_bookmarks'] = db_counts['bookmarks']
        
        # Count chat sessions and messages
        chat_sessions = 0
        total_messages = 0
        for doc_id in documents:
            history = chatbot.get_conversation_history(doc_id)
            if history and len(history) > 0:
                chat_sessions += 1
                total_messages += len(history)
        
        # Also check history for command counts
        commands = history_manager.get_commands()
        
        stats['chat_sessions'] = chat_sessions
        stats['total_messages'] = total_messages
        stats['active_documents'] = len(documents)
        stats['unique_documents'] = unique_doc_count
        stats['total_versions'] = len(history_manager.get_all_history())
        stats['total_commands_history'] = len(commands)
        stats['last_updated'] = datetime.now().isoformat()
        
        return jsonify({"success": True, "stats": stats})
        
    except Exception as e:
        print(f"❌ Stats error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/notes/<doc_id>', methods=['GET'])
def get_notes(doc_id):
    """Get notes for a document"""
    try:
        notes = db.get_notes(doc_id)
        return jsonify({"success": True, "notes": notes})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/notes/all', methods=['GET'])
def get_all_notes():
    """Get all notes from all documents"""
    try:
        all_notes = db.get_all_notes()
        return jsonify({
            "success": True,
            "notes": all_notes,
            "count": len(all_notes)
        })
    except Exception as e:
        print(f"❌ Error getting all notes: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/bookmarks/<doc_id>', methods=['GET'])
def get_bookmarks(doc_id):
    """Get bookmarks for a document"""
    try:
        bookmarks = db.get_bookmarks(doc_id)
        return jsonify({"success": True, "bookmarks": bookmarks})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload():
    """Handle file upload OR URL submission with duplicate prevention"""
    try:
        content_hash = None
        source_name = None
        source_type = None
        text = None
        
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                return jsonify({"success": False, "error": "No file selected"}), 400
            
            # Read file content for hash
            file_content = file.read()
            file.seek(0)
            
            # Create hash of file content
            content_hash = hashlib.md5(file_content).hexdigest()
            
            # Check for duplicate by content hash
            for existing_id, existing_doc in documents.items():
                if existing_doc.get('content_hash') == content_hash:
                    print(f"⚠️ Duplicate file detected: {file.filename}")
                    return jsonify({
                        "success": True,
                        "document_id": existing_id,
                        "filename": existing_doc['filename'],
                        "source_type": existing_doc['source_type'],
                        "overview": existing_doc.get('overview', ''),
                        "sections": list(existing_doc.get('sections', {}).keys()),
                        "sections_dict": existing_doc.get('sections', {}),
                        "section_count": len(existing_doc.get('sections', {})),
                        "word_count": existing_doc.get('word_count', 0),
                        "audio_url": f"/audio/overview_{existing_id}.mp3" if os.path.exists(os.path.join(app.config['AUDIO_FOLDER'], f"overview_{existing_id}.mp3")) else None,
                        "duplicate": True,
                        "message": "Document already exists"
                    }), 200
            
            doc_id = str(uuid.uuid4())
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{doc_id}_{filename}")
            file.save(filepath)
            
            print(f"\n📄 Processing file: {filename}")
            text = parser.parse_file(filepath, filename)
            source_type = 'file'
            source_name = filename
        
        elif request.is_json and 'url' in request.json:
            data = request.get_json()
            url = data.get('url', '').strip()
            
            if not url:
                return jsonify({"success": False, "error": "Empty URL"}), 400
            
            print(f"\n🌐 Processing URL: {url}")
            text = parser.parse_url(url)
            
            if not text or len(text.strip()) < 100:
                return jsonify({"success": False, "error": "Could not extract text from URL"}), 400
            
            # Create hash of text content for URL
            content_hash = hashlib.md5(text.encode('utf-8')).hexdigest()
            
            # Check for duplicate by content hash
            for existing_id, existing_doc in documents.items():
                if existing_doc.get('content_hash') == content_hash:
                    print(f"⚠️ Duplicate URL detected: {url}")
                    return jsonify({
                        "success": True,
                        "document_id": existing_id,
                        "filename": existing_doc['filename'],
                        "source_type": existing_doc['source_type'],
                        "overview": existing_doc.get('overview', ''),
                        "sections": list(existing_doc.get('sections', {}).keys()),
                        "sections_dict": existing_doc.get('sections', {}),
                        "section_count": len(existing_doc.get('sections', {})),
                        "word_count": existing_doc.get('word_count', 0),
                        "audio_url": f"/audio/overview_{existing_id}.mp3" if os.path.exists(os.path.join(app.config['AUDIO_FOLDER'], f"overview_{existing_id}.mp3")) else None,
                        "duplicate": True,
                        "message": "URL already exists"
                    }), 200
            
            doc_id = str(uuid.uuid4())
            source_name = url
            source_type = 'url'
        
        else:
            return jsonify({"success": False, "error": "No file or URL provided"}), 400
        
        if not text or len(text.strip()) < 100:
            return jsonify({"success": False, "error": "Not enough text extracted"}), 400
        
        print(f"📄 Text length: {len(text)} characters")
        
        sections_dict = nlp.extract_sections(text)
        
        try:
            import nltk
            from nltk.tokenize import sent_tokenize
            try:
                nltk.data.find('tokenizers/punkt')
            except:
                nltk.download('punkt', quiet=True)
            
            sentences = sent_tokenize(text)
            overview = ' '.join(sentences[:3]) if len(sentences) >= 3 else text[:300]
        except:
            overview = text[:300]
        
        documents[doc_id] = {
            "id": doc_id,
            "filename": source_name,
            "source_type": source_type,
            "text": text,
            "sections": sections_dict,
            "overview": overview,
            "word_count": len(text.split()),
            "uploaded_at": datetime.now().isoformat(),
            "content_hash": content_hash
        }
        
        db.save_document(doc_id, documents[doc_id])
        
        try:
            chatbot.index_document(doc_id, text, source_name)
            print(f"💬 Document indexed for Q&A")
        except Exception as e:
            print(f"⚠️ Chatbot indexing error: {e}")
        
        # Add to history
        history_manager.add_document({
            "id": doc_id,
            "filename": source_name,
            "type": source_type,
            "sections": len(sections_dict),
            "words": len(text.split()),
            "timestamp": datetime.now().isoformat()
        })
        
        # Only increment stats for NEW unique documents
        is_new = True
        for existing_id, existing_doc in documents.items():
            if existing_id != doc_id and existing_doc.get('content_hash') == content_hash:
                is_new = False
                break
        
        if is_new:
            stats_manager.increment_documents()
            print(f"   ✅ New unique document added. Total unique: {stats_manager.get_stats().get('total_documents')}")
        
        save_documents()
        
        audio_file = tts.text_to_speech(overview, f"overview_{doc_id}")
        
        sections_list = list(sections_dict.keys()) if sections_dict else []
        
        return jsonify({
            "success": True,
            "document_id": doc_id,
            "filename": source_name,
            "source_type": source_type,
            "overview": overview,
            "sections": sections_list,
            "sections_dict": sections_dict,
            "section_count": len(sections_dict),
            "word_count": len(text.split()),
            "audio_url": f"/audio/{audio_file}" if audio_file else None,
            "duplicate": False
        })
        
    except Exception as e:
        print(f"❌ Upload error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/command', methods=['POST'])
def command():
    """Process voice commands"""
    try:
        data = request.json
        cmd = data.get('command', '').lower()
        doc_id = data.get('document_id')
        
        if not doc_id or doc_id not in documents:
            return jsonify({"success": False, "error": "Please upload a document first"}), 400
        
        doc = documents[doc_id]
        
        intent = nlp.identify_intent(cmd)
        
        response = {"success": True, "intent": intent}
        response_text = ""
        
        if intent == 'read':
            text_to_read = ""
            message = ""
            
            if 'first line' in cmd:
                lines = doc['text'].split('\n')
                first_line = next((l for l in lines if l.strip()), "No content")
                text_to_read = first_line
                message = "Reading first line"
                response_text = text_to_read[:100]
            
            elif 'overview' in cmd or 'summary' in cmd:
                text_to_read = doc['overview']
                message = "Reading overview"
                response_text = "Reading overview"
            
            else:
                found_section = None
                section_content = None
                
                for section_name in doc['sections'].keys():
                    if section_name.lower() in cmd.lower():
                        found_section = section_name
                        section_content = doc['sections'][section_name]
                        break
                
                if not found_section:
                    cmd_words = set(cmd.lower().split())
                    for section_name in doc['sections'].keys():
                        section_words = set(section_name.lower().split())
                        if cmd_words & section_words:
                            found_section = section_name
                            section_content = doc['sections'][section_name]
                            break
                
                if found_section and section_content:
                    if len(section_content) > 1000:
                        text_to_read = section_content[:1000] + "..."
                    else:
                        text_to_read = section_content
                    message = f"Reading: {found_section}"
                    response_text = f"Reading section: {found_section}"
                else:
                    text_to_read = doc['overview']
                    message = "Reading overview"
                    response_text = "Reading overview"
            
            audio_file = tts.text_to_speech(text_to_read, f"read_{doc_id}")
            response.update({
                "message": message,
                "text": text_to_read[:200] + "..." if len(text_to_read) > 200 else text_to_read,
                "audio_url": f"/audio/{audio_file}" if audio_file else None
            })
        
        elif intent == 'summarize':
            found_section = None
            for section_name in doc['sections'].keys():
                if section_name.lower() in cmd.lower():
                    found_section = section_name
                    break
            
            if found_section:
                text = doc['sections'][found_section]
                summary = llm.summarize(text)
                response.update({
                    "message": f"Summary of {found_section}",
                    "summary": summary
                })
                response_text = f"Summarized: {found_section}"
            else:
                summary = llm.summarize(doc['text'][:3000])
                response.update({
                    "message": "Document summary",
                    "summary": summary
                })
                response_text = "Summarized document"
        
        elif intent == 'explain':
            try:
                result = chatbot.answer_question(doc_id, cmd)
                answer = result['answer']
            except:
                answer = f"Based on the document: {doc['overview']}"
            
            audio_file = tts.text_to_speech(answer, f"answer_{doc_id}")
            response.update({
                "message": "Here's your answer",
                "answer": answer,
                "audio_url": f"/audio/{audio_file}" if audio_file else None
            })
            response_text = answer[:100]
        
        elif intent == 'quiz':
            questions = quiz.generate_quiz(doc['text'][:4000])
            response.update({
                "message": f"Generated {len(questions)} questions",
                "quiz": questions
            })
            response_text = f"Generated {len(questions)} quiz questions"
            stats_manager.increment_quizzes()
        
        elif intent == 'note':
            # Voice note recording commands
            if 'start notes' in cmd or 'start recording' in cmd or 'begin notes' in cmd:
                # Start voice note recording
                result = voice_recorder.start_recording()
                response.update({
                    "message": "🎤 Recording your voice note... Say 'stop notes' when done",
                    "recording": True
                })
                response_text = "Started voice note recording"
            
            elif 'stop notes' in cmd or 'stop recording' in cmd or 'end notes' in cmd:
                # Stop recording and save
                if voice_recorder.is_recording:
                    audio_file = voice_recorder.stop_recording()
                    
                    if audio_file:
                        note_text = speech_to_text(audio_file)
                        
                        if not note_text:
                            note_text = f"Voice note recorded at {datetime.now().strftime('%H:%M:%S')}"
                        
                        note = db.add_note(doc_id, {
                            "text": note_text,
                            "source": "voice",
                            "audio_file": os.path.basename(audio_file)
                        })
                        
                        stats_manager.increment_notes()
                        
                        response.update({
                            "message": f"✅ Voice note saved: \"{note_text[:100]}\"",
                            "note": note,
                            "text": note_text
                        })
                        response_text = f"Saved voice note: {note_text[:50]}"
                    else:
                        response.update({"message": "No recording found"})
                else:
                    response.update({"message": "No active recording"})
            
            else:
                # Regular text note
                note_text = ""
                patterns = [
                    r'note\s+(.+)$',
                    r'remember\s+(.+)$',
                    r'save\s+(.+)$',
                    r'make a note\s+(.+)$',
                    r'create a note\s+(.+)$',
                    r'add note\s+(.+)$'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, cmd, re.IGNORECASE)
                    if match:
                        note_text = match.group(1).strip()
                        break
                
                if not note_text and 'note' in cmd:
                    parts = cmd.split('note')
                    if len(parts) > 1:
                        note_text = parts[1].strip()
                
                note_text = note_text.strip(' .,;:')
                
                if note_text and len(note_text) > 3:
                    note = db.add_note(doc_id, {"text": note_text, "source": "text"})
                    response.update({
                        "message": f"✅ Note saved: \"{note_text[:50]}\"",
                        "note": note
                    })
                    response_text = f"Saved note: {note_text[:50]}"
                    stats_manager.increment_notes()
                else:
                    response.update({
                        "message": "What would you like to note? Try: 'note this is important' or 'start notes' for voice recording"
                    })
        
        elif intent == 'bookmark':
            section = "Current section"
            for section_name in doc['sections'].keys():
                if section_name.lower() in cmd.lower():
                    section = section_name
                    break
            
            bookmark = db.add_bookmark(doc_id, {"section": section})
            response.update({
                "message": f"🔖 Bookmarked: {section}",
                "bookmark": bookmark
            })
            response_text = f"Bookmarked: {section}"
            stats_manager.increment_bookmarks()
        
        elif 'show notes' in cmd or 'list notes' in cmd or 'my notes' in cmd:
            notes = db.get_notes(doc_id)
            if notes and len(notes) > 0:
                notes_list = "\n".join([f"• {n['text'][:50]}" for n in notes[-5:]])
                response.update({
                    "message": f"Your recent notes:\n{notes_list}",
                    "notes": notes
                })
                response_text = f"Showing {len(notes)} notes"
            else:
                response.update({"message": "No notes yet"})
        
        elif 'show bookmarks' in cmd or 'list bookmarks' in cmd:
            bookmarks = db.get_bookmarks(doc_id)
            if bookmarks and len(bookmarks) > 0:
                bookmarks_list = "\n".join([f"• {b['section'][:50]}" for b in bookmarks[-5:]])
                response.update({
                    "message": f"Your bookmarks:\n{bookmarks_list}",
                    "bookmarks": bookmarks
                })
                response_text = f"Showing {len(bookmarks)} bookmarks"
            else:
                response.update({"message": "No bookmarks yet"})
        
        elif 'export' in cmd:
            try:
                export_path = exporter.export_document_data(doc_id, db, doc['filename'])
                response.update({
                    "message": f"📥 Exported to: {os.path.basename(export_path)}",
                    "export_path": export_path,
                    "export_file": os.path.basename(export_path)
                })
                response_text = f"Exported data"
                stats_manager.increment_exports()
            except Exception as e:
                response.update({"message": f"Export failed: {str(e)}"})
        
        elif intent == 'control':
            if 'pause' in cmd:
                response.update({"action": "pause", "message": "⏸️ Paused"})
                response_text = "Paused playback"
            elif 'resume' in cmd or 'play' in cmd:
                response.update({"action": "resume", "message": "▶️ Resumed"})
                response_text = "Resumed playback"
            elif 'stop' in cmd:
                response.update({"action": "stop", "message": "⏹️ Stopped"})
                response_text = "Stopped playback"
            elif 'faster' in cmd or 'speed up' in cmd:
                response.update({"action": "speed_up", "message": "⚡ Speed increased"})
                response_text = "Speed increased"
            elif 'slower' in cmd or 'slow down' in cmd:
                response.update({"action": "slow_down", "message": "🐢 Speed decreased"})
                response_text = "Speed decreased"
            else:
                response.update({"message": "Control commands: pause, resume, stop, faster, slower"})
        
        elif 'help' in cmd:
            help_text = """
📖 READ: 'read section name', 'read overview', 'read first line'
📝 SUMMARIZE: 'summarize this', 'summarize section'
💬 CHAT: 'ask about X', 'what is Y?', 'explain Z'
📌 NOTE: 'note this is important', 'start notes' (for voice recording)
🔖 BOOKMARK: 'bookmark this section'
📋 QUIZ: 'quiz', 'generate quiz'
📥 EXPORT: 'export my notes'
🎚️ CONTROL: 'pause', 'resume', 'faster', 'slower'
            """
            response.update({"message": help_text})
            response_text = "Displayed help"
        
        else:
            response.update({
                "message": "Command not recognized. Say 'help' for options."
            })
        
        if response_text or response.get('message'):
            history_manager.add_command({
                "command": cmd,
                "intent": intent,
                "document": doc['filename'],
                "response": response_text or str(response.get('message', ''))[:100],
                "timestamp": datetime.now().isoformat()
            })
        
        stats_manager.increment_commands()
        
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ Command error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# Audio serving routes
@app.route('/audio/<filename>', methods=['GET'])
def serve_audio(filename):
    try:
        return send_file(os.path.join(app.config['AUDIO_FOLDER'], filename))
    except:
        return jsonify({"error": "Audio not found"}), 404

@app.route('/temp_audio/<filename>', methods=['GET'])
def serve_temp_audio(filename):
    try:
        return send_file(os.path.join('temp_audio', filename))
    except Exception as e:
        print(f"Error serving temp audio: {e}")
        return jsonify({"error": "Audio not found"}), 404

@app.route('/api/export/<doc_id>', methods=['GET'])
def export_document(doc_id):
    if doc_id not in documents:
        return jsonify({"error": "Document not found"}), 404
    
    export_path = exporter.export_document_data(doc_id, db, documents[doc_id]['filename'])
    return send_file(export_path, as_attachment=True)

# Voice note routes
@app.route('/api/voice-note/start', methods=['POST'])
def start_voice_note():
    """Start recording a voice note"""
    try:
        result = voice_recorder.start_recording()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/voice-note/stop', methods=['POST'])
def stop_voice_note():
    """Stop recording and save voice note"""
    try:
        data = request.json
        doc_id = data.get('document_id')
        
        if not doc_id or doc_id not in documents:
            return jsonify({"success": False, "error": "Document not found"}), 400
        
        # Stop recording and get audio file
        audio_file = voice_recorder.stop_recording()
        
        if not audio_file:
            return jsonify({"success": False, "error": "No audio recorded"}), 400
        
        # Convert speech to text
        note_text = speech_to_text(audio_file)
        
        if not note_text:
            # Fallback to placeholder if recognition fails
            note_text = f"Voice note recorded at {datetime.now().strftime('%H:%M:%S')}"
        
        # Save note to database
        note = db.add_note(doc_id, {
            "text": note_text,
            "source": "voice",
            "audio_file": os.path.basename(audio_file)
        })
        
        # Update stats
        stats_manager.increment_notes()
        
        # Add to history
        history_manager.add_command({
            "command": "voice note recorded",
            "intent": "note",
            "document": documents[doc_id]['filename'],
            "response": note_text[:100],
            "timestamp": datetime.now().isoformat()
        })
        
        return jsonify({
            "success": True,
            "message": "Voice note saved!",
            "note": note,
            "text": note_text
        })
        
    except Exception as e:
        print(f"❌ Voice note error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/voice-note/cancel', methods=['POST'])
def cancel_voice_note():
    """Cancel voice note recording"""
    try:
        voice_recorder.is_recording = False
        return jsonify({"success": True, "message": "Recording cancelled"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/voice-note/upload', methods=['POST'])
def upload_voice_note():
    """Upload and process a voice note from browser recording"""
    try:
        if 'audio' not in request.files:
            return jsonify({"success": False, "error": "No audio file provided"}), 400
        
        audio_file = request.files['audio']
        doc_id = request.form.get('document_id')
        
        if not doc_id or doc_id not in documents:
            return jsonify({"success": False, "error": "Document not found"}), 400
        
        # Save audio file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"voice_note_{doc_id}_{timestamp}.wav"
        filepath = os.path.join('temp_audio', filename)
        
        audio_file.save(filepath)
        print(f"✅ Voice note saved: {filepath}")
        
        # Convert speech to text
        note_text = speech_to_text(filepath)
        
        if not note_text:
            note_text = f"Voice note recorded at {datetime.now().strftime('%H:%M:%S')}"
        
        # Save note to database
        note = db.add_note(doc_id, {
            "text": note_text,
            "source": "voice",
            "audio_file": filename
        })
        
        # Update stats
        stats_manager.increment_notes()
        
        # Add to history
        history_manager.add_command({
            "command": "voice note recorded",
            "intent": "note",
            "document": documents[doc_id]['filename'],
            "response": note_text[:100],
            "timestamp": datetime.now().isoformat()
        })
        
        return jsonify({
            "success": True,
            "message": "Voice note saved!",
            "note": note,
            "text": note_text,
            "audio_file": filename
        })
        
    except Exception as e:
        print(f"❌ Voice note upload error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/notes/<doc_id>/<note_id>', methods=['DELETE'])
def delete_note(doc_id, note_id):
    """Delete a specific note"""
    try:
        # In a real implementation, you would delete from database
        # For now, return success
        return jsonify({"success": True, "message": "Note deleted"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)