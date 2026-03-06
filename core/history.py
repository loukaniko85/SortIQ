"""
Rename history manager - tracks rename operations for undo/redo
"""

import json
import os
import threading
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class RenameHistory:
    """Manages rename history for undo/redo operations"""

    def __init__(self, history_file: str = None):
        self.history_file = history_file or os.path.join(
            os.path.expanduser("~"), ".sortiq", "history.json"
        )
        self.history: List[Dict] = []
        self.current_index = -1
        self._lock = threading.Lock()
        self._ensure_history_dir()
        self._load_history()
    
    def _ensure_history_dir(self):
        """Ensure history directory exists"""
        history_dir = os.path.dirname(self.history_file)
        os.makedirs(history_dir, exist_ok=True)
    
    def _load_history(self):
        """Load history from file"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    self.history = json.load(f)
                    self.current_index = len(self.history) - 1
            except Exception:
                self.history = []
                self.current_index = -1
    
    def _save_history(self):
        """Save history to file"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            print(f"Error saving history: {e}")
    
    def add_operation(self, original_path: str, new_path: str, match_info: Dict = None):
        """Add a rename operation to history"""
        operation = {
            'timestamp': datetime.now().isoformat(),
            'original_path': original_path,
            'new_path': new_path,
            'match_info': match_info or {}
        }
        with self._lock:
            # Remove any operations after current index (when undoing)
            if self.current_index < len(self.history) - 1:
                self.history = self.history[:self.current_index + 1]

            self.history.append(operation)
            self.current_index = len(self.history) - 1

            # Keep only last 100 operations
            if len(self.history) > 100:
                self.history = self.history[-100:]
                self.current_index = len(self.history) - 1

        self._save_history()

    def can_undo(self) -> bool:
        """Check if undo is possible"""
        with self._lock:
            return self.current_index >= 0

    def can_redo(self) -> bool:
        """Check if redo is possible"""
        with self._lock:
            return self.current_index < len(self.history) - 1

    def undo(self) -> Optional[Dict]:
        """Get the last operation to undo"""
        with self._lock:
            if self.current_index < 0:
                return None
            operation = self.history[self.current_index]
            self.current_index -= 1
        self._save_history()
        return operation

    def redo(self) -> Optional[Dict]:
        """Get the next operation to redo"""
        with self._lock:
            if self.current_index >= len(self.history) - 1:
                return None
            self.current_index += 1
            operation = self.history[self.current_index]
        self._save_history()
        return operation

    def revert_undo(self):
        """Restore index after a failed undo (file missing / move failed).

        Call this instead of directly incrementing current_index so that
        the lock is held and the history file is updated consistently.
        """
        with self._lock:
            self.current_index = min(self.current_index + 1, len(self.history) - 1)
        self._save_history()

    def revert_redo(self):
        """Restore index after a failed redo (source file missing / move failed)."""
        with self._lock:
            self.current_index = max(self.current_index - 1, -1)
        self._save_history()

    def get_last_operations(self, count: int = 10) -> List[Dict]:
        """Get last N operations"""
        with self._lock:
            start = max(0, len(self.history) - count)
            return list(self.history[start:])
