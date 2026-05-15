"""
folder_icon_manager.py — Manage folder icons in gamelist.xml
Extract folders, display/change their icons, and apply changes.
"""
import os
import shutil
import logging
from pathlib import Path
from lxml import etree
from PIL import Image
from gamelist_parser import GameList, Game

logger = logging.getLogger(__name__)


class FolderIconManager:
    """Manage folder icons from gamelist."""

    def __init__(self, gamelist: GameList | None, gamelist_path: str | None = None):
        self.gamelist = gamelist
        self.gamelist_path = gamelist_path
        self.folders: list[Game] = []
        self.available_icons: list[str] = []
        self._load_folders()
        self._load_available_icons()
        logger.info(f"Initialized FolderIconManager with {len(self.folders)} folders and {len(self.available_icons)} available icons")

    def _load_folders(self):
        """Extract all <folder> elements from gamelist."""
        if not self.gamelist:
            self.folders = []
            logger.info("No gamelist provided, folders list is empty")
            return
        self.folders = [g for g in self.gamelist.games if g.element_tag == "folder"]
        logger.info(f"Loaded {len(self.folders)} folders from gamelist")

    def _load_available_icons(self):
        """Load all icon files from icons/ folder, preferring 32x32."""
        icons_dir = Path("icons")
        if not icons_dir.exists():
            self.available_icons = []
            logger.warning("Icons directory does not exist")
            return

        all_icons = sorted([f.name for f in icons_dir.glob("*.png")])
        
        # Prefer 32x32 versions
        icons_32 = [f for f in all_icons if "32" in f]
        icons_other = [f for f in all_icons if "32" not in f]
        
        self.available_icons = icons_32 + icons_other
        logger.info(f"Loaded {len(self.available_icons)} available icons from {icons_dir}")

    def _normalize_folder_name(self, path: str | None) -> str:
        if not path:
            return ""
        normalized = path.strip().replace("\\", "/")
        if normalized.startswith("./"):
            normalized = normalized[2:]
        if normalized.endswith("/"):
            normalized = normalized[:-1]
        return normalized

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

        # Try relative to gamelist base directory
        if self.gamelist and self.gamelist.base_dir:
            icon_path = Path(self.gamelist.base_dir) / icon_rel.lstrip("./")
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

    def copy_image_to_collection(self, src_path: str) -> str | None:
        """Copy a selected image into the gamelist collection and return a relative path."""
        if not self.gamelist:
            logger.error("No gamelist available for copying image")
            return None

        src = Path(src_path)
        if not src.exists():
            logger.error(f"Source image not found: {src_path}")
            return None

        images_dir = Path(self.gamelist.base_dir) / "images" / "misc"
        images_dir.mkdir(parents=True, exist_ok=True)

        dest = images_dir / src.name
        base = src.stem
        ext = src.suffix
        counter = 1
        while dest.exists() and not os.path.samefile(dest, src):
            dest = images_dir / f"{base}_{counter}{ext}"
            counter += 1

        shutil.copy2(src, dest)
        rel_path = "./" + os.path.relpath(dest, self.gamelist.base_dir).replace(os.sep, "/")
        logger.info(f"Copied image to collection: {rel_path}")
        return rel_path

    def scan_missing_folders(self) -> list[str]:
        """
        Scan subdirectories in gamelist directory and return folders not in gamelist.
        Returns list of folder names that are missing from gamelist.
        """
        if not self.gamelist_path:
            logger.warning("No gamelist path provided for scanning missing folders")
            return []
        
        gamelist_dir = Path(self.gamelist_path).parent
        if not gamelist_dir.exists():
            logger.warning(f"Gamelist directory does not exist: {gamelist_dir}")
            return []
        
        # Get all subdirectories in gamelist folder
        all_subdirs = [d.name for d in gamelist_dir.iterdir() if d.is_dir()]
        normalized_subdirs = {self._normalize_folder_name(d) for d in all_subdirs}
        logger.info(f"Found {len(all_subdirs)} subdirectories in {gamelist_dir}: {all_subdirs}")
        
        # Get folder names already in gamelist
        existing_folders = {
            self._normalize_folder_name(f.get("path") or f.name)
            for f in self.folders
        }
        logger.info(f"Existing folders in gamelist: {existing_folders}")
        
        # Find missing folders
        missing = [d for d in all_subdirs if self._normalize_folder_name(d) not in existing_folders]
        logger.info(f"Missing folders: {missing}")
        
        return sorted(missing)

    def add_missing_folders(self, folder_names: list[str]) -> int:
        """
        Add specified folders to gamelist.xml.
        Returns count of folders added.
        """
        if not self.gamelist:
            logger.error("No gamelist available to add folders")
            return 0
        
        logger.info(f"Adding {len(folder_names)} missing folders to gamelist: {folder_names}")
        added_count = 0
        
        for folder_name in folder_names:
            # Use gamelist.add_folder to properly add
            fields = {"path": f"./{folder_name}", "name": folder_name}
            self.gamelist.add_folder(fields)
            logger.info(f"Added folder '{folder_name}' via gamelist.add_folder")
            
            added_count += 1
        
        logger.info(f"Successfully added {added_count} folders to XML tree")
        # Reload folders
        self._load_folders()
        logger.info(f"Reloaded folders list, now has {len(self.folders)} folders")
        
        return added_count

    def apply_all_changes(self):
        """Mark all modified folders as dirty so they save."""
        for folder in self.folders:
            if folder._dirty:
                pass  # Already marked
        return True

