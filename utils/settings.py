import json
import os


class Settings:
    """Application settings manager."""

    DEFAULT_SETTINGS = {
        "threading_enabled": True,
        "thread_count": 8,
        "min_inliers": 6,
        "match_threshold": 10,
        "cache_duration_minutes": 15,
        "update_interval_cells": 3,  # Update overlay every N cells
        "orb_features": 6000,  # More features for better accuracy
        "ratio_test": 0.75,  # Tighter matching
        "early_stop_threshold": 75,  # Confidence % to stop early (0-100 scale)
        "min_cache_confidence": 60,  # Min confidence % to trust cached results
        "language": "en"  # Language for location names (en, zh, etc.)
    }

    def __init__(self, settings_file="settings.json"):
        self.settings_file = settings_file
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.load()

    def load(self):
        """Load settings from file."""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    loaded = json.load(f)
                    self.settings.update(loaded)
            except:
                pass

    def save(self):
        """Save settings to file."""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except:
            pass

    def get(self, key, default=None):
        """Get a setting value."""
        return self.settings.get(key, default)

    def set(self, key, value):
        """Set a setting value."""
        self.settings[key] = value
        self.save()

    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.save()


# Global settings instance
_settings = None


def get_settings():
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
