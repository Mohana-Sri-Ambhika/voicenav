# backend/database.py - PROPER NOTE STORAGE
import json
import os
import uuid
from datetime import datetime

class Database:
    def __init__(self, db_path='data'):
        self.db_path = db_path
        os.makedirs(db_path, exist_ok=True)
        
        self.notes_file = os.path.join(db_path, 'notes.json')
        self.bookmarks_file = os.path.join(db_path, 'bookmarks.json')
        self.documents_file = os.path.join(db_path, 'documents.json')
        
        self.notes = self._load(self.notes_file, {})
        self.bookmarks = self._load(self.bookmarks_file, {})
        self.documents = self._load(self.documents_file, {})
        
        print(f"💾 Database ready - {len(self.documents)} docs, {self.get_all_notes_count()} notes, {self.get_all_bookmarks_count()} bookmarks")
    
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
    
    def save_document(self, doc_id, data):
        self.documents[doc_id] = {
            "id": doc_id,
            "filename": data.get('filename'),
            "uploaded_at": data.get('uploaded_at', datetime.now().isoformat())
        }
        self._save(self.documents_file, self.documents)
        return self.documents[doc_id]
    
    def get_document(self, doc_id):
        return self.documents.get(doc_id)
    
    def get_all_documents(self):
        return self.documents
    
    def add_note(self, doc_id, note_data):
        if doc_id not in self.notes:
            self.notes[doc_id] = []
        
        note = {
            'id': str(uuid.uuid4()),
            'text': note_data.get('text', ''),
            'source': note_data.get('source', 'voice'),
            'audio_file': note_data.get('audio_file'),
            'timestamp': datetime.now().isoformat()
        }
        
        self.notes[doc_id].append(note)
        self._save(self.notes_file, self.notes)
        
        # Get document info for logging
        doc_info = self.get_document(doc_id)
        doc_name = doc_info.get('filename', 'Unknown') if doc_info else 'Unknown'
        print(f"✅ Note saved for document {doc_id} ({doc_name}): {note['text'][:50]}...")
        return note
    
    def get_notes(self, doc_id):
        """Get all notes for a document"""
        return self.notes.get(doc_id, [])
    
    def get_all_notes(self):
        """Get all notes from all documents with document info"""
        all_notes = []
        for doc_id, notes in self.notes.items():
            doc_info = self.get_document(doc_id)
            doc_name = doc_info.get('filename', 'Unknown Document') if doc_info else 'Unknown Document'
            
            for note in notes:
                note_copy = note.copy()
                note_copy['document_id'] = doc_id
                note_copy['document_name'] = doc_name
                all_notes.append(note_copy)
        return all_notes
    
    def get_all_notes_count(self):
        return sum(len(notes) for notes in self.notes.values())
    
    def sync_counts(self):
        """Get accurate counts from all collections"""
        return {
            'documents': len(self.documents),
            'notes': self.get_all_notes_count(),
            'bookmarks': self.get_all_bookmarks_count()
        }
    
    def add_bookmark(self, doc_id, bookmark_data):
        if doc_id not in self.bookmarks:
            self.bookmarks[doc_id] = []
        
        bookmark = {
            'id': str(uuid.uuid4()),
            'section': bookmark_data.get('section', 'Current section'),
            'timestamp': datetime.now().isoformat()
        }
        
        self.bookmarks[doc_id].append(bookmark)
        self._save(self.bookmarks_file, self.bookmarks)
        return bookmark
    
    def get_bookmarks(self, doc_id):
        return self.bookmarks.get(doc_id, [])
    
    def get_all_bookmarks_count(self):
        return sum(len(bm) for bm in self.bookmarks.values())