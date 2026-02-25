# backend/stats_manager.py

import json
import os
from datetime import datetime, timedelta

class StatsManager:
    def __init__(self, history_dir='history_data'):
        self.history_dir = history_dir
        self.stats_file = os.path.join(history_dir, 'stats.json')
        self.stats = self._load_defaults()
        print(f"📊 Stats Manager ready - Total Docs: {self.stats['total_documents']}")
    
    def _load_defaults(self):
        """Load stats or create defaults"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    stats = json.load(f)
                    
                    # Ensure all required fields exist with proper defaults
                    required_fields = {
                        "total_documents": 0,
                        "total_commands": 0,
                        "total_notes": 0,
                        "total_bookmarks": 0,
                        "total_quizzes": 0,
                        "total_exports": 0,
                        "daily_stats": {},
                        "last_updated": datetime.now().isoformat()
                    }
                    
                    for field, default_value in required_fields.items():
                        if field not in stats:
                            if field == "daily_stats":
                                stats[field] = {}
                            else:
                                stats[field] = default_value
                    
                    return stats
            else:
                # Create new stats file with initial data
                stats = {
                    "total_documents": 0,
                    "total_commands": 0,
                    "total_notes": 0,
                    "total_bookmarks": 0,
                    "total_quizzes": 0,
                    "total_exports": 0,
                    "daily_stats": {},
                    "last_updated": datetime.now().isoformat()
                }
                # Save immediately
                with open(self.stats_file, 'w') as f:
                    json.dump(stats, f, indent=2)
                return stats
                
        except Exception as e:
            print(f"⚠️ Error loading stats: {e}")
            return {
                "total_documents": 0,
                "total_commands": 0,
                "total_notes": 0,
                "total_bookmarks": 0,
                "total_quizzes": 0,
                "total_exports": 0,
                "daily_stats": {},
                "last_updated": datetime.now().isoformat()
            }
    
    def _save(self):
        """Save stats to file"""
        try:
            # Ensure we're not overwriting with zeros
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving stats: {e}")
    
    def _update_daily(self, key):
        """Update daily stats"""
        today = datetime.now().strftime('%Y-%m-%d')
        if today not in self.stats["daily_stats"]:
            self.stats["daily_stats"][today] = {
                "documents": 0,
                "commands": 0,
                "notes": 0,
                "bookmarks": 0,
                "quizzes": 0,
                "exports": 0
            }
        
        self.stats["daily_stats"][today][key] += 1
        
        # Keep only last 90 days
        dates = sorted(self.stats["daily_stats"].keys())
        if len(dates) > 90:
            for old_date in dates[:-90]:
                del self.stats["daily_stats"][old_date]
    
    def increment_documents(self):
        """Increment document count"""
        self.stats["total_documents"] += 1
        self._update_daily("documents")
        self.stats["last_updated"] = datetime.now().isoformat()
        self._save()
        print(f"📊 Stats updated: total_documents = {self.stats['total_documents']}")
    
    def increment_commands(self):
        """Increment command count"""
        self.stats["total_commands"] += 1
        self._update_daily("commands")
        self.stats["last_updated"] = datetime.now().isoformat()
        self._save()
    
    def increment_notes(self):
        """Increment notes count"""
        self.stats["total_notes"] += 1
        self._update_daily("notes")
        self.stats["last_updated"] = datetime.now().isoformat()
        self._save()
    
    def increment_bookmarks(self):
        """Increment bookmarks count"""
        self.stats["total_bookmarks"] += 1
        self._update_daily("bookmarks")
        self.stats["last_updated"] = datetime.now().isoformat()
        self._save()
    
    def increment_quizzes(self):
        """Increment quizzes count"""
        self.stats["total_quizzes"] += 1
        self._update_daily("quizzes")
        self.stats["last_updated"] = datetime.now().isoformat()
        self._save()
    
    def increment_exports(self):
        """Increment exports count"""
        self.stats["total_exports"] += 1
        self._update_daily("exports")
        self.stats["last_updated"] = datetime.now().isoformat()
        self._save()
    
    def get_stats(self):
        """Get current stats"""
        return self.stats
    
    def reset_stats(self):
        """Reset all stats"""
        self.stats = {
            "total_documents": 0,
            "total_commands": 0,
            "total_notes": 0,
            "total_bookmarks": 0,
            "total_quizzes": 0,
            "total_exports": 0,
            "daily_stats": {},
            "last_updated": datetime.now().isoformat()
        }
        self._save()