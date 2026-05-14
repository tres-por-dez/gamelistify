"""
config.py — constants, defaults, known media subfolder names
"""
import os
import sys

APP_NAME = "GameList Editor"
APP_VERSION = "1.0.0"
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".gamelist_editor_settings.json")

# Known ROM extensions per system (extensible)
ROM_EXTENSIONS = {
    "default": [".zip", ".7z", ".chd", ".cue", ".iso", ".img", ".bin",
                ".rom", ".n64", ".z64", ".v64", ".nes", ".sfc", ".smc",
                ".gba", ".gbc", ".gb", ".nds", ".pce", ".md", ".gen",
                ".32x", ".gg", ".sms", ".col", ".a26", ".a78", ".lnx",
                ".ngp", ".ngc", ".ws", ".wsc", ".psx", ".pbp"],
}

# Media subfolder names that EmulationStation / RetroBat use
MEDIA_SUBFOLDERS = [
    "images", "videos", "marquees", "wheels", "fanart",
    "screenshots", "boxart", "box2dfront", "box2dback",
    "box3d", "support", "steam", "snap", "titles",
    "media/images", "media/videos", "media/marquees",
    "media/wheels", "media/fanart", "media/screenshots",
    "media/boxart", "media/box2dfront",
]

# gamelist.xml fields we expose in the editor
GAME_FIELDS = [
    "path", "name", "desc", "rating", "releasedate",
    "developer", "publisher", "genre", "players",
    "image", "video", "marquee", "wheel", "fanart",
    "thumbnail", "screenshot",
    "hidden", "kidgame", "favorite",
    "playcount", "lastplayed",
    "hash", "genreid",
]

# Fields that are boolean flags
BOOL_FIELDS = {"hidden", "kidgame", "favorite"}

# Fields that are file paths (images/video)
MEDIA_FIELDS = {"image", "video", "marquee", "wheel", "fanart", "thumbnail", "screenshot"}

# Skyscraper default binary locations to search
SKYSCRAPER_CANDIDATES = [
    "Skyscraper",
    "skyscraper",
    os.path.join(os.path.expanduser("~"), "Skyscraper", "Skyscraper"),
    "/usr/local/bin/Skyscraper",
    "/usr/bin/Skyscraper",
]

SCRAPER_PLATFORMS = [
    "amiga", "amstradcpc", "arcade", "atari2600", "atari5200", "atari7800",
    "atarilynx", "atarist", "c64", "colecovision", "dreamcast", "fba",
    "fds", "gameandwatch", "gamegear", "gb", "gba", "gbc", "genesis",
    "intellivision", "mame-libretro", "mastersystem", "megadrive", "msx",
    "n64", "nds", "neogeo", "nes", "ngp", "ngpc", "pcengine", "pcfx",
    "ps2", "psp", "psx", "saturn", "scummvm", "sega32x", "segacd",
    "sg-1000", "snes", "vectrex", "virtualboy", "wii", "wonderswan",
    "wonderswancolor", "x68000", "zxspectrum",
]
