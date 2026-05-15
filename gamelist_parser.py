"""
gamelist_parser.py — parse and write gamelist.xml using lxml.
Preserves comments and attribute order. Thread-safe read; writes go through
save() which keeps a .bak backup.
"""
import os
import shutil
import logging
from copy import deepcopy
from lxml import etree
from config import GAME_FIELDS, BOOL_FIELDS
from datetime import datetime
import io

logger = logging.getLogger(__name__)


class Game:
    """Mutable in-memory representation of a <game> or <folder> element."""

    __slots__ = ["_el", "_dirty", "element_tag"]

    def __init__(self, element: etree._Element):
        self._el = element
        self._dirty = False
        self.element_tag = element.tag  # 'game' or 'folder'

    # ── field access ────────────────────────────────────────────────────────

    def get(self, field: str, default="") -> str:
        child = self._el.find(field)
        if child is None:
            return default
        return (child.text or "").strip()

    def set(self, field: str, value: str):
        child = self._el.find(field)
        if child is None:
            child = etree.SubElement(self._el, field)
        new_val = str(value).strip()
        if child.text != new_val:
            old_val = child.text
            child.text = new_val
            self._dirty = True
            logger.debug(f"Game field changed: {field} from {old_val!r} to {new_val!r} for {self.name}")

    def delete_field(self, field: str):
        child = self._el.find(field)
        if child is not None:
            self._el.remove(child)
            self._dirty = True

    # ── convenience props ────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self.get("name") or self.get("path")

    @property
    def path(self) -> str:
        return self.get("path")

    @property
    def hidden(self) -> bool:
        return self.get("hidden", "false").lower() in ("true", "1", "yes")

    @hidden.setter
    def hidden(self, val: bool):
        self.set("hidden", "true" if val else "false")

    @property
    def favorite(self) -> bool:
        return self.get("favorite", "false").lower() in ("true", "1", "yes")

    @favorite.setter
    def favorite(self, val: bool):
        self.set("favorite", "true" if val else "false")

    @property
    def kidgame(self) -> bool:
        return self.get("kidgame", "false").lower() in ("true", "1", "yes")

    @kidgame.setter
    def kidgame(self, val: bool):
        self.set("kidgame", "true" if val else "false")

    def as_dict(self) -> dict:
        return {f: self.get(f) for f in GAME_FIELDS}

    def __repr__(self):
        return f"<Game path={self.path!r} name={self.name!r}>"


