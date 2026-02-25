# backend/stats_manager.py - FULL PER-USER ISOLATION - Python 3.8+ compatible
import json
import os
from datetime import datetime, date
from typing import Optional


def _today():
    # type: () -> str
    return date.today().isoformat()


class StatsManager:
    def __init__(self, history_folder='history_data'):
        self.history_folder = history_folder
        os.makedirs(history_folder, exist_ok=True)

        self.stats_file = os.path.join(history_folder, 'stats.json')
        self._stats     = self._load_file(self.stats_file, self._default_stats())
        print("StatsManager ready")

    # ── Defaults ─────────────────────────────────────────────────────────────

    @staticmethod
    def _default_stats():
        return {
            'total_documents': 0,
            'total_commands':  0,
            'total_notes':     0,
            'total_bookmarks': 0,
            'total_quizzes':   0,
            'total_exports':   0,
            'daily_stats':     {}
        }

    # ── File helpers ─────────────────────────────────────────────────────────

    def _load_file(self, filepath, default):
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print("Error loading {}: {}".format(filepath, e))
        return default

    def _save_file(self, filepath, data):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print("Error saving {}: {}".format(filepath, e))

    # ── Per-user paths ────────────────────────────────────────────────────────

    def _user_dir(self, user_id):
        # type: (str) -> str
        path = os.path.join(self.history_folder, 'users', str(user_id))
        os.makedirs(path, exist_ok=True)
        return path

    def _user_stats_file(self, user_id):
        # type: (str) -> str
        return os.path.join(self._user_dir(user_id), 'stats.json')

    def _load_user_stats(self, user_id):
        # type: (str) -> dict
        return self._load_file(self._user_stats_file(user_id), self._default_stats())

    def _save_user_stats(self, user_id, stats):
        self._save_file(self._user_stats_file(user_id), stats)

    # ── Internal get/save ────────────────────────────────────────────────────

    def _get(self, user_id=None):
        if user_id:
            return self._load_user_stats(user_id)
        return self._stats

    def _save(self, user_id=None, stats=None):
        if user_id:
            if stats is None:
                stats = self._load_user_stats(user_id)
            self._save_user_stats(user_id, stats)
        else:
            if stats is not None:
                self._stats = stats
            self._save_file(self.stats_file, self._stats)

    def _ensure_daily(self, stats, today):
        stats.setdefault('daily_stats', {})
        stats['daily_stats'].setdefault(today, {
            'documents': 0, 'commands': 0, 'notes': 0,
            'bookmarks': 0, 'quizzes': 0, 'exports': 0
        })

    # ── Public getters/setters ────────────────────────────────────────────────

    def get_stats(self, user_id=None):
        return self._get(user_id)

    def increment_documents(self, user_id=None):
        today = _today()
        stats = self._get(user_id)
        stats['total_documents'] = stats.get('total_documents', 0) + 1
        self._ensure_daily(stats, today)
        stats['daily_stats'][today]['documents'] += 1
        self._save(user_id, stats)

    def increment_commands(self, user_id=None):
        today = _today()
        stats = self._get(user_id)
        stats['total_commands'] = stats.get('total_commands', 0) + 1
        self._ensure_daily(stats, today)
        stats['daily_stats'][today]['commands'] += 1
        self._save(user_id, stats)

    def increment_notes(self, user_id=None):
        today = _today()
        stats = self._get(user_id)
        stats['total_notes'] = stats.get('total_notes', 0) + 1
        self._ensure_daily(stats, today)
        stats['daily_stats'][today]['notes'] += 1
        self._save(user_id, stats)

    def increment_bookmarks(self, user_id=None):
        today = _today()
        stats = self._get(user_id)
        stats['total_bookmarks'] = stats.get('total_bookmarks', 0) + 1
        self._ensure_daily(stats, today)
        stats['daily_stats'][today]['bookmarks'] += 1
        self._save(user_id, stats)

    def increment_quizzes(self, user_id=None):
        today = _today()
        stats = self._get(user_id)
        stats['total_quizzes'] = stats.get('total_quizzes', 0) + 1
        self._ensure_daily(stats, today)
        stats['daily_stats'][today]['quizzes'] += 1
        self._save(user_id, stats)

    def increment_exports(self, user_id=None):
        today = _today()
        stats = self._get(user_id)
        stats['total_exports'] = stats.get('total_exports', 0) + 1
        self._ensure_daily(stats, today)
        stats['daily_stats'][today]['exports'] += 1
        self._save(user_id, stats)

    def reset_stats(self, user_id=None):
        fresh = self._default_stats()
        if user_id:
            self._save_user_stats(user_id, fresh)
            print("Stats reset for user {}".format(user_id))
        else:
            self._stats = fresh
            self._save_file(self.stats_file, fresh)
            print("Global stats reset")