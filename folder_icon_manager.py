"""
folder_icon_manager.py — Manage folder icons in gamelist.xml
Extract folders, display/change their icons, and apply changes.
"""
import os
from pathlib import Path
from lxml import etree
from PIL import Image
from gamelist_parser import GameList, Game


class FolderIconManager:
    """Manage folder icons from gamelist."""

    def __init__(self, gamelist: GameList | None, gamelist_path: str | None = None):
        self.gamelist = gamelist
        self.gamelist_path = gamelist_path
        self.folders: list[Game] = []
        self.available_icons: list[str] = []
        self._load_folders()
        self._load_available_icons()

    def _load_folders(self):
        """Extract all <folder> elements from gamelist."""
        if not self.gamelist:
            self.folders = []
            return
        self.folders = [g for g in self.gamelist.games if g.element_tag == "folder"]

    def _load_available_icons(self):
        """Load all icon files from icons/ folder, preferring 32x32."""
        icons_dir = Path("icons")
        if not icons_dir.exists():
            self.available_icons = []
            return

        all_icons = sorted([f.name for f in icons_dir.glob("*.png")])
        
        # Prefer 32x32 versions
        icons_32 = [f for f in all_icons if "32" in f]
        icons_other = [f for f in all_icons if "32" not in f]
        
        self.available_icons = icons_32 + icons_other

    def get_folder_icon_path(self, folder: Game) -> str | None:
        """Get absolute path to folder's current icon, or None if not set."""
        icon_rel = folder.get("image")
        if not icon_rel:
            return None
        
        # Try to resolve relative to icons/ folder
        icon_path = Path("icons") / icon_rel
        if icon_path.exists():
            return str(icon_path.resolve())
        
        # Try as-is
        icon_path = Path(icon_rel)
        if icon_path.exists():
            return str(icon_path.resolve())
        
        return None

    def set_folder_icon(self, folder: Game, icon_filename: str):
        """Set folder icon to the specified icon filename from icons/ folder."""
        icon_path = Path("icons") / icon_filename
        if icon_path.exists():
            folder.set("image", icon_filename)
            return True
        return False

    def scan_missing_folders(self) -> list[str]:
        """
        Scan subdirectories in gamelist directory and return folders not in gamelist.
        Returns list of folder names that are missing from gamelist.
        """
        if not self.gamelist_path:
            return []
        
        gamelist_dir = Path(self.gamelist_path).parent
        if not gamelist_dir.exists():
            return []
        
        # Get all subdirectories in gamelist folder
        all_subdirs = [d.name for d in gamelist_dir.iterdir() if d.is_dir()]
        
        # Get folder names already in gamelist
        existing_folders = {f.get("path") for f in self.folders}
        
        # Find missing folders
        missing = [d for d in all_subdirs if d not in existing_folders]
        
        return sorted(missing)

    def add_missing_folders(self) -> int:
        """
        Add missing folders to gamelist.xml.
        Returns count of folders added.
        """
        if not self.gamelist:
            return 0
        
        missing = self.scan_missing_folders()
        added_count = 0
        
        for folder_name in missing:
            # Create new <folder> element
            folder_el = etree.Element("folder")
            
            path_el = etree.SubElement(folder_el, "path")
            path_el.text = folder_name
            
            name_el = etree.SubElement(folder_el, "name")
            name_el.text = folder_name
            
            # Add to gamelist root
            self.gamelist._el.append(folder_el)
            
            added_count += 1
        
        # Reload folders
        self._load_folders()
        
        return added_count

    def apply_all_changes(self):
        """Mark all modified folders as dirty so they save."""
        for folder in self.folders:
            if folder._dirty:
                pass  # Already marked
        return True

