"""
Simple settings storage utility for AI features
Replace OpenShot's SettingStore with this lightweight version
"""

import json
import os
from pathlib import Path


class SimpleSettings:
    """Simple key-value settings store with JSON persistence"""
    
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = Path.home() / ".ai_app" / "settings.json"
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._data = {}
        self.load()
    
    def load(self):
        """Load settings from disk"""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}
        else:
            self._data = {}
    
    def save(self):
        """Save settings to disk"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            print(f"Failed to save settings: {e}")
    
    def get(self, key, default=None):
        """Get a setting value"""
        return self._data.get(key, default)
    
    def set(self, key, value):
        """Set a setting value"""
        self._data[key] = value
        self.save()
    
    def has(self, key):
        """Check if a setting exists"""
        return key in self._data


class CharacterStorage:
    """Simple character data storage"""
    
    def __init__(self, storage_path=None):
        if storage_path is None:
            storage_path = Path.home() / ".ai_app" / "characters.json"
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._characters = []
        self.load()
    
    def load(self):
        """Load characters from disk"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    self._characters = json.load(f)
            except Exception:
                self._characters = []
        else:
            self._characters = []
    
    def save(self):
        """Save characters to disk"""
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self._characters, f, indent=2)
        except Exception as e:
            print(f"Failed to save characters: {e}")
    
    def get_all(self):
        """Get all characters"""
        return self._characters
    
    def add(self, character):
        """Add a character"""
        self._characters.append(character)
        self.save()
    
    def update(self, index, character):
        """Update a character by index"""
        if 0 <= index < len(self._characters):
            self._characters[index] = character
            self.save()
    
    def delete(self, index):
        """Delete a character by index"""
        if 0 <= index < len(self._characters):
            del self._characters[index]
            self.save()

