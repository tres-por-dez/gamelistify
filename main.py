"""
main.py — GameList Editor entry point.
CustomTkinter-based desktop application for editing EmulationStation/RetroBat
gamelist.xml files.
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
import customtkinter as ctk
from PIL import Image
from PIL import ImageTk
import logging
import colorama
import threading
import traceback
import webbrowser

from CTkToolTip import CTkToolTip

from settings import settings
from gamelist_parser import GameList, Game
from config import GAME_FIELDS, BOOL_FIELDS, MEDIA_FIELDS, SCRAPER_PLATFORMS
from rom_scanner import scan_roms, diff_against_gamelist
from scraper_bridge import (
    ScraperJob, build_skyscraper_bulk_command,
    build_skyscraper_command, write_skyscraper_credentials, find_skyscraper_bin,
)

def show_toast(root, message, duration=2500):
    toast = ctk.CTkToplevel(root)
    toast.wm_overrideredirect(True)
    toast.attributes("-topmost", True)
    toast.attributes("-alpha", 0.97)

    label = ctk.CTkLabel(
        toast,
        text=message,
        fg_color="#2196F3",
        text_color="white",
        corner_radius=8,
        font=ctk.CTkFont(size=13, weight="bold"),
        padx=18,
        pady=10,
    )
    label.pack()

    # borda via frame externo
    toast.configure(fg_color="#1565C0")  # borda simulada pela cor do toplevel
    label.pack(padx=2, pady=2)

    def _position():
        toast.update_idletasks()
        tw = toast.winfo_width()
        th = toast.winfo_height()
        rx = root.winfo_rootx()
        ry = root.winfo_rooty()
        rw = root.winfo_width()
        rh = root.winfo_height()
        x = rx + rw - tw - 10
        y = ry + rh - th - 10
        toast.wm_geometry(f"+{x}+{y}")

    root.after(10, _position)  # aguarda render pra ter dimensões corretas

    def dismiss():
        threading.Event().wait(duration / 1000)
        try:
            toast.destroy()
        except Exception:
            pass

    threading.Thread(target=dismiss, daemon=True).start()


def show_error_dialog(root, title: str, message: str, details: str | list[str] | None = None):
    try:
        dlg = ctk.CTkToplevel(root)
        dlg.title(title)
        dlg.geometry("900x360")
        dlg.transient(root)
        dlg.grab_set()
        center_window(dlg, root)

        ctk.CTkLabel(dlg, text=message, font=("", 13, "bold"), text_color=COL_HIGHLIGHT).pack(anchor="w", padx=12, pady=(8, 6))

        # Large monospaced textbox for details
        txt = ctk.CTkTextbox(
            dlg,
            height=12,
            wrap="none",
            font=("Courier", 10),
            fg_color=COL_PANEL,
            text_color=COL_TEXT,
        )
        txt.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        txt.configure(state="normal")
        if details:
            if isinstance(details, list):
                txt.insert("1.0", "".join(details))
            else:
                txt.insert("1.0", str(details))
        txt.configure(state="disabled")

        btns = ctk.CTkFrame(dlg)
        btns.pack(fill="x", padx=12, pady=8)

        def do_close():
            try:
                dlg.destroy()
            except Exception:
                pass

        def do_restart():
            try:
                dlg.destroy()
            finally:
                # Relaunch the current Python executable with same args
                os.execv(sys.executable, [sys.executable] + sys.argv)

        ctk.CTkButton(btns, text="OK", command=do_close, fg_color=COL_ACCENT).pack(side="right", padx=6)
        ctk.CTkButton(btns, text="Restart", command=do_restart, fg_color=COL_HIGHLIGHT).pack(side="right")
    except Exception:
        # Fallback to messagebox if dialog construction fails
        logger.exception("Failed to show error dialog")
        try:
            messagebox.showerror(title, message)
        except Exception:
            pass


# Global exception hook: show dialog with traceback
def _global_excepthook(exc_type, exc_value, exc_tb):
    tb = traceback.format_exception(exc_type, exc_value, exc_tb)
    # Log full traceback as well
    logger.exception("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))
    # Try to attach to a root window if possible
    root = None
    try:
        root = tk._default_root
    except Exception:
        root = None
    show_error_dialog(root or tk.Tk(), "Unhandled Exception", str(exc_value), tb)

sys.excepthook = _global_excepthook

# threading exceptions
def _threading_excepthook(args):
    exc_type = args.exc_type
    exc_value = args.exc_value
    exc_tb = args.exc_traceback
    _global_excepthook(exc_type, exc_value, exc_tb)

try:
    threading.excepthook = _threading_excepthook
except Exception:
    pass

# ── Logging Setup ─────────────────────────────────────────────────────────────
colorama.init()

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[94m',     # Blue
        'INFO': '\033[92m',      # Green
        'WARNING': '\033[93m',   # Yellow
        'ERROR': '\033[91m',     # Red
        'CRITICAL': '\033[95m'   # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)

formatter = ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
root_logger = logging.getLogger()
root_logger.addHandler(handler)
root_logger.setLevel(logging.DEBUG if settings.get("debug_logging", False) else logging.INFO)
logger = logging.getLogger(__name__)
logger.debug(f"Logging initialized at {'DEBUG' if root_logger.level == logging.DEBUG else 'INFO'} level")

# ── Theme ─────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

COL_BG = "#1a1a2e"
COL_PANEL = "#16213e"
COL_ACCENT = "#0f3460"
COL_HIGHLIGHT = "#e94560"
COL_TEXT = "#eaeaea"
COL_MUTED = "#888888"
COL_HIDDEN = "#555577"
COL_FAV = "#e8c84a"
COL_HEADER = "#0d2137"

THUMB_W, THUMB_H = 200, 200
PREVIEW_MAX = 360


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_thumbnail(path: str, maxw=THUMB_W, maxh=THUMB_H):
    try:
        img = Image.open(path)
        img.thumbnail((maxw, maxh), Image.LANCZOS)
        return ctk.CTkImage(img, size=(img.width, img.height))
    except Exception:
        return None


def format_rating(raw: str) -> str:
    try:
        v = float(raw)
        stars = int(round(v * 5))
        return "★" * stars + "☆" * (5 - stars)
    except Exception:
        return raw or ""


def center_window(win: tk.Toplevel, parent: tk.Widget | None = None):
    win.update_idletasks()
    width = win.winfo_width()
    height = win.winfo_height()
    if parent is None:
        parent = win.master
    if parent is not None:
        parent.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = px + max(0, (pw - width) // 2)
        y = py + max(0, (ph - height) // 2)
    else:
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")


# ── Settings Dialog ───────────────────────────────────────────────────────────

class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("540x420")
        self.resizable(False, False)
        self.transient(parent)
        center_window(self, parent)
        self.grab_set()
        self._build()

    def _build(self):
        pad = {"padx": 14, "pady": 6}

        ctk.CTkLabel(self, text="Skyscraper Binary", font=("", 12, "bold")).pack(anchor="w", **pad)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=14)
        self._sky_var = ctk.StringVar(value=settings.get("skyscraper_bin", ""))
        ctk.CTkEntry(row, textvariable=self._sky_var, width=360).pack(side="left", padx=(0, 6))
        ctk.CTkButton(row, text="Browse", width=80, command=self._browse_sky).pack(side="left")

        ctk.CTkLabel(self, text="ScreenScraper Login", font=("", 12, "bold")).pack(anchor="w", **pad)
        ctk.CTkLabel(self, text="Username").pack(anchor="w", padx=14)
        self._user_var = ctk.StringVar(value=settings.get("screenscraper_user", ""))
        ctk.CTkEntry(self, textvariable=self._user_var, width=300).pack(anchor="w", padx=14, pady=(0, 6))
        ctk.CTkLabel(self, text="Password").pack(anchor="w", padx=14)
        self._pass_var = ctk.StringVar(value=settings.get("screenscraper_pass", ""))
        ctk.CTkEntry(self, textvariable=self._pass_var, show="•", width=300).pack(anchor="w", padx=14, pady=(0, 6))

        ctk.CTkLabel(self, text="Preview Image Size (px)", font=("", 12, "bold")).pack(anchor="w", **pad)
        self._prev_var = ctk.StringVar(value=str(settings.get("image_preview_size", 220)))
        ctk.CTkEntry(self, textvariable=self._prev_var, width=100).pack(anchor="w", padx=14)

        self._debug_var = ctk.BooleanVar(value=settings.get("debug_logging", False))
        ctk.CTkCheckBox(self, text="Enable debug logging", variable=self._debug_var).pack(anchor="w", padx=14, pady=(10, 0))

        btnrow = ctk.CTkFrame(self, fg_color="transparent")
        btnrow.pack(side="bottom", pady=14, padx=14, fill="x")
        ctk.CTkButton(btnrow, text="Save", command=self._save, fg_color=COL_HIGHLIGHT).pack(side="right", padx=4)
        ctk.CTkButton(btnrow, text="Cancel", command=self.destroy, fg_color=COL_ACCENT).pack(side="right", padx=4)

    def _browse_sky(self):
        path = filedialog.askopenfilename(title="Locate Skyscraper binary")
        if path:
            self._sky_var.set(path)

    def _save(self):
        settings.set("skyscraper_bin", self._sky_var.get())
        settings.set("screenscraper_user", self._user_var.get())
        settings.set("screenscraper_pass", self._pass_var.get())
        settings.set("debug_logging", self._debug_var.get())
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG if self._debug_var.get() else logging.INFO)
        if hasattr(self.master, "_debug_enabled"):
            self.master._debug_enabled.set(self._debug_var.get())
        try:
            settings.set("image_preview_size", int(self._prev_var.get()))
        except ValueError:
            pass
        user = self._user_var.get()
        pw = self._pass_var.get()
        if user and pw:
            write_skyscraper_credentials(user, pw)
        self.destroy()


# ── Batch Favorite Dialog ─────────────────────────────────────────────────────

class BatchFavoriteDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Batch Favorite by Names")
        self.geometry("700x500")
        self.resizable(False, False)
        self.transient(parent)
        center_window(self, parent)
        self.grab_set()
        self._matches = []
        self._build()

    def _build(self):
        # Top: input
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(14, 6))
        ctk.CTkLabel(top, text="Paste list of game names (one per line):", font=("", 12, "bold")).pack(anchor="w")
        self._text_box = ctk.CTkTextbox(top, height=100, wrap="word")
        self._text_box.pack(fill="x", pady=(6, 0))
        self._text_box.bind('<KeyRelease>', self._update_matches)

        # Bottom: matches
        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="both", expand=True, padx=14, pady=6)
        ctk.CTkLabel(bottom, text="Matching games:", font=("", 12, "bold")).pack(anchor="w", pady=(0, 6))
        self._tree = ttk.Treeview(bottom, columns=("name",), show="headings", height=10)
        self._tree.heading("name", text="Game Name")
        self._tree.column("name", width=600)
        sb = ttk.Scrollbar(bottom, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        btnrow = ctk.CTkFrame(self, fg_color="transparent")
        btnrow.pack(side="bottom", pady=14, padx=14, fill="x")
        ctk.CTkButton(btnrow, text="Apply", command=self._apply, fg_color=COL_HIGHLIGHT).pack(side="right", padx=4)
        ctk.CTkButton(btnrow, text="Cancel", command=self.destroy, fg_color=COL_ACCENT).pack(side="right", padx=4)

    def _update_matches(self, event=None):
        self._tree.delete(*self._tree.get_children())
        self._matches.clear()
        text = self._text_box.get("1.0", "end").strip()
        if not text or not self.parent._gamelist:
            return
        names = [line.strip().lower() for line in text.splitlines() if line.strip()]
        seen = set()
        for name in names:
            for g in self.parent._gamelist.games:
                if id(g) not in seen and (name in g.name.lower() or g.name.lower() in name):
                    self._tree.insert("", "end", values=(g.name,))
                    self._matches.append(g)
                    seen.add(id(g))

    def _apply(self):
        if not self._matches:
            logger.warning("No matching games found for batch favorite")
            messagebox.showinfo("No matches", "No matching games found.")
            return
        for g in self._matches:
            g.favorite = True
        self.parent._apply_filter()
        self.parent._status(f"Favored {len(self._matches)} games")
        logger.info(f"Batch favored {len(self._matches)} games")
        self.destroy()


# ── Detect Duplicates Dialog ──────────────────────────────────────────────────

import re

def get_base_name(name: str) -> str:
    # Remove region tags like (USA), [U], (Europe), etc.
    name = re.sub(r'\s*\([^)]*\)', '', name)  # Remove (anything)
    name = re.sub(r'\s*\[[^\]]*\]', '', name)  # Remove [anything]
    return name.strip()

def get_priority(name: str) -> int:
    name_lower = name.lower()
    if 'usa' in name_lower or 'ntsc-u' in name_lower or 'us' in name_lower:
        return 1
    elif 'japan' in name_lower or 'ntsc-j' in name_lower or 'jp' in name_lower:
        return 2
    elif 'brazil' in name_lower or 'br' in name_lower:
        return 3
    elif 'europe' in name_lower or 'pal' in name_lower or 'eur' in name_lower:
        return 4
    else:
        return 5

class DetectDuplicatesDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Detect and Hide Duplicates")
        self.geometry("800x600")
        self.resizable(False, False)
        self.transient(parent)
        center_window(self, parent)
        self.grab_set()
        self._visible_games = []
        self._hidden_games = []
        self._build()
        self._scan_duplicates()

    def _build(self):
        # Top: visible games
        top = ctk.CTkFrame(self)
        top.pack(fill="both", expand=True, padx=14, pady=(14, 6))
        ctk.CTkLabel(top, text="Games to Keep Visible:", font=("", 12, "bold")).pack(anchor="w", pady=(0, 6))
        self._visible_tree = ttk.Treeview(top, columns=("name",), show="headings", height=8)
        self._visible_tree.heading("name", text="Game Name")
        self._visible_tree.column("name", width=700)
        vsb1 = ttk.Scrollbar(top, orient="vertical", command=self._visible_tree.yview)
        self._visible_tree.configure(yscrollcommand=vsb1.set)
        self._visible_tree.pack(side="left", fill="both", expand=True)
        vsb1.pack(side="right", fill="y")

        # Bottom: hidden games
        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="both", expand=True, padx=14, pady=6)
        ctk.CTkLabel(bottom, text="Games to Hide:", font=("", 12, "bold")).pack(anchor="w", pady=(0, 6))
        self._hidden_tree = ttk.Treeview(bottom, columns=("name",), show="headings", height=8)
        self._hidden_tree.heading("name", text="Game Name")
        self._hidden_tree.column("name", width=700)
        vsb2 = ttk.Scrollbar(bottom, orient="vertical", command=self._hidden_tree.yview)
        self._hidden_tree.configure(yscrollcommand=vsb2.set)
        self._hidden_tree.pack(side="left", fill="both", expand=True)
        vsb2.pack(side="right", fill="y")

        btnrow = ctk.CTkFrame(self, fg_color="transparent")
        btnrow.pack(side="bottom", pady=14, padx=14, fill="x")
        ctk.CTkButton(btnrow, text="Apply", command=self._apply, fg_color=COL_HIGHLIGHT).pack(side="right", padx=4)
        ctk.CTkButton(btnrow, text="Cancel", command=self.destroy, fg_color=COL_ACCENT).pack(side="right", padx=4)

    def _scan_duplicates(self):
        if not self.parent._gamelist:
            return
        groups = {}
        for g in self.parent._gamelist.games:
            base = get_base_name(g.name)
            if base not in groups:
                groups[base] = []
            groups[base].append(g)

        for base, games in groups.items():
            if len(games) > 1:
                # Sort by priority
                games.sort(key=lambda g: get_priority(g.name))
                self._visible_games.append(games[0])
                self._hidden_games.extend(games[1:])
                # If any hidden game is favorite, mark the visible one as favorite
                if any(g.favorite for g in games[1:]):
                    games[0].favorite = True

        # Populate trees
        for g in self._visible_games:
            self._visible_tree.insert("", "end", values=(g.name,))
        for g in self._hidden_games:
            self._hidden_tree.insert("", "end", values=(g.name,))

    def _apply(self):
        for g in self._hidden_games:
            g.hidden = True
        self.parent._apply_filter()
        self.parent._status(f"Hidden {len(self._hidden_games)} duplicate games")
        logger.info(f"Hidden {len(self._hidden_games)} duplicate games")
        self.destroy()


def is_bad_version(name: str) -> bool:
    name_lower = name.lower()
    bad_tags = ['[b]', '[bad dump]', '[beta]', '[proto]', '[sample]', '[demo]', '[trailer]']
    return any(tag in name_lower for tag in bad_tags)

def get_revision(name: str) -> int:
    match = re.search(r'\(Rev (\d+)\)', name, re.IGNORECASE)
    return int(match.group(1)) if match else 0


class DetectBadVersionsDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Detect and Hide Bad Versions")
        self.geometry("800x600")
        self.resizable(False, False)
        self.transient(parent)
        center_window(self, parent)
        self.grab_set()
        self._visible_games = []
        self._hidden_games = []
        self._build()
        self._scan_bad_versions()

    def _build(self):
        # Top: visible games
        top = ctk.CTkFrame(self)
        top.pack(fill="both", expand=True, padx=14, pady=(14, 6))
        ctk.CTkLabel(top, text="Games to Keep Visible:", font=("", 12, "bold")).pack(anchor="w", pady=(0, 6))
        self._visible_tree = ttk.Treeview(top, columns=("name",), show="headings", height=8)
        self._visible_tree.heading("name", text="Game Name")
        self._visible_tree.column("name", width=700)
        vsb1 = ttk.Scrollbar(top, orient="vertical", command=self._visible_tree.yview)
        self._visible_tree.configure(yscrollcommand=vsb1.set)
        self._visible_tree.pack(side="left", fill="both", expand=True)
        vsb1.pack(side="right", fill="y")

        # Bottom: hidden games
        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="both", expand=True, padx=14, pady=6)
        ctk.CTkLabel(bottom, text="Games to Hide:", font=("", 12, "bold")).pack(anchor="w", pady=(0, 6))
        self._hidden_tree = ttk.Treeview(bottom, columns=("name",), show="headings", height=8)
        self._hidden_tree.heading("name", text="Game Name")
        self._hidden_tree.column("name", width=700)
        vsb2 = ttk.Scrollbar(bottom, orient="vertical", command=self._hidden_tree.yview)
        self._hidden_tree.configure(yscrollcommand=vsb2.set)
        self._hidden_tree.pack(side="left", fill="both", expand=True)
        vsb2.pack(side="right", fill="y")

        btnrow = ctk.CTkFrame(self, fg_color="transparent")
        btnrow.pack(side="bottom", pady=14, padx=14, fill="x")
        ctk.CTkButton(btnrow, text="Apply", command=self._apply, fg_color=COL_HIGHLIGHT).pack(side="right", padx=4)
        ctk.CTkButton(btnrow, text="Cancel", command=self.destroy, fg_color=COL_ACCENT).pack(side="right", padx=4)

    def _scan_bad_versions(self):
        if not self.parent._gamelist:
            return
        groups = {}
        for g in self.parent._gamelist.games:
            base = get_base_name(g.name)
            if base not in groups:
                groups[base] = []
            groups[base].append(g)

        for base, games in groups.items():
            if len(games) > 1:
                good_games = [g for g in games if not is_bad_version(g.name)]
                bad_games = [g for g in games if is_bad_version(g.name)]
                self._hidden_games.extend(bad_games)
                if len(good_games) > 1:
                    # Sort by revision descending
                    good_games.sort(key=lambda g: get_revision(g.name), reverse=True)
                    self._visible_games.append(good_games[0])
                    self._hidden_games.extend(good_games[1:])
                    # Transfer favorite if any hidden was favorite
                    if any(g.favorite for g in good_games[1:] + bad_games):
                        good_games[0].favorite = True
                elif good_games:
                    self._visible_games.append(good_games[0])
                    # Transfer favorite if any bad was favorite
                    if any(g.favorite for g in bad_games):
                        good_games[0].favorite = True
                # If no good games, maybe keep all? But since bad, perhaps hide all except one
                elif bad_games:
                    bad_games.sort(key=lambda g: get_revision(g.name), reverse=True)
                    self._visible_games.append(bad_games[0])
                    self._hidden_games.extend(bad_games[1:])
                    # No transfer needed since all are bad

        # Populate trees
        for g in self._visible_games:
            self._visible_tree.insert("", "end", values=(g.name,))
        for g in self._hidden_games:
            self._hidden_tree.insert("", "end", values=(g.name,))

    def _apply(self):
        for g in self._hidden_games:
            g.hidden = True
        self.parent._apply_filter()
        self.parent._status(f"Hidden {len(self._hidden_games)} bad/alternate version games")
        logger.info(f"Hidden {len(self._hidden_games)} bad/alternate version games")
        self.destroy()


class ReviewHiddenFavoritesDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Review Hidden & Favorites")
        self.geometry("400x200")
        self.resizable(False, False)
        self.transient(parent)
        center_window(self, parent)
        self.grab_set()
        self._build()
        self._review()

    def _build(self):
        ctk.CTkLabel(self, text="Reviewing hidden games and favorites...", font=("", 12)).pack(pady=20)
        self._status_label = ctk.CTkLabel(self, text="", font=("", 10))
        self._status_label.pack(pady=10)
        btnrow = ctk.CTkFrame(self, fg_color="transparent")
        btnrow.pack(side="bottom", pady=14, padx=14, fill="x")
        ctk.CTkButton(btnrow, text="Apply", command=self._apply, fg_color=COL_HIGHLIGHT).pack(side="right", padx=4)
        ctk.CTkButton(btnrow, text="Cancel", command=self.destroy, fg_color=COL_ACCENT).pack(side="right", padx=4)

    def _review(self):
        if not self.parent._gamelist:
            return
        groups = {}
        for g in self.parent._gamelist.games:
            base = get_base_name(g.name)
            if base not in groups:
                groups[base] = []
            groups[base].append(g)

        made_visible = 0
        for base, games in groups.items():
            # Check if all are hidden
            if all(g.hidden for g in games):
                # Make the highest priority visible
                games.sort(key=lambda g: get_priority(g.name))
                games[0].hidden = False
                made_visible += 1
            # Check favorites
            favorites = [g for g in games if g.favorite]
            if favorites and all(g.hidden for g in favorites):
                # Make the highest priority favorite visible
                favorites.sort(key=lambda g: get_priority(g.name))
                favorites[0].hidden = False
                made_visible += 1

        self._status_label.configure(text=f"Found {made_visible} games to make visible.")

    def _apply(self):
        self.parent._apply_filter()
        self.parent._status("Review applied")
        logger.info("Review hidden & favorites applied")
        self.destroy()


# ── Add Missing Folders Dialog ────────────────────────────────────────────────

class AddMissingFoldersDialog(ctk.CTkToplevel):
    def __init__(self, parent, manager: FolderIconManager):
        super().__init__(parent)
        self.parent = parent
        self.manager = manager
        self.title("Add Missing Folders")
        self.geometry("600x500")
        self.resizable(False, False)
        self.transient(parent)
        center_window(self, parent)
        self.grab_set()
        self.focus_force()
        self._missing = manager.scan_missing_folders()
        self._selected = {name: ctk.BooleanVar(value=True) for name in self._missing}
        self._build()
        self.wait_window()

    def _build(self):
        ctk.CTkLabel(self, text=f"Found {len(self._missing)} missing folders:", font=("", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 6))

        # Scrollable frame for checkboxes
        scroll_frame = ctk.CTkScrollableFrame(self, height=350)
        scroll_frame.pack(fill="both", expand=True, padx=14, pady=6)

        for name in self._missing:
            cb = ctk.CTkCheckBox(scroll_frame, text=name, variable=self._selected[name])
            cb.pack(anchor="w", padx=10, pady=2)

        btnrow = ctk.CTkFrame(self, fg_color="transparent")
        btnrow.pack(side="bottom", pady=14, padx=14, fill="x")
        ctk.CTkButton(btnrow, text="Select All", command=self._select_all).pack(side="left", padx=4)
        ctk.CTkButton(btnrow, text="Deselect All", command=self._deselect_all).pack(side="left", padx=4)
        ctk.CTkButton(btnrow, text="Add Selected", command=self._add_selected, fg_color=COL_HIGHLIGHT).pack(side="right", padx=4)
        ctk.CTkButton(btnrow, text="Cancel", command=self.destroy, fg_color=COL_ACCENT).pack(side="right", padx=4)

        self._status_label = ctk.CTkLabel(self, text="", font=("", 10))
        self._status_label.pack(fill="x", padx=14, pady=(0, 10))

    def _select_all(self):
        for var in self._selected.values():
            var.set(True)

    def _deselect_all(self):
        for var in self._selected.values():
            var.set(False)

    def _add_selected(self):
        selected_names = [name for name, var in self._selected.items() if var.get()]
        logger.info(f"User selected {len(selected_names)} folders to add: {selected_names}")
        if not selected_names:
            self._status_label.configure(text="Please select at least one folder to add.")
            return
        added = self.manager.add_missing_folders(selected_names)
        logger.info(f"Added {added} folders to gamelist")
        self._status_label.configure(text=f"Added {added} folders to the gamelist.")
        self.parent._update_folder_dropdown()
        self.destroy()


# ── Folder Icon Manager Dialog ────────────────────────────────────────────────

from folder_icon_manager import FolderIconManager

class FolderIconManagerDialog(ctk.CTkToplevel):
    """Manage folder icons in gamelist.xml"""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Manage Folder Icons")
        self.geometry("900x600")
        self.resizable(True, True)
        self.transient(parent)
        center_window(self, parent)
        self.grab_set()
        
        if not parent._gamelist:
            parent._status("Please open a gamelist first.")
            self.destroy()
            return
        
        self.manager = FolderIconManager(parent._gamelist, parent._gamelist.xml_path)
        self._current_folder_idx = 0
        self._current_icon_img = None
        self._new_icon_img = None
        self._build()
        self._load_folder(0)

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Main container
        main = ctk.CTkFrame(self)
        main.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(1, weight=1)

        # Top: folder list
        top = ctk.CTkFrame(main)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        
        header_frame = ctk.CTkFrame(top, fg_color="transparent")
        header_frame.pack(fill="x", anchor="w")
        self._folder_count_label = ctk.CTkLabel(header_frame, text=f"Folders found: {len(self.manager.folders)}", font=("", 12, "bold"))
        self._folder_count_label.pack(side="left")
        ctk.CTkButton(header_frame, text="Add Missing Folders", command=self._add_missing_folders, width=150, fg_color=COL_ACCENT).pack(side="right", padx=0)
        
        list_frame = ctk.CTkFrame(top)
        list_frame.pack(fill="x", pady=(6, 0))
        list_frame.grid_columnconfigure(0, weight=1)
        
        self._folder_var = ctk.StringVar()
        self._folder_dropdown = ctk.CTkOptionMenu(
            list_frame,
            variable=self._folder_var,
            values=[f.name for f in self.manager.folders],
            command=self._on_folder_select
        )
        self._folder_dropdown.pack(fill="x")
        
        # Hidden checkbox
        hidden_frame = ctk.CTkFrame(top, fg_color="transparent")
        hidden_frame.pack(fill="x", pady=(6, 0))
        self._hidden_var = ctk.BooleanVar()
        self._hidden_checkbox = ctk.CTkCheckBox(hidden_frame, text="Hidden", variable=self._hidden_var)
        self._hidden_checkbox.pack(anchor="w")
        self._hidden_var.trace_add("write", lambda *_: self._apply_hidden_change())

        # Middle: current icon | new icon
        mid = ctk.CTkFrame(main)
        mid.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        mid.grid_columnconfigure(0, weight=1)
        mid.grid_columnconfigure(1, weight=1)

        # Left: current icon
        left = ctk.CTkFrame(mid)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ctk.CTkLabel(left, text="Current Icon", font=("", 11, "bold")).pack(anchor="w", pady=(0, 4))
        self._current_icon_label = ctk.CTkLabel(left, text="No icon", width=200, height=200, fg_color=COL_HEADER)
        self._current_icon_label.pack()

        # Right: new icon selection
        right = ctk.CTkFrame(mid)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        ctk.CTkLabel(right, text="New Icon", font=("", 11, "bold")).pack(anchor="w", pady=(0, 4))
        
        # Icon selector with browse button
        icon_frame = ctk.CTkFrame(right)
        icon_frame.pack(fill="both", expand=True)
        icon_frame.grid_columnconfigure(0, weight=1)
        icon_frame.grid_rowconfigure(1, weight=1)
        
        browse_btn_frame = ctk.CTkFrame(icon_frame, fg_color="transparent")
        browse_btn_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ctk.CTkButton(browse_btn_frame, text="Browse…", command=self._browse_icon, width=80).pack(side="left", padx=2)
        self._icon_path_label = ctk.CTkLabel(browse_btn_frame, text="No file selected", text_color="gray", font=("", 10))
        self._icon_path_label.pack(side="left", fill="x", expand=True, padx=(8, 0))
        
        self._new_icon_label = ctk.CTkLabel(icon_frame, text="Preview", width=200, height=200, fg_color=COL_HEADER)
        self._new_icon_label.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        
        self._selected_icon_path = None

        # Bottom: buttons
        btm = ctk.CTkFrame(main, fg_color="transparent")
        btm.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        
        ctk.CTkButton(btm, text="Previous", command=self._prev_folder, width=100).pack(side="left", padx=2)
        ctk.CTkButton(btm, text="Next", command=self._next_folder, width=100).pack(side="left", padx=2)
        
        ctk.CTkButton(btm, text="Done", command=self._done, fg_color=COL_HIGHLIGHT, width=80).pack(side="right", padx=2)
        ctk.CTkButton(btm, text="Cancel", command=self.destroy, fg_color=COL_ACCENT, width=80).pack(side="right", padx=2)

        self._status_label = ctk.CTkLabel(main, text="", font=("", 10))
        self._status_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def _update_folder_dropdown(self):
        """Update the folder dropdown with current folders."""
        folder_names = [f.name for f in self.manager.folders]
        logger.info(f"Updating folder dropdown with {len(folder_names)} folders: {folder_names}")
        self._folder_dropdown.configure(values=folder_names)
        if folder_names:
            self._folder_var.set(folder_names[0])
            self._load_folder(0)
        # Update count label
        self._folder_count_label.configure(text=f"Folders found: {len(self.manager.folders)}")

    def _load_folder(self, idx: int):
        """Load folder at given index."""
        if not 0 <= idx < len(self.manager.folders):
            return
        
        self._current_folder_idx = idx
        folder = self.manager.folders[idx]
        
        # Update dropdown
        self._folder_var.set(folder.name)
        
        # Load hidden state
        self._hidden_var.set(folder.hidden)
        
        # Load current icon
        current_icon_path = self.manager.get_folder_icon_path(folder)
        if current_icon_path:
            try:
                img = Image.open(current_icon_path).convert("RGBA")
                img.thumbnail((200, 200), Image.Resampling.LANCZOS)
                self._current_icon_img = ctk.CTkImage(img, size=(200, 200))
                self._current_icon_label.configure(image=self._current_icon_img, text="")
            except Exception:
                logger.exception("Failed to load current icon")
                self._current_icon_label.configure(image=None, text="Error loading icon")
                self._current_icon_img = None
        else:
            self._current_icon_label.configure(image=None, text="No icon")
            self._current_icon_img = None
        
        # Reset preview
        try:
            self._new_icon_label.configure(image=None)
        except Exception:
            pass
        self._new_icon_label.configure(text="Preview")
        self._new_icon_img = None
        self._selected_icon_path = None
        self._icon_path_label.configure(text="No file selected")
        
        # Update status
        self._status_label.configure(text=f"Folder {idx + 1} of {len(self.manager.folders)}")

    def _on_folder_select(self, value: str):
        """Handle folder selection from dropdown."""
        for i, folder in enumerate(self.manager.folders):
            if folder.name == value:
                self._load_folder(i)
                break

    def _browse_icon(self):
        """Open file browser to select an icon file and apply it immediately."""
        file_path = filedialog.askopenfilename(
            title="Select Icon",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp"), ("All files", "*.*")]
        )
        if not file_path:
            return

        rel_path = self.manager.copy_image_to_collection(file_path)
        if not rel_path:
            self._status_label.configure(text="Failed to copy icon into collection.")
            logger.error("Failed to copy icon into collection")
            return

        folder = self.manager.folders[self._current_folder_idx]
        self._ensure_folder_path_prefix(folder)
        folder.set("image", rel_path)
        abs_path = Path(self.manager.gamelist.base_dir) / rel_path.lstrip("./")
        self._selected_icon_path = str(abs_path)
        self._icon_path_label.configure(text=Path(rel_path).name, text_color="white")
        self._preview_icon(str(abs_path))
        self._status_label.configure(text=f"Updated icon for {folder.name}")
        logger.info(f"Applied image {rel_path} to folder {folder.name}")

    def _preview_icon(self, icon_path: str):
        """Preview the selected icon file."""
        try:
            img = Image.open(icon_path).convert("RGBA")
            img.thumbnail((200, 200), Image.Resampling.LANCZOS)
            self._new_icon_img = ctk.CTkImage(img, size=(200, 200))
            self._new_icon_label.configure(image=self._new_icon_img, text="")
        except Exception:
            logger.exception("Failed to load preview icon")
            self._new_icon_img = None
            self._selected_icon_path = None
            try:
                self._new_icon_label.configure(image=None)
            except Exception:
                pass
            self._new_icon_label.configure(text="Error loading")

    def _apply_current(self):
        """Apply current hidden state and ensure path normalization."""
        folder = self.manager.folders[self._current_folder_idx]
        self._ensure_folder_path_prefix(folder)
        folder.hidden = self._hidden_var.get()
        self._status_label.configure(text=f"Updated hidden state for {folder.name}")
        logger.info(f"Set hidden={folder.hidden} for folder {folder.name}")

    def _apply_hidden_change(self):
        """Triggered when the hidden checkbox changes."""
        folder = self.manager.folders[self._current_folder_idx]
        self._ensure_folder_path_prefix(folder)
        folder.hidden = self._hidden_var.get()
        self._status_label.configure(text=f"Hidden set to {folder.hidden} for {folder.name}")
        logger.info(f"Hidden changed to {folder.hidden} for folder {folder.name}")

    def _ensure_folder_path_prefix(self, folder: Game):
        if folder.path and not folder.path.startswith("./") and not os.path.isabs(folder.path):
            folder.set("path", "./" + folder.path.lstrip("./"))

    def _prev_folder(self):
        """Load previous folder."""
        self._load_folder(self._current_folder_idx - 1)

    def _add_missing_folders(self):
        """Scan and add missing folders from gamelist directory."""
        missing = self.manager.scan_missing_folders()
        
        if not missing:
            self._status_label.configure(text="All subdirectories are already in the gamelist.")
            logger.info("No missing folders to add")
            return
        
        # Open the new dialog
        AddMissingFoldersDialog(self, self.manager)

    def _next_folder(self):
        """Load next folder."""
        self._load_folder(self._current_folder_idx + 1)

    def _done(self):
        """Save all changes and close."""
        self.manager.apply_all_changes()
        self.parent._apply_filter()
        self.parent._status("Folder icons updated")
        logger.info("Folder icon manager closed and changes applied")
        self.destroy()


# ── Game Edit Dialog ──────────────────────────────────────────────────────────

class GameEditDialog(ctk.CTkToplevel):
    """Full metadata editor for a single game."""

    def __init__(self, parent, game: Game, gamelist: GameList):
        super().__init__(parent)
        self.game = game
        self.gamelist = gamelist
        self.title(f"Edit — {game.name}")
        self.geometry("860x680")
        self.transient(parent)
        center_window(self, parent)
        self.grab_set()
        self._vars: dict[str, tk.Variable] = {}
        self._thumb_img = None
        self._build()
        self._populate()
        self._initial_values = self.game.as_dict()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        # Left — scrollable fields
        left = ctk.CTkScrollableFrame(self, label_text="Metadata")
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 4), pady=10)
        left.grid_columnconfigure(1, weight=1)

        text_fields = [f for f in GAME_FIELDS if f not in BOOL_FIELDS and f not in MEDIA_FIELDS]
        for i, field in enumerate(text_fields):
            ctk.CTkLabel(left, text=field, width=110, anchor="e").grid(row=i, column=0, padx=(4, 8), pady=3, sticky="e")
            if field == "desc":
                var = tk.StringVar()
                box = ctk.CTkTextbox(left, height=80)
                box.grid(row=i, column=1, padx=4, pady=3, sticky="ew")
                self._vars[field] = ("textbox", box)
            else:
                var = ctk.StringVar()
                entry = ctk.CTkEntry(left, textvariable=var)
                entry.grid(row=i, column=1, padx=4, pady=3, sticky="ew")
                self._vars[field] = var

        # Bool checkboxes
        offset = len(text_fields)
        for j, field in enumerate(sorted(BOOL_FIELDS)):
            var = ctk.BooleanVar()
            cb = ctk.CTkCheckBox(left, text=field, variable=var)
            cb.grid(row=offset + j, column=1, padx=4, pady=3, sticky="w")
            self._vars[field] = var

        # Media path fields with browse buttons
        offset2 = offset + len(BOOL_FIELDS)
        for k, field in enumerate(sorted(MEDIA_FIELDS)):
            ctk.CTkLabel(left, text=field, width=110, anchor="e").grid(
                row=offset2 + k, column=0, padx=(4, 8), pady=3, sticky="e")
            var = ctk.StringVar()
            row_f = ctk.CTkFrame(left, fg_color="transparent")
            row_f.grid(row=offset2 + k, column=1, padx=4, pady=3, sticky="ew")
            row_f.grid_columnconfigure(0, weight=1)
            entry = ctk.CTkEntry(row_f, textvariable=var)
            entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
            ctk.CTkButton(
                row_f, text="…", width=28,
                command=lambda f=field, v=var: self._browse_media(f, v)
            ).grid(row=0, column=1)
            self._vars[field] = var

        # Right — image preview
        right = ctk.CTkFrame(self, width=240)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 10), pady=10)
        right.grid_propagate(False)

        self._thumb_label = ctk.CTkLabel(right, text="No image", width=220, height=220)
        self._thumb_label.pack(padx=10, pady=10)

        ctk.CTkButton(right, text="Refresh Preview", command=self._refresh_preview).pack(pady=4)

        ctk.CTkLabel(right, text="Orphan Media", font=("", 11, "bold")).pack(pady=(10, 2))
        self._orphan_box = ctk.CTkTextbox(right, height=120, state="disabled")
        self._orphan_box.pack(fill="x", padx=8)

        # Bottom buttons
        btnrow = ctk.CTkFrame(self, fg_color="transparent")
        btnrow.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=8)
        ctk.CTkButton(btnrow, text="Save", fg_color=COL_HIGHLIGHT, command=self._save).pack(side="right", padx=4)
        ctk.CTkButton(btnrow, text="Cancel", fg_color=COL_ACCENT, command=self.destroy).pack(side="right", padx=4)
        ctk.CTkButton(btnrow, text="Find Orphan Media", command=self._scan_orphans).pack(side="left", padx=4)

    def _populate(self):
        for field, var in self._vars.items():
            val = self.game.get(field)
            if isinstance(var, tuple) and var[0] == "textbox":
                box = var[1]
                box.configure(state="normal")
                box.delete("1.0", "end")
                box.insert("1.0", val)
                box.configure(state="normal")
            elif isinstance(var, ctk.BooleanVar) or isinstance(var, tk.BooleanVar):
                var.set(val.lower() in ("true", "1", "yes"))
            else:
                var.set(val)
        self._refresh_preview()

    def _refresh_preview(self):
        img_path_raw = None
        if isinstance(self._vars.get("image"), ctk.StringVar):
            img_path_raw = self._vars["image"].get()
        if not img_path_raw:
            img_path_raw = self.game.get("image")
        abs_path = self.gamelist.resolve_media_path(img_path_raw)
        self._thumb_label.configure(image=None)  # Clear previous image
        if abs_path:
            self._thumb_img = load_thumbnail(abs_path, 220, 220)
            if self._thumb_img:
                self._thumb_label.configure(image=self._thumb_img, text="")
                return
        self._thumb_label.configure(text="No image")

    def _browse_media(self, field: str, var: ctk.StringVar):
        path = filedialog.askopenfilename(
            title=f"Select {field}",
            filetypes=[("Images/Video", "*.png *.jpg *.jpeg *.webp *.gif *.mp4 *.avi"), ("All", "*.*")]
        )
        if path:
            # Store relative to gamelist base_dir if possible
            try:
                rel = os.path.relpath(path, self.gamelist.base_dir)
                var.set("./" + rel.replace(os.sep, "/"))
            except ValueError:
                var.set(path)
            if field == "image":
                self._refresh_preview()

    def _scan_orphans(self):
        found = self.gamelist.find_orphan_media(self.game)
        self._orphan_box.configure(state="normal")
        self._orphan_box.delete("1.0", "end")
        if found:
            for key, abs_p in found.items():
                self._orphan_box.insert("end", f"{key}\n")
        else:
            self._orphan_box.insert("end", "(none found)")
        self._orphan_box.configure(state="disabled")

    def _save(self):
        changes = []
        for field, var in self._vars.items():
            if isinstance(var, tuple) and var[0] == "textbox":
                val = var[1].get("1.0", "end").strip()
            elif isinstance(var, ctk.BooleanVar) or isinstance(var, tk.BooleanVar):
                val = "true" if var.get() else "false"
            else:
                val = var.get().strip()
            old_val = self.game.get(field, "")
            if old_val != val:
                self.game.set(field, val)
                changes.append((field, old_val, val))
        if changes:
            logger.info(
                f"Saved changes for game {self.game.name}: "
                + ", ".join(f"{f}: {o!r} -> {n!r}" for f, o, n in changes)
            )
        else:
            logger.debug(f"No changes saved for game {self.game.name}")
        self.destroy()


# ── Scraper Log Dialog ────────────────────────────────────────────────────────

class ScraperDialog(ctk.CTkToplevel):
    def __init__(self, parent, cmd: list[str], title="Scraping..."):
        super().__init__(parent)
        self.title(title)
        self.geometry("700x440")
        self.transient(parent)
        center_window(self, parent)
        self._job: ScraperJob | None = None
        self._cmd = cmd
        self._build()
        self.after(200, self._start)

    def _build(self):
        ctk.CTkLabel(self, text=" ".join(self._cmd[:4]) + " ...", font=("Courier", 10)).pack(
            anchor="w", padx=10, pady=(8, 2))
        self._log = ctk.CTkTextbox(self, state="disabled", font=("Courier", 11))
        self._log.pack(fill="both", expand=True, padx=10, pady=4)
        self._status = ctk.CTkLabel(self, text="Running...", text_color=COL_MUTED)
        self._status.pack(pady=2)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=8)
        self._cancel_btn = ctk.CTkButton(row, text="Cancel", fg_color=COL_ACCENT, command=self._cancel)
        self._cancel_btn.pack(side="left", padx=6)
        self._close_btn = ctk.CTkButton(row, text="Close", fg_color=COL_HIGHLIGHT, command=self.destroy, state="disabled")
        self._close_btn.pack(side="left", padx=6)

    def _start(self):
        self._job = ScraperJob(self._cmd, progress_cb=self._on_line, done_cb=self._on_done)
        self._job.run()

    def _on_line(self, line: str):
        self.after(0, self._append_log, line)

    def _append_log(self, line: str):
        self._log.configure(state="normal")
        self._log.insert("end", line + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _on_done(self, rc: int):
        self.after(0, self._finish, rc)

    def _finish(self, rc: int):
        color = "#44cc88" if rc == 0 else COL_HIGHLIGHT
        self._status.configure(text=f"Done (exit code {rc})", text_color=color)
        self._cancel_btn.configure(state="disabled")
        self._close_btn.configure(state="normal")

    def _cancel(self):
        if self._job:
            self._job.cancel()
        self._status.configure(text="Cancelled", text_color=COL_MUTED)
        self._cancel_btn.configure(state="disabled")
        self._close_btn.configure(state="normal")


# ── ROM Scanner Dialog ────────────────────────────────────────────────────────

class RomScannerDialog(ctk.CTkToplevel):
    def __init__(self, parent, gamelist: GameList, on_add_cb):
        super().__init__(parent)
        self.gamelist = gamelist
        self.on_add_cb = on_add_cb
        self.title("Scan ROMs")
        self.geometry("760x520")
        self.transient(parent)
        center_window(self, parent)
        self.grab_set()
        self._results: list[dict] = []
        self._build()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=8)

        self._dir_var = ctk.StringVar(value=self.gamelist.base_dir)
        ctk.CTkLabel(top, text="ROM Directory:").pack(side="left")
        ctk.CTkEntry(top, textvariable=self._dir_var, width=400).pack(side="left", padx=6)
        ctk.CTkButton(top, text="Browse", command=self._browse, width=70).pack(side="left")
        ctk.CTkButton(top, text="Scan", fg_color=COL_HIGHLIGHT, command=self._scan, width=70).pack(side="left", padx=6)

        self._count_label = ctk.CTkLabel(self, text="")
        self._count_label.pack()

        # Table
        frame = ctk.CTkFrame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=4)

        cols = ("sel", "name", "path")
        self._tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="extended")
        self._tree.heading("sel", text="✓")
        self._tree.heading("name", text="Name")
        self._tree.heading("path", text="Path")
        self._tree.column("sel", width=30, anchor="center")
        self._tree.column("name", width=220)
        self._tree.column("path", width=420)

        sb = ttk.Scrollbar(frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._checked: set[str] = set()
        self._tree.bind("<space>", self._toggle_sel)
        self._tree.bind("<Double-1>", self._toggle_sel)

        btnrow = ctk.CTkFrame(self, fg_color="transparent")
        btnrow.pack(pady=8)
        ctk.CTkButton(btnrow, text="Select All", command=self._sel_all, width=100).pack(side="left", padx=4)
        ctk.CTkButton(btnrow, text="Select None", command=self._sel_none, width=100).pack(side="left", padx=4)
        ctk.CTkButton(btnrow, text="Add Selected to Gamelist",
                      fg_color=COL_HIGHLIGHT, command=self._add_selected).pack(side="left", padx=4)

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self._dir_var.get())
        if d:
            self._dir_var.set(d)

    def _scan(self):
        self._tree.delete(*self._tree.get_children())
        self._checked.clear()
        directory = self._dir_var.get()
        all_roms = scan_roms(directory)
        self._results = diff_against_gamelist(all_roms, self.gamelist)
        for r in self._results:
            iid = r["path"]
            self._tree.insert("", "end", iid=iid, values=("☐", r["name"], r["path"]))
        self._count_label.configure(
            text=f"{len(self._results)} new ROMs found (not in gamelist)")

    def _toggle_sel(self, event=None):
        for iid in self._tree.selection():
            vals = list(self._tree.item(iid, "values"))
            if iid in self._checked:
                self._checked.discard(iid)
                vals[0] = "☐"
            else:
                self._checked.add(iid)
                vals[0] = "☑"
            self._tree.item(iid, values=vals)

    def _sel_all(self):
        for r in self._results:
            iid = r["path"]
            self._checked.add(iid)
            self._tree.item(iid, values=("☑", r["name"], r["path"]))

    def _sel_none(self):
        for r in self._results:
            iid = r["path"]
            self._checked.discard(iid)
            self._tree.item(iid, values=("☐", r["name"], r["path"]))

    def _add_selected(self):
        to_add = [r for r in self._results if r["path"] in self._checked]
        if not to_add:
            messagebox.showinfo("Nothing selected", "Check at least one ROM first.")
            return
        for r in to_add:
            fields = {"path": r["path"], "name": r["name"]}
            self.gamelist.add_game(fields)
        self.on_add_cb(len(to_add))
        self.destroy()


def get_asset_path(relative_path):
    """Resolve o caminho para assets, compatível com PyInstaller --onefile"""
    if hasattr(sys, '_MEIPASS'):
        # Caminho da pasta temporária onde o PyInstaller extrai os arquivos
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)
# ── Main Window ───────────────────────────────────────────────────────────────

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("GameList Editor — RetroBat / EmulationStation")
        self.geometry("1340x780")
        self.minsize(900, 600)
        self._gamelist: GameList | None = None
        self._filtered_games: list[Game] = []
        self._selected_games: list[Game] = []
        self._preview_img = None
        self._sort_col = "name"
        self._sort_rev = False
        self._debug_enabled = tk.BooleanVar(value=settings.get("debug_logging", False))

        # Load icons
        try:
            self.icon_open = ctk.CTkImage(Image.open(get_asset_path("icons/icons8-opened-folder-32.png")), size=(24,24))
            self.icon_save = ctk.CTkImage(Image.open(get_asset_path("icons/icons8-save-32.png")), size=(24,24))
            self.icon_reload = ctk.CTkImage(Image.open(get_asset_path("icons/icons8-restart-32.png")), size=(24,24))
            self.icon_hide = ctk.CTkImage(Image.open(get_asset_path("icons/icons8-switch-off-32.png")), size=(24,24))
            self.icon_unhide = ctk.CTkImage(Image.open(get_asset_path("icons/icons8-eye-32.png")), size=(24,24))
            self.icon_favorite = ctk.CTkImage(Image.open(get_asset_path("icons/icons8-star-32.png")), size=(24,24))
            self.icon_delete = ctk.CTkImage(Image.open(get_asset_path("icons/icons8-trash-32.png")), size=(24,24))
            self.icon_scan = ctk.CTkImage(Image.open(get_asset_path("icons/icons8-search-32.png")), size=(24,24))
            self.icon_scrape = ctk.CTkImage(Image.open(get_asset_path("icons/icons8-command-line-32.png")), size=(24,24))
            self.icon_tools = ctk.CTkImage(Image.open(get_asset_path("icons/icons8-toolbox-32.png")), size=(24,24))
            # App icon
            self.iconphoto(False, ImageTk.PhotoImage(Image.open(get_asset_path("icons/app_icon.ico"))))
            logger.info("Icons loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load some icons: {e}")
            self.icon_open = None
            self.icon_save = None
            self.icon_reload = None
            self.icon_hide = None
            self.icon_unhide = None
            self.icon_favorite = None
            self.icon_delete = None
            self.icon_scan = None
            self.icon_scrape = None
            self.icon_tools = None

        self._build_menu()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._confirm_exit)

    def report_callback_exception(self, exc, val, tb):
        # Called by Tkinter for exceptions in callbacks
        try:
            tb_lines = traceback.format_exception(exc, val, tb)
            show_error_dialog(self, "Application Error", str(val), tb_lines)
        except Exception:
            logger.exception("Failed while reporting callback exception")

    def _set_title_with_path(self, path: str):
        # Truncate the start of the path if too long; keep last 2 folders + file
        try:
            p = Path(path)
            parts = [p.drive] + list(p.parts[1:]) if p.drive else list(p.parts)
            # Use only last 3 components (two folders + filename)
            if len(parts) > 3:
                display = os.path.join("...", *parts[-3:])
            else:
                display = path
            self.title(f"GameList Editor — {display}")
        except Exception:
            self.title(f"GameList Editor — {os.path.basename(path)}")

    def _show_about(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("About")
        dlg.geometry("540x300")
        dlg.transient(self)
        center_window(dlg, self)
        dlg.grab_set()

        # Icon if available
        try:
            ico = Image.open(get_asset_path("icons/app_icon.ico"))
            img = ctk.CTkImage(ico, size=(64, 64))
            ctk.CTkLabel(dlg, image=img, text="").pack(pady=(12, 4))
        except Exception:
            pass

        # Version
        ver = "?"
        try:
            ver = open(get_asset_path("VERSION")).read().strip()
        except Exception:
            try:
                ver = open("VERSION").read().strip()
            except Exception:
                pass

        ctk.CTkLabel(dlg, text=f"gamelistify — version {ver}", font=("", 13, "bold")).pack(pady=(6, 4))

        about_text = (
            "Author: Marcelo Frau\n"
            "Co-authors: Copilot, Claude Code, Gemini\n"
            "Icons: icons8\n\n"
            "Project: https://github.com/tres-por-dez/gamelistify"
        )
        txt = ctk.CTkLabel(dlg, text=about_text, justify="left")
        txt.pack(padx=12, pady=6)

        def open_proj():
            webbrowser.open("https://github.com/tres-por-dez/gamelistify")

        ctk.CTkButton(dlg, text="Open Project Page", command=open_proj, fg_color=COL_ACCENT).pack(pady=10)

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self):
        menubar = tk.Menu(self)
        self.configure(menu=menubar)

        fm = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=fm)
        fm.add_command(label="Open gamelist.xml…", accelerator="Ctrl+O", command=self._open_file)
        fm.add_command(label="Save", accelerator="Ctrl+S", command=self._save)
        fm.add_command(label="Save As…", command=self._save_as)
        fm.add_separator()
        fm.add_command(label="Reload from disk", command=self._reload)
        fm.add_separator()
        self._recent_menu = tk.Menu(fm, tearoff=0)
        fm.add_cascade(label="Recent Files", menu=self._recent_menu)
        self._update_recent_menu()
        fm.add_separator()
        fm.add_command(label="Exit", command=self._confirm_exit)

        em = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=em)
        em.add_command(label="Select All", accelerator="Ctrl+A", command=self._select_all)
        em.add_command(label="Invert Selection", command=self._invert_selection)
        em.add_separator()
        em.add_command(label="Hide Selected", command=lambda: self._bulk_set_flag("hidden", True))
        em.add_command(label="Unhide Selected", command=lambda: self._bulk_set_flag("hidden", False))
        em.add_command(label="Favorite Selected", command=lambda: self._bulk_set_flag("favorite", True))
        em.add_command(label="Unfavorite Selected", command=lambda: self._bulk_set_flag("favorite", False))
        em.add_separator()
        em.add_command(label="Delete Selected Entries…", command=self._delete_selected)
        em.add_command(label="Add Game Manually…", command=self._add_manual)

        sm = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Scrape", menu=sm)
        sm.add_command(label="Scrape Selected…", command=self._scrape_selected, state="disabled")
        sm.add_command(label="Scrape All (bulk)…", command=self._scrape_bulk, state="disabled")

        vm = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=vm)
        vm.add_command(label="Scan ROMs…", command=self._scan_roms, state="disabled")
        vm.add_checkbutton(
            label="Enable Debug Logging",
            variable=self._debug_enabled,
            onvalue=True, offvalue=False,
            command=self._toggle_debug_logging,
        )

        om = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=om)
        om.add_command(label="Settings…", command=self._open_settings)
        om.add_command(label="Set Name from Filename", command=self._set_name_from_filename)
        om.add_command(label="Batch Favorite by Names", command=self._batch_favorite)
        om.add_command(label="Detect and Hide Duplicates", command=self._detect_duplicates)
        om.add_command(label="Detect and Hide Bad Versions", command=self._detect_bad_versions)
        om.add_command(label="Review Hidden & Favorites", command=self._review_hidden_favorites)
        om.add_separator()
        om.add_command(label="Manage Folder Icons…", command=self._manage_folder_icons)

        # Help / About
        hm = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=hm)
        hm.add_command(label="About", command=self._show_about)

        self.bind("<Control-o>", lambda e: self._open_file())
        self.bind("<Control-s>", lambda e: self._save())
        self.bind("<Control-a>", lambda e: self._select_all())
        self.bind("<Control-d>", lambda e: self._delete_selected())
        self.bind("<Control-i>", lambda e: self._invert_selection())
        self.bind("<Control-f>", lambda e: self._focus_filter())
        self.bind("<Control-Shift-d>", lambda e: self._toggle_debug_logging())

    def _update_recent_menu(self):
        self._recent_menu.delete(0, "end")
        for path in settings.get("recent_files", []):
            self._recent_menu.add_command(
                label=path, command=lambda p=path: self._load_gamelist(p))

    def _focus_filter(self):
        if hasattr(self, '_filter_entry'):
            self._filter_entry.focus()

    def _toggle_debug_logging(self):
        enabled = self._debug_enabled.get()
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG if enabled else logging.INFO)
        settings.set("debug_logging", enabled)
        self._status(f"Debug logging {'enabled' if enabled else 'disabled'}")
        logger.info(f"Debug logging {'enabled' if enabled else 'disabled'}")


    # ── UI Layout ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Top toolbar ───────────────────────────────────────────────────────
        toolbar = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color=COL_HEADER)
        toolbar.grid(row=0, column=0, sticky="ew", columnspan=2)
        toolbar.grid_propagate(False)

        open_btn = ctk.CTkButton(toolbar, image=self.icon_open, text="", width=40, command=self._open_file, compound="left")
        open_btn.pack(side="left", padx=4, pady=6)
        CTkToolTip(open_btn, "Open gamelist.xml (Ctrl+O)")

        save_btn = ctk.CTkButton(toolbar, image=self.icon_save, text="", width=40, fg_color=COL_ACCENT, command=self._save, compound="left")
        save_btn.pack(side="left", padx=2, pady=6)
        CTkToolTip(save_btn, "Save (Ctrl+S)")

        reload_btn = ctk.CTkButton(toolbar, image=self.icon_reload, text="", width=40, fg_color=COL_ACCENT, command=self._reload, compound="left")
        reload_btn.pack(side="left", padx=2, pady=6)
        CTkToolTip(reload_btn, "Reload from disk")

        self.tools_btn = ctk.CTkButton(toolbar, image=self.icon_tools, text="Tools", width=40)
        self.tools_btn.pack(side="left", padx=2, pady=6)
        CTkToolTip(self.tools_btn, "Tools")
        self.tools_btn.bind("<Button-1>", self._show_tools_menu)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8, pady=4)

        ctk.CTkButton(toolbar, image=self.icon_hide, text="Hide", width=70, command=lambda: self._bulk_set_flag("hidden", True), compound="left").pack(side="left", padx=2, pady=6)
        ctk.CTkButton(toolbar, image=self.icon_unhide, text="Unhide", width=80, command=lambda: self._bulk_set_flag("hidden", False), compound="left").pack(side="left", padx=2, pady=6)
        ctk.CTkButton(toolbar, image=self.icon_favorite, text="Fav", width=70, command=lambda: self._bulk_set_flag("favorite", True), compound="left").pack(side="left", padx=2, pady=6)
        ctk.CTkButton(toolbar, image=self.icon_delete, text="Delete", width=80, fg_color="#6b1a1a", command=self._delete_selected, compound="left").pack(side="left", padx=2, pady=6)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8, pady=4)

        scan_btn = ctk.CTkButton(toolbar, image=self.icon_scan, text="Scan ROMs", width=100, command=self._scan_roms, compound="left", state="disabled")
        scan_btn.pack(side="left", padx=2, pady=6)
        CTkToolTip(scan_btn, "Not implemented yet")

        scrape_sel_btn = ctk.CTkButton(toolbar, image=self.icon_scrape, text="Scrape Sel.", width=100, command=self._scrape_selected, compound="left", state="disabled")
        scrape_sel_btn.pack(side="left", padx=2, pady=6)
        CTkToolTip(scrape_sel_btn, "Not implemented yet")

        scrape_all_btn = ctk.CTkButton(toolbar, image=self.icon_scrape, text="Scrape All", width=100, command=self._scrape_bulk, compound="left", state="disabled")
        scrape_all_btn.pack(side="left", padx=2, pady=6)
        CTkToolTip(scrape_all_btn, "Not implemented yet")

        # Search / filter
        ctk.CTkLabel(toolbar, text="Filter:").pack(side="right", padx=(4, 2))
        self._filter_var = ctk.StringVar()
        self._filter_var.trace_add("write", lambda *_: self._apply_filter())
        self._filter_entry = ctk.CTkEntry(toolbar, textvariable=self._filter_var, width=180)
        self._filter_entry.pack(side="right", padx=(0, 8), pady=6)

        # Show hidden checkbox
        self._show_hidden_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(toolbar, text="Show Hidden", variable=self._show_hidden_var,
                        command=self._apply_filter).pack(side="right", padx=8, pady=6)

        # ── Main pane ─────────────────────────────────────────────────────────
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=0)

        # Game list table
        list_frame = ctk.CTkFrame(main, fg_color=COL_PANEL, corner_radius=0)
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        cols = ("name", "genre", "developer", "releasedate", "rating", "players", "hidden", "favorite")
        self._tree = ttk.Treeview(list_frame, columns=cols, show="headings", selectmode="extended")
        col_widths = {"name": 260, "genre": 120, "developer": 140,
                      "releasedate": 90, "rating": 90, "players": 60,
                      "hidden": 56, "favorite": 60}
        for col in cols:
            w = col_widths.get(col, 100)
            self._tree.heading(col, text=col.title(),
                               command=lambda c=col: self._sort_by(c))
            self._tree.column(col, width=w, anchor="center" if col in ("rating", "hidden", "favorite", "players") else "w")

        # Row tags
        self._tree.tag_configure("hidden", foreground=COL_HIDDEN)
        self._tree.tag_configure("favorite", foreground=COL_FAV)
        self._tree.tag_configure("hidden_fav", foreground="#8b7a30")

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self._tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.bind("<Double-1>", self._on_double_click)
        self._tree.bind("<Return>", self._on_double_click)
        self._tree.bind("<Delete>", lambda e: self._delete_selected())
        self._tree.bind("<Control-Prior>", self._page_up)
        self._tree.bind("<Control-Next>", self._page_down)
        self._tree.bind("<Control-End>", self._select_last)
        self._tree.bind("<Control-Home>", self._select_first)
        self._tree.bind("h", self._on_toggle_hidden)
        self._tree.bind("H", self._on_toggle_hidden)
        self._tree.bind("u", lambda e: self._bulk_set_flag("hidden", False))
        self._tree.bind("U", lambda e: self._bulk_set_flag("hidden", False))
        self._tree.bind("f", self._on_toggle_favorite)
        self._tree.bind("F", self._on_toggle_favorite)
        self._tree.bind("g", lambda e: self._bulk_set_flag("favorite", False))
        self._tree.bind("G", lambda e: self._bulk_set_flag("favorite", False))

        # Right panel — preview + quick edit
        right = ctk.CTkFrame(main, fg_color=COL_PANEL, corner_radius=0, width=310)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_propagate(False)

        ctk.CTkLabel(right, text="Preview", font=("", 13, "bold")).pack(pady=(10, 4))

        self._preview_label = ctk.CTkLabel(right, text="No selection", width=260, height=260)
        self._preview_label.pack(padx=10)

        self._info_box = ctk.CTkTextbox(
            right,
            state="disabled",
            font=("", 11),
            fg_color=COL_PANEL,
            text_color=COL_TEXT,
            wrap="word",
        )
        self._info_box.pack(fill="both", expand=True, padx=8, pady=6)

        ctk.CTkButton(right, text="Edit…", fg_color=COL_ACCENT, command=self._edit_selected).pack(pady=4)
        ctk.CTkButton(right, text="Scrape This Game", fg_color=COL_HIGHLIGHT,
                      command=self._scrape_selected, state="disabled").pack(pady=2)
        

        # ── Status bar ────────────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="No gamelist loaded.")
        status = ctk.CTkLabel(self, textvariable=self._status_var, anchor="w",
                              font=("", 11), text_color=COL_MUTED)
        status.grid(row=2, column=0, sticky="ew", padx=10, pady=2)

    def _show_tools_menu(self, event):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Settings…", command=self._open_settings)
        menu.add_command(label="Set Name from Filename", command=self._set_name_from_filename)
        menu.add_command(label="Batch Favorite by Names", command=self._batch_favorite)
        menu.add_command(label="Detect and Hide Duplicates", command=self._detect_duplicates)
        menu.add_command(label="Detect and Hide Bad Versions", command=self._detect_bad_versions)
        menu.add_command(label="Review Hidden & Favorites", command=self._review_hidden_favorites)
        menu.add_separator()
        menu.add_command(label="Manage Folder Icons…", command=self._manage_folder_icons)
        menu.post(event.x_root, event.y_root)

    # ── File operations ───────────────────────────────────────────────────────

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="Open gamelist.xml",
            initialdir=settings.get("last_gamelist_dir", os.path.expanduser("~")),
            filetypes=[("GameList XML", "gamelist.xml"), ("XML files", "*.xml"), ("All", "*.*")]
        )
        
        if path:
            self._load_gamelist(path)

    def _load_gamelist(self, path: str):
        try:
            logger.info(f"Opening gamelist: {path}")
            gl = GameList(path)
            gl.load()
            self._gamelist = gl
            # Update window title to include the file (truncated)
            try:
                self._set_title_with_path(path)
            except Exception:
                pass
            settings.set("last_gamelist_dir", os.path.dirname(path))
            settings.add_recent(path)
            self._update_recent_menu()
            self._apply_filter()
            self._status(f"Loaded {len(gl)} entries from {path}")
            logger.info(f"Loaded gamelist with {len(gl)} entries from {path}")
            try:
                show_toast(self, f"Opened {os.path.basename(path)}")
            except Exception:
                pass
        except Exception as e:
            logger.exception(f"Failed to load gamelist from {path}")
            tb = traceback.format_exc()
            show_error_dialog(self, "Load Error", str(e), tb)

    def _reload(self):
        if self._gamelist:
            self._load_gamelist(self._gamelist.xml_path)
            try:
                show_toast(self, "Reloaded gamelist from disk")
            except Exception:
                pass

    def _save(self):
        if not self._gamelist:
            return
        try:
            logger.info(f"Saving gamelist to {self._gamelist.xml_path}")
            self._gamelist.save(backup=True)
            self._status(f"Saved — backup created")
            logger.info(f"Saved gamelist to {self._gamelist.xml_path} with backup")
            logger.debug("Save operation completed successfully")
            
            show_toast(self, "File saved successfully.")
        except Exception as e:
            logger.exception("Failed to save gamelist")
            tb = traceback.format_exc()
            show_error_dialog(self, "Save Error", str(e), tb)

    def _save_as(self):
        if not self._gamelist:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xml",
            filetypes=[("XML", "*.xml")],
            initialfile="gamelist.xml",
        )
        if path:
            logger.info(f"Saving gamelist as {path}")
            self._gamelist.save_as(path)
            self._status(f"Saved as {path}")
            logger.debug(f"Save-As operation completed to {path}")
            try:
                show_toast(self, f"Saved as {os.path.basename(path)}")
            except Exception:
                pass

    # ── Table population ──────────────────────────────────────────────────────

    def _apply_filter(self, *_):
        if not self._gamelist:
            return
        selected_iids = set(self._tree.selection()) if hasattr(self, '_tree') else set()
        query = self._filter_var.get().lower()
        show_hidden = self._show_hidden_var.get()

        games = self._gamelist.games
        if not show_hidden:
            games = [g for g in games if not g.hidden]
        if query:
            games = [g for g in games if query in g.name.lower() or query in g.get("genre").lower()
                     or query in g.get("developer").lower()]

        # Sort
        rev = self._sort_rev
        col = self._sort_col
        try:
            if col == "favorite":
                # Sort by favorite first (True first), then by name
                games = sorted(games, key=lambda g: (0 if g.favorite else 1, g.name.lower()), reverse=rev)
            else:
                games = sorted(games, key=lambda g: g.get(col, "").lower(), reverse=rev)
        except Exception:
            pass

        self._filtered_games = games
        self._populate_tree(games)
        if selected_iids:
            valid = [iid for iid in selected_iids if self._tree.exists(iid)]
            if valid:
                self._tree.selection_set(valid)
                self._tree.focus(valid[0])
                self._tree.see(valid[0])

    def _populate_tree(self, games: list[Game]):
        self._tree.delete(*self._tree.get_children())
        for g in games:
            tag = ""
            if g.hidden and g.favorite:
                tag = "hidden_fav"
            elif g.hidden:
                tag = "hidden"
            elif g.favorite:
                tag = "favorite"

            self._tree.insert(
                "", "end",
                iid=id(g),
                values=(
                    ("[H] " if g.hidden else "") + g.name,
                    g.get("genre"),
                    g.get("developer"),
                    g.get("releasedate", "")[:10],
                    format_rating(g.get("rating")),
                    g.get("players"),
                    "✓" if g.hidden else "",
                    "★" if g.favorite else "",
                ),
                tags=(tag,),
            )
        self._status(f"{len(games)} games" + (" (filtered)" if self._filter_var.get() else ""))

    def _sort_by(self, col: str):
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = False
        self._apply_filter()

    # ── Selection helpers ─────────────────────────────────────────────────────

    def _selected_game_objects(self) -> list[Game]:
        iids = self._tree.selection()
        iid_set = {int(i) for i in iids}
        return [g for g in self._filtered_games if id(g) in iid_set]

    def _select_all(self):
        self._tree.selection_set(self._tree.get_children())

    def _invert_selection(self):
        all_iids = set(self._tree.get_children())
        sel = set(self._tree.selection())
        self._tree.selection_set(list(all_iids - sel))

    def _page_up(self, event=None):
        self._tree.yview_scroll(-1, "pages")
        visible = self._tree.identify_row(0)  # First visible row
        if visible:
            self._tree.selection_set(visible)
            self._tree.focus(visible)

    def _page_down(self, event=None):
        self._tree.yview_scroll(1, "pages")
        visible = self._tree.identify_row(self._tree.winfo_height() - 10)  # Approximate last visible
        if visible:
            self._tree.selection_set(visible)
            self._tree.focus(visible)

    def _select_first(self, event=None):
        children = self._tree.get_children()
        if children:
            self._tree.selection_set(children[0])
            self._tree.focus(children[0])
            self._tree.see(children[0])

    def _select_last(self, event=None):
        children = self._tree.get_children()
        if children:
            self._tree.selection_set(children[-1])
            self._tree.focus(children[-1])
            self._tree.see(children[-1])

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_select(self, event=None):
        sel = self._selected_game_objects()
        if not sel:
            return
        logger.debug(f"Selected {len(sel)} game(s): {[g.name for g in sel]}")
        g = sel[0]
        # Update preview
        img_raw = g.get("image")
        abs_img = self._gamelist.resolve_media_path(img_raw) if self._gamelist else None
        self._preview_img = None
        self._preview_label.configure(text="")
        if abs_img:
            self._preview_img = load_thumbnail(abs_img, 240, 240)
            if self._preview_img:
                self._preview_label.configure(image=self._preview_img)
            else:
                self._preview_label.configure(image=None)
        # Info box
        desc = g.get("desc") or ""
        info = (
            f"Name:   {g.name}\n"
            f"Genre:  {g.get('genre')}\n"
            f"Dev:    {g.get('developer')}\n"
            f"Pub:    {g.get('publisher')}\n"
            f"Year:   {g.get('releasedate', '')[:10]}\n"
            f"Rating: {format_rating(g.get('rating'))}\n"
            f"Hidden: {g.hidden} | Fav: {g.favorite}\n\n"
            f"{desc}"
        )
        self._info_box.configure(state="normal")
        self._info_box.delete("1.0", "end")
        self._info_box.insert("1.0", info)
        self._info_box.configure(state="disabled")

    def _on_double_click(self, event=None):
        self._edit_selected()

    def _edit_selected(self):
        sel = self._selected_game_objects()
        if not sel or not self._gamelist:
            return
        dlg = GameEditDialog(self, sel[0], self._gamelist)
        self.wait_window(dlg)
        self._apply_filter()

    # ── Bulk actions ──────────────────────────────────────────────────────────

    def _bulk_set_flag(self, field: str, value: bool):
        sel = self._selected_game_objects()
        if not sel:
            return
        changed = []
        for g in sel:
            new_val = "true" if value else "false"
            old_val = g.get(field, "false")
            if old_val != new_val:
                g.set(field, new_val)
                changed.append(g)
                logger.debug(f"Bulk update {field} for {g.name} ({g.path}): {old_val} -> {new_val}")
            else:
                logger.debug(f"Bulk update {field} skipped for {g.name} ({g.path}); already {new_val}")
        self._apply_filter()
        self._restore_tree_focus()
        self._status(f"Set {field}={'true' if value else 'false'} on {len(changed)} games")
        logger.info(f"Bulk set {field}={'true' if value else 'false'} for {len(changed)} selected game(s)")

    def _toggle_flag(self, field: str):
        sel = self._selected_game_objects()
        if not sel:
            return
        changed = []
        for g in sel:
            current = g.get(field, "false").lower() in ("true", "1", "yes")
            new_val = "false" if current else "true"
            g.set(field, new_val)
            changed.append((g, current, new_val))
            logger.debug(f"Toggled {field} for {g.name} ({g.path}): {current} -> {new_val}")
        self._apply_filter()
        self._restore_tree_focus()
        self._status(f"Toggled {field} for {len(changed)} games")
        logger.info(f"Toggled {field} for {len(changed)} selected game(s)")

    def _on_toggle_hidden(self, event=None):
        self._toggle_flag("hidden")
        return "break"

    def _on_toggle_favorite(self, event=None):
        self._toggle_flag("favorite")
        return "break"

    def _restore_tree_focus(self):
        selection = self._tree.selection()
        if selection:
            self._tree.focus(selection[0])
            self._tree.see(selection[0])
        self._tree.focus_set()

    def _confirm_exit(self):
        if not self._gamelist or not self._gamelist.has_unsaved_changes():
            self.destroy()
            return

        result = messagebox.askyesnocancel(
            "Unsaved changes",
            "There are unsaved changes. Save before exiting?",
            parent=self,
        )
        if result is True:
            try:
                self._save()
                if not self._gamelist.has_unsaved_changes():
                    self.destroy()
            except Exception:
                pass
        elif result is False:
            self.destroy()
        else:
            # Cancel: do nothing
            return

    def _delete_selected(self):
        sel = self._selected_game_objects()
        if not sel:
            return
        names = [g.name for g in sel]
        logger.info(f"Deleting {len(sel)} selected game(s): {names}")
        if not messagebox.askyesno(
            "Delete entries",
            f"Remove {len(sel)} entries from the gamelist?\n(Files on disk are NOT deleted.)"
        ):
            logger.debug("Delete cancelled by user")
            return
        self._gamelist.remove_games(sel)
        self._apply_filter()
        self._status(f"Deleted {len(sel)} entries")
        logger.info(f"Deleted {len(sel)} games from gamelist")
        try:
            show_toast(self, f"Deleted {len(sel)} entries")
        except Exception:
            pass

    def _add_manual(self):
        if not self._gamelist:
            messagebox.showinfo("No gamelist", "Open a gamelist.xml first.")
            return
        logger.info("Adding new manual game entry")
        g = self._gamelist.add_game({"path": "./newgame", "name": "New Game"})
        dlg = GameEditDialog(self, g, self._gamelist)
        self.wait_window(dlg)
        self._apply_filter()
        logger.info(f"Manual game added: {g.name} ({g.path})")
        try:
            show_toast(self, "Added new game")
        except Exception:
            pass

    def _set_name_from_filename(self):
        sel = self._selected_game_objects()
        if not sel:
            logger.warning("No games selected for setting name from filename")
            return
        for g in sel:
            path = g.path
            if path:
                filename = os.path.basename(path)
                name_without_ext = os.path.splitext(filename)[0]
                g.set("name", name_without_ext)
        self._apply_filter()
        self._status(f"Set name from filename for {len(sel)} games")
        logger.info(f"Set name from filename for {len(sel)} games")
        try:
            show_toast(self, f"Updated names for {len(sel)} games")
        except Exception:
            pass

    def _batch_favorite(self):
        if not self._gamelist:
            logger.warning("No gamelist loaded for batch favorite")
            messagebox.showinfo("No gamelist", "Open a gamelist.xml first.")
            return
        try:
            try:
                show_toast(self, "Opening Batch Favorite dialog")
            except Exception:
                pass
            dlg = BatchFavoriteDialog(self)
            self.wait_window(dlg)
            logger.info("Batch favorite dialog opened")
            try:
                show_toast(self, "Batch Favorite finished")
            except Exception:
                pass
        except Exception:
            logger.exception("Error during batch favorite")

    def _detect_duplicates(self):
        if not self._gamelist:
            messagebox.showinfo("No gamelist", "Open a gamelist.xml first.")
            return
        try:
            try:
                show_toast(self, "Detecting duplicates")
            except Exception:
                pass
            dlg = DetectDuplicatesDialog(self)
            self.wait_window(dlg)
            try:
                show_toast(self, "Detect duplicates finished")
            except Exception:
                pass
        except Exception:
            logger.exception("Error in duplicate detection")

    def _detect_bad_versions(self):
        if not self._gamelist:
            messagebox.showinfo("No gamelist", "Open a gamelist.xml first.")
            return
        try:
            try:
                show_toast(self, "Detecting bad versions")
            except Exception:
                pass
            dlg = DetectBadVersionsDialog(self)
            self.wait_window(dlg)
            try:
                show_toast(self, "Detect bad versions finished")
            except Exception:
                pass
        except Exception:
            logger.exception("Error detecting bad versions")

    def _review_hidden_favorites(self):
        if not self._gamelist:
            messagebox.showinfo("No gamelist", "Open a gamelist.xml first.")
            return
        try:
            try:
                show_toast(self, "Reviewing hidden & favorites")
            except Exception:
                pass
            dlg = ReviewHiddenFavoritesDialog(self)
            self.wait_window(dlg)
            try:
                show_toast(self, "Review finished")
            except Exception:
                pass
        except Exception:
            logger.exception("Error reviewing hidden & favorites")

    def _manage_folder_icons(self):
        if not self._gamelist:
            messagebox.showinfo("No gamelist", "Open a gamelist.xml first.")
            return
        try:
            try:
                show_toast(self, "Opening Folder Icons manager")
            except Exception:
                pass
            dlg = FolderIconManagerDialog(self)
            self.wait_window(dlg)
            try:
                show_toast(self, "Folder icons manager closed")
            except Exception:
                pass
        except Exception:
            logger.exception("Error in folder icon manager")

    # ── ROM Scanner ───────────────────────────────────────────────────────────

    def _scan_roms(self):
        if not self._gamelist:
            messagebox.showinfo("No gamelist", "Open a gamelist.xml first.")
            return
        def on_add(count):
            self._apply_filter()
            self._status(f"Added {count} ROMs to gamelist (not saved yet)")
        RomScannerDialog(self, self._gamelist, on_add_cb=on_add)
        try:
            show_toast(self, "ROM scan started")
        except Exception:
            pass

    # ── Scraper ───────────────────────────────────────────────────────────────

    def _pick_platform(self) -> str | None:
        dlg = ctk.CTkToplevel(self)
        dlg.title("Select Platform")
        dlg.geometry("340x160")
        dlg.transient(self)
        center_window(dlg, self)
        dlg.grab_set()
        result = {"value": None}

        ctk.CTkLabel(dlg, text="Platform:").pack(pady=(16, 4))
        var = ctk.StringVar(value=SCRAPER_PLATFORMS[0])
        combo = ctk.CTkComboBox(dlg, values=SCRAPER_PLATFORMS, variable=var, width=280)
        combo.pack(pady=4)

        def ok():
            result["value"] = var.get()
            dlg.destroy()

        ctk.CTkButton(dlg, text="OK", fg_color=COL_HIGHLIGHT, command=ok).pack(pady=10)
        self.wait_window(dlg)
        return result["value"]

    def _scrape_selected(self):
        sel = self._selected_game_objects()
        if not sel or not self._gamelist:
            return
        binary = find_skyscraper_bin()
        if not binary:
            messagebox.showerror("Skyscraper not found",
                                 "Set the Skyscraper binary path in Settings.")
            return
        platform = self._pick_platform()
        if not platform:
            return
        roms_dir = self._gamelist.base_dir

        # Write credentials if set
        user = settings.get("screenscraper_user", "")
        pw = settings.get("screenscraper_pass", "")
        if user and pw:
            write_skyscraper_credentials(user, pw)

        for g in sel:
            rom_abs = self._gamelist.resolve_media_path(g.path) or os.path.join(roms_dir, g.path.lstrip("./"))
            try:
                cmd = build_skyscraper_command(platform, rom_abs, roms_dir)
                ScraperDialog(self, cmd, title=f"Scraping — {g.name}")
                try:
                    show_toast(self, f"Scraping: {g.name}")
                except Exception:
                    pass
            except FileNotFoundError as e:
                messagebox.showerror("Error", str(e))
                return

    def _scrape_bulk(self):
        if not self._gamelist:
            return
        binary = find_skyscraper_bin()
        if not binary:
            messagebox.showerror("Skyscraper not found",
                                 "Set the Skyscraper binary path in Settings.")
            return
        platform = self._pick_platform()
        if not platform:
            return
        roms_dir = self._gamelist.base_dir

        user = settings.get("screenscraper_user", "")
        pw = settings.get("screenscraper_pass", "")
        if user and pw:
            write_skyscraper_credentials(user, pw)

        try:
            cmd = build_skyscraper_bulk_command(platform, roms_dir)
            ScraperDialog(self, cmd, title=f"Bulk Scrape — {platform}")
            try:
                show_toast(self, "Bulk scrape started")
            except Exception:
                pass
        except FileNotFoundError as e:
            messagebox.showerror("Error", str(e))

    # ── Settings ──────────────────────────────────────────────────────────────

    def _open_settings(self):
        try:
            SettingsDialog(self)
            try:
                show_toast(self, "Settings opened")
            except Exception:
                pass
        except Exception:
            logger.exception("Failed to open settings dialog")

    # ── Status bar helper ─────────────────────────────────────────────────────

    def _status(self, msg: str):
        self._status_var.set(msg)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
