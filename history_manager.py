# backend/history_manager.py

import json
import os
from datetime import datetime
from collections import defaultdict

class HistoryManager:
    def __init__(self, history_dir='history_data'):
        self.history_dir = history_dir
        os.makedirs(history_dir, exist_ok=True)
        
        self.documents_file = os.path.join(history_dir, 'documents.json')
        self.commands_file = os.path.join(history_dir, 'commands.json')
        self.history_file = os.path.join(history_dir, 'full_history.json')
        
        self.documents = self._load(self.documents_file, [])
        self.commands = self._load(self.commands_file, [])
        self.full_history = self._load(self.history_file, [])
        
        print(f"📜 History Manager ready - {len(self.documents)} documents in history")
    
    def _load(self, filepath, default):
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading {filepath}: {e}")
        return default
    
    def _save(self, filepath, data):
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Error saving {filepath}: {e}")
    
    def add_document(self, doc_data):
        """Add document to history"""
        entry = {
            "type": "document",
            "id": doc_data.get("id"),
            "filename": doc_data.get("filename"),
            "source_type": doc_data.get("type", "file"),
            "sections": doc_data.get("sections", 0),
            "words": doc_data.get("words", 0),
            "timestamp": doc_data.get("timestamp", datetime.now().isoformat())
        }
        
        # Check if document already exists (update instead of duplicate)
        existing = False
        for i, doc in enumerate(self.documents):
            if doc.get('id') == entry['id']:
                self.documents[i] = entry
                existing = True
                break
        
        if not existing:
            self.documents.append(entry)
        
        self.full_history.append(entry)
        
        # Keep only last 200 entries
        if len(self.documents) > 200:
            self.documents = self.documents[-200:]
        if len(self.full_history) > 1000:
            self.full_history = self.full_history[-1000:]
        
        self._save(self.documents_file, self.documents)
        self._save(self.history_file, self.full_history)
        
        print(f"✅ Document added to history: {entry['filename']}")
        return entry
    
    def add_command(self, cmd_data):
        """Add command to history"""
        entry = {
            "type": "command",
            "command": cmd_data.get("command"),
            "intent": cmd_data.get("intent"),
            "document": cmd_data.get("document"),
            "response": cmd_data.get("response"),
            "timestamp": cmd_data.get("timestamp", datetime.now().isoformat())
        }
        
        self.commands.append(entry)
        self.full_history.append(entry)
        
        # Keep only last 500 commands
        if len(self.commands) > 500:
            self.commands = self.commands[-500:]
        if len(self.full_history) > 1000:
            self.full_history = self.full_history[-1000:]
        
        self._save(self.commands_file, self.commands)
        self._save(self.history_file, self.full_history)
        
        return entry
    
    def get_documents(self, limit=100):
        """Get document history (most recent first)"""
        return list(reversed(self.documents))[:limit]
    
    def get_commands(self, limit=200):
        """Get command history (most recent first)"""
        return list(reversed(self.commands))[:limit]
    
    def get_all_history(self, limit=500):
        """Get all history entries (most recent first)"""
        return list(reversed(self.full_history))[:limit]
    
    def clear_history(self):
        """Clear all history"""
        self.documents = []
        self.commands = []
        self.full_history = []
        
        self._save(self.documents_file, self.documents)
        self._save(self.commands_file, self.commands)
        self._save(self.history_file, self.full_history)
        
        print("🗑️ History cleared")