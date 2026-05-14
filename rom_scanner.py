"""
rom_scanner.py — scan a directory for ROM files and return entries
not yet present in a GameList.
"""
import os
from config import ROM_EXTENSIONS


def scan_roms(directory: str, extensions: list[str] | None = None) -> list[dict]:
    """
    Walk directory recursively and return a list of dicts with minimal
    game fields for ROMs found.
    """
    if extensions is None:
        extensions = ROM_EXTENSIONS["default"]
    ext_set = {e.lower() for e in extensions}

    results = []
    for root, dirs, files in os.walk(directory):
        # Skip hidden dirs and known media folders
        dirs[:] = [d for d in dirs if not d.startswith(".") and d.lower() not in (
            "images", "videos", "marquees", "wheels", "fanart",
            "screenshots", "boxart", "media", "snap", "titles",
        )]
        for fname in sorted(files):
            _, ext = os.path.splitext(fname)
            if ext.lower() in ext_set:
                abs_path = os.path.join(root, fname)
                rel_path = os.path.relpath(abs_path, directory)
                # ES uses ./ prefix
                es_path = "./" + rel_path.replace(os.sep, "/")
                stem = os.path.splitext(fname)[0]
                results.append({
                    "path": es_path,
                    "name": stem,
                    "_abs": abs_path,
                })
    return results


def diff_against_gamelist(scanned: list[dict], gamelist) -> list[dict]:
    """Return scanned entries whose path is NOT already in gamelist."""
    existing_paths = {g.path for g in gamelist.games}
    return [r for r in scanned if r["path"] not in existing_paths]
