"""
settings.py — persistent settings backed by JSON
"""
import json
import os
import logging
from config import SETTINGS_FILE

logger = logging.getLogger(__name__)


_defaults = {
    "skyscraper_bin": "",
    "screenscraper_user": "",
    "screenscraper_pass": "",
    "last_gamelist_dir": "",
    "theme": "dark",
    "image_preview_size": 220,
    "debug_logging": False,
    "recent_files": [],
    "columns_visible": {
        "name": True,
        "genre": True,
        "developer": True,
        "releasedate": True,
        "rating": True,
        "players": True,
        "hidden": True,
        "favorite": True,
        "kidgame": False,
        "playcount": False,
    },
}


class Settings:
    def __init__(self):
        self._data = dict(_defaults)
        self.load()

    def load(self):
        logger.info(f"Loading settings from {SETTINGS_FILE}")
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                # Merge — keep defaults for missing keys
                for k, v in stored.items():
                    if k in self._data and isinstance(self._data[k], dict) and isinstance(v, dict):
                        self._data[k].update(v)
                    else:
                        self._data[k] = v
                logger.info("Settings loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load settings: {e}")
        else:
            logger.info("Settings file does not exist, using defaults")

    def save(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            logger.info("Settings saved successfully")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def get(self, key, fallback=None):
        return self._data.get(key, fallback)

    def set(self, key, value):
        logger.info(f"Setting {key} = {value}")
        self._data[key] = value
        self.save()

    def add_recent(self, path: str):
        logger.info(f"Adding recent file: {path}")
        recents = self._data.get("recent_files", [])
        if path in recents:
            recents.remove(path)
        recents.insert(0, path)
        self._data["recent_files"] = recents[:10]
        self.save()


# Module-level singleton
settings = Settings()
