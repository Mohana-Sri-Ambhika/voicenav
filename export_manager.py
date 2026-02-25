# backend/export_manager.py - CREATES PROPER .txt FILES
import os
from datetime import datetime

class ExportManager:
    def __init__(self, export_dir='exports'):
        self.export_dir = export_dir
        os.makedirs(export_dir, exist_ok=True)
        print("📤 Export Manager ready")
    
    def export_document_data(self, doc_id, database, filename):
        """Export notes and bookmarks as .txt file"""
        notes = database.get_notes(doc_id)
        bookmarks = database.get_bookmarks(doc_id)
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Clean filename for safe use
        safe_filename = ''.join(c for c in filename if c.isalnum() or c in ' ._-')[:30]
        export_file = f"VoiceNav_{safe_filename}_{timestamp}.txt"
        export_path = os.path.join(self.export_dir, export_file)
        
        # Build content with proper formatting
        lines = []
        lines.append("="*70)
        lines.append("🎤 VOICENAV AI - NOTES & BOOKMARKS EXPORT")
        lines.append("="*70)
        lines.append(f"Document: {filename}")
        lines.append(f"Document ID: {doc_id}")
        lines.append(f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("="*70)
        
        # NOTES SECTION
        lines.append("\n📝 NOTES:")
        lines.append("-" * 40)
        if notes and len(notes) > 0:
            for i, note in enumerate(notes, 1):
                ts = note.get('timestamp', '')
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts)
                        ts_str = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        ts_str = ts[:16]
                else:
                    ts_str = 'Unknown date'
                
                text = note.get('text', '')
                source = note.get('source', 'text')
                
                # Add source indicator
                if source == 'voice':
                    source_icon = '🎤'
                    source_label = 'VOICE NOTE'
                else:
                    source_icon = '📝'
                    source_label = 'TEXT NOTE'
                
                lines.append(f"\n  {i}. {source_icon} [{source_label}] {text}")
                lines.append(f"     Saved: {ts_str}")
                
                # Add audio file info if available
                if note.get('audio_file'):
                    lines.append(f"     Audio file: {note.get('audio_file')}")
        else:
            lines.append("\n  No notes saved")
        
        # BOOKMARKS SECTION
        lines.append("\n\n🔖 BOOKMARKS:")
        lines.append("-" * 40)
        if bookmarks and len(bookmarks) > 0:
            for i, bm in enumerate(bookmarks, 1):
                ts = bm.get('timestamp', '')
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts)
                        ts_str = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        ts_str = ts[:16]
                else:
                    ts_str = 'Unknown date'
                
                section = bm.get('section', 'Unknown section')
                lines.append(f"\n  {i}. 🔖 {section}")
                lines.append(f"     Saved: {ts_str}")
        else:
            lines.append("\n  No bookmarks saved")
        
        # SUMMARY
        lines.append("\n\n" + "="*70)
        lines.append(f"📊 SUMMARY:")
        lines.append(f"   Total Notes: {len(notes)}")
        
        # Count voice notes
        voice_notes = sum(1 for note in notes if note.get('source') == 'voice')
        text_notes = len(notes) - voice_notes
        lines.append(f"   ├─ Voice Notes: {voice_notes} 🎤")
        lines.append(f"   └─ Text Notes: {text_notes} 📝")
        
        lines.append(f"   Total Bookmarks: {len(bookmarks)}")
        lines.append("="*70)
        
        # Write file with UTF-8 encoding
        with open(export_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        print(f"✅ Exported: {export_file}")
        return export_path