class GameList:
    """Parsed gamelist.xml with O(1) lookup by path."""

    def __init__(self, xml_path: str):
        self.xml_path = xml_path
        self.base_dir = os.path.dirname(xml_path)
        self._tree: etree._ElementTree | None = None
        self._root: etree._Element | None = None
        self.games: list[Game] = []
        self._path_index: dict[str, Game] = {}
        self._loaded = False
        self._dirty = False
        logger.info(f"Initialized GameList for {xml_path}")

    def load(self):
        logger.info(f"Loading gamelist from {self.xml_path}")
        parser = etree.XMLParser(remove_blank_text=False, recover=True)
        self._tree = etree.parse(self.xml_path, parser)
        self._root = self._tree.getroot()
        self.games = []
        self._path_index = {}
        game_count = 0
        folder_count = 0
        for el in self._root:
            if el.tag in ("game", "folder"):
                g = Game(el)
                self.games.append(g)
                self._path_index[g.path] = g
                if el.tag == "game":
                    game_count += 1
                else:
                    folder_count += 1
        self._loaded = True
        logger.info(f"Loaded {game_count} games and {folder_count} folders from {self.xml_path}")

    def reload(self):
        self.load()

    def has_unsaved_changes(self) -> bool:
        if self._dirty:
            return True
        return any(getattr(g, '_dirty', False) for g in self.games)

    def mark_saved(self):
        self._dirty = False
        for g in self.games:
            if hasattr(g, '_dirty'):
                g._dirty = False

    # ── mutations ────────────────────────────────────────────────────────────

    def add_game(self, fields: dict) -> Game:
        """Insert a new <game> element and return the Game wrapper."""
        el = etree.SubElement(self._root, "game")
        g = Game(el)
        for k, v in fields.items():
            if v:
                g.set(k, v)
        self.games.append(g)
        self._path_index[g.path] = g
        self._dirty = True
        logger.info(f"Added new game: {g.name} ({g.path})")
        return g

    def add_folder(self, fields: dict) -> Game:
        el = etree.SubElement(self._root, "folder")
        g = Game(el)
        for k, v in fields.items():
            if v:
                g.set(k, v)
        self.games.append(g)
        self._path_index[g.path] = g
        self._dirty = True
        logger.info(f"Added new folder: {g.name} ({g.path})")
        return g

    def remove_game(self, game: Game):
        self._root.remove(game._el)
        if game in self.games:
            self.games.remove(game)
        self._path_index.pop(game.path, None)
        self._dirty = True

    def remove_games(self, game_list: list):
        for g in game_list:
            self.remove_game(g)

    def get_by_path(self, path: str) -> "Game | None":
        return self._path_index.get(path)

    # ── save ─────────────────────────────────────────────────────────────────

    def save(self, backup=True):
        logger.debug(f"Saving gamelist.xml to {self.xml_path} (backup={backup})")
        # Prepare new content in-memory for comparison
        etree.indent(self._root, space="  ")
        buf = io.BytesIO()
        self._tree.write(buf, pretty_print=True, xml_declaration=True, encoding="UTF-8")
        new_bytes = buf.getvalue()

        # If backup requested and an existing file exists, create an incremental
        # timestamped backup only if the file content actually changed.
        if backup and os.path.exists(self.xml_path):
            try:
                with open(self.xml_path, "rb") as f:
                    old_bytes = f.read()
            except Exception:
                old_bytes = None

            if old_bytes != new_bytes:
                # safe ISO-like timestamp for filenames (colon is invalid on Windows)
                ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S.%f")[:-3]
                base = os.path.basename(self.xml_path)
                dirn = os.path.dirname(self.xml_path)
                if base.lower().endswith(".xml"):
                    stem = base[:-4]
                    bak_name = f"{stem}.{ts}.xml.bak"
                else:
                    bak_name = f"{base}.{ts}.bak"
                bak_path = os.path.join(dirn, bak_name)
                shutil.copy2(self.xml_path, bak_path)
                logger.debug(f"Created backup file: {bak_path}")
            else:
                logger.debug("No changes detected; backup skipped")

        # Finally write the new content to disk
        with open(self.xml_path, "wb") as out:
            out.write(new_bytes)
        self.mark_saved()

    def save_as(self, path: str):
        etree.indent(self._root, space="  ")
        self._tree.write(
            path,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
        )
        self.mark_saved()

    # ── media resolution ──────────────────────────────────────────────────────

    def resolve_media_path(self, raw_path: str) -> str | None:
        """
        Resolve a path that may be:
          - absolute
          - relative to base_dir
          - EmulationStation ~/ syntax (relative to gamelist dir)
        Returns absolute path if file exists, else None.
        """
        if not raw_path:
            return None
        p = raw_path.replace("~/", "").lstrip("/\\")
        candidates = [
            raw_path,
            os.path.join(self.base_dir, p),
            os.path.join(self.base_dir, raw_path.lstrip("./")),
        ]
        for c in candidates:
            if os.path.isfile(c):
                return c
        return None

    def find_orphan_media(self, game: Game) -> dict:
        """
        Scan known media subfolders for files matching the ROM stem.
        Returns dict of media_type -> abs_path for files NOT already in gamelist.
        """
        from config import MEDIA_SUBFOLDERS
        stem = os.path.splitext(os.path.basename(game.path))[0]
        found = {}
        for sub in MEDIA_SUBFOLDERS:
            folder = os.path.join(self.base_dir, sub)
            if not os.path.isdir(folder):
                continue
            for fname in os.listdir(folder):
                fbase, fext = os.path.splitext(fname)
                if fbase.lower() == stem.lower() and fext.lower() in (
                    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".avi"
                ):
                    mtype = sub.split("/")[-1].rstrip("s")  # rough guess
                    found[f"{sub}/{fname}"] = os.path.join(folder, fname)
        return found

    @property
    def is_loaded(self):
        return self._loaded

    def __len__(self):
        return len(self.games)
