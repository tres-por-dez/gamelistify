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
import customtkinter as ctk
from PIL import Image, ImageTk

from settings import settings
from gamelist_parser import GameList, Game
from config import GAME_FIELDS, BOOL_FIELDS, MEDIA_FIELDS, SCRAPER_PLATFORMS
from rom_scanner import scan_roms, diff_against_gamelist
from scraper_bridge import (
    ScraperJob, build_skyscraper_bulk_command,
    build_skyscraper_command, write_skyscraper_credentials, find_skyscraper_bin,
)

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
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


def format_rating(raw: str) -> str:
    try:
        v = float(raw)
        stars = int(round(v * 5))
        return "★" * stars + "☆" * (5 - stars)
    except Exception:
        return raw or ""


# ── Settings Dialog ───────────────────────────────────────────────────────────

class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("540x420")
        self.resizable(False, False)
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
        try:
            settings.set("image_preview_size", int(self._prev_var.get()))
        except ValueError:
            pass
        user = self._user_var.get()
        pw = self._pass_var.get()
        if user and pw:
            write_skyscraper_credentials(user, pw)
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
        self.grab_set()
        self._vars: dict[str, tk.Variable] = {}
        self._thumb_img = None
        self._build()
        self._populate()

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
        if abs_path:
            self._thumb_img = load_thumbnail(abs_path, 220, 220)
            if self._thumb_img:
                self._thumb_label.configure(image=self._thumb_img, text="")
                return
        self._thumb_label.configure(image=None, text="No image")

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
        for field, var in self._vars.items():
            if isinstance(var, tuple) and var[0] == "textbox":
                val = var[1].get("1.0", "end").strip()
            elif isinstance(var, ctk.BooleanVar) or isinstance(var, tk.BooleanVar):
                val = "true" if var.get() else "false"
            else:
                val = var.get().strip()
            self.game.set(field, val)
        self.destroy()


# ── Scraper Log Dialog ────────────────────────────────────────────────────────

class ScraperDialog(ctk.CTkToplevel):
    def __init__(self, parent, cmd: list[str], title="Scraping..."):
        super().__init__(parent)
        self.title(title)
        self.geometry("700x440")
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
        self._build_menu()
        self._build_ui()

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
        fm.add_command(label="Exit", command=self.quit)

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
        sm.add_command(label="Scrape Selected…", command=self._scrape_selected)
        sm.add_command(label="Scrape All (bulk)…", command=self._scrape_bulk)

        vm = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=vm)
        vm.add_command(label="Scan ROMs…", command=self._scan_roms)

        om = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=om)
        om.add_command(label="Settings…", command=self._open_settings)

        self.bind("<Control-o>", lambda e: self._open_file())
        self.bind("<Control-s>", lambda e: self._save())
        self.bind("<Control-a>", lambda e: self._select_all())

    def _update_recent_menu(self):
        self._recent_menu.delete(0, "end")
        for path in settings.get("recent_files", []):
            self._recent_menu.add_command(
                label=path, command=lambda p=path: self._load_gamelist(p))

    # ── UI Layout ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Top toolbar ───────────────────────────────────────────────────────
        toolbar = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color=COL_HEADER)
        toolbar.grid(row=0, column=0, sticky="ew", columnspan=2)
        toolbar.grid_propagate(False)

        ctk.CTkButton(toolbar, text="⊕ Open", width=80, command=self._open_file).pack(side="left", padx=4, pady=6)
        ctk.CTkButton(toolbar, text="💾 Save", width=80, fg_color=COL_ACCENT, command=self._save).pack(side="left", padx=2, pady=6)
        ctk.CTkButton(toolbar, text="🔄 Reload", width=80, fg_color=COL_ACCENT, command=self._reload).pack(side="left", padx=2, pady=6)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8, pady=4)

        ctk.CTkButton(toolbar, text="👁 Hide", width=70, command=lambda: self._bulk_set_flag("hidden", True)).pack(side="left", padx=2, pady=6)
        ctk.CTkButton(toolbar, text="👁 Unhide", width=80, command=lambda: self._bulk_set_flag("hidden", False)).pack(side="left", padx=2, pady=6)
        ctk.CTkButton(toolbar, text="⭐ Fav", width=70, command=lambda: self._bulk_set_flag("favorite", True)).pack(side="left", padx=2, pady=6)
        ctk.CTkButton(toolbar, text="🗑 Delete", width=80, fg_color="#6b1a1a", command=self._delete_selected).pack(side="left", padx=2, pady=6)

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8, pady=4)

        ctk.CTkButton(toolbar, text="🎮 Scan ROMs", width=100, command=self._scan_roms).pack(side="left", padx=2, pady=6)
        ctk.CTkButton(toolbar, text="🕹 Scrape Sel.", width=100, command=self._scrape_selected).pack(side="left", padx=2, pady=6)
        ctk.CTkButton(toolbar, text="🕹 Scrape All", width=100, command=self._scrape_bulk).pack(side="left", padx=2, pady=6)

        # Search / filter
        ctk.CTkLabel(toolbar, text="Filter:").pack(side="right", padx=(4, 2))
        self._filter_var = ctk.StringVar()
        self._filter_var.trace_add("write", lambda *_: self._apply_filter())
        ctk.CTkEntry(toolbar, textvariable=self._filter_var, width=180).pack(side="right", padx=(0, 8), pady=6)

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

        # Right panel — preview + quick edit
        right = ctk.CTkFrame(main, fg_color=COL_PANEL, corner_radius=0, width=260)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_propagate(False)

        ctk.CTkLabel(right, text="Preview", font=("", 13, "bold")).pack(pady=(10, 4))

        self._preview_label = ctk.CTkLabel(right, text="No selection", width=240, height=240)
        self._preview_label.pack(padx=10)

        self._info_box = ctk.CTkTextbox(right, height=160, state="disabled", font=("", 11))
        self._info_box.pack(fill="x", padx=8, pady=6)

        ctk.CTkButton(right, text="Edit…", fg_color=COL_ACCENT, command=self._edit_selected).pack(pady=4)
        ctk.CTkButton(right, text="Scrape This Game", fg_color=COL_HIGHLIGHT,
                      command=self._scrape_selected).pack(pady=2)

        # ── Status bar ────────────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="No gamelist loaded.")
        status = ctk.CTkLabel(self, textvariable=self._status_var, anchor="w",
                              font=("", 11), text_color=COL_MUTED)
        status.grid(row=2, column=0, sticky="ew", padx=10, pady=2)

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
            gl = GameList(path)
            gl.load()
            self._gamelist = gl
            settings.set("last_gamelist_dir", os.path.dirname(path))
            settings.add_recent(path)
            self._update_recent_menu()
            self._apply_filter()
            self._status(f"Loaded {len(gl)} entries from {path}")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def _reload(self):
        if self._gamelist:
            self._load_gamelist(self._gamelist.xml_path)

    def _save(self):
        if not self._gamelist:
            return
        try:
            self._gamelist.save(backup=True)
            self._status(f"Saved — backup written to {self._gamelist.xml_path}.bak")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def _save_as(self):
        if not self._gamelist:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xml",
            filetypes=[("XML", "*.xml")],
            initialfile="gamelist.xml",
        )
        if path:
            self._gamelist.save_as(path)
            self._status(f"Saved as {path}")

    # ── Table population ──────────────────────────────────────────────────────

    def _apply_filter(self, *_):
        if not self._gamelist:
            return
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
            games = sorted(games, key=lambda g: g.get(col, "").lower(), reverse=rev)
        except Exception:
            pass

        self._filtered_games = games
        self._populate_tree(games)

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
                    ("👁 " if g.hidden else "") + g.name,
                    g.get("genre"),
                    g.get("developer"),
                    g.get("releasedate", "")[:10],
                    format_rating(g.get("rating")),
                    g.get("players"),
                    "✓" if g.hidden else "",
                    "⭐" if g.favorite else "",
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

    # ── Event handlers ────────────────────────────────────────────────────────

    def _on_select(self, event=None):
        sel = self._selected_game_objects()
        if not sel:
            return
        g = sel[0]
        # Update preview
        img_raw = g.get("image")
        abs_img = self._gamelist.resolve_media_path(img_raw) if self._gamelist else None
        if abs_img:
            self._preview_img = load_thumbnail(abs_img, 240, 240)
            self._preview_label.configure(image=self._preview_img, text="")
        else:
            self._preview_label.configure(image=None, text="No image")
        # Info box
        info = (
            f"Name:   {g.name}\n"
            f"Genre:  {g.get('genre')}\n"
            f"Dev:    {g.get('developer')}\n"
            f"Pub:    {g.get('publisher')}\n"
            f"Year:   {g.get('releasedate', '')[:10]}\n"
            f"Rating: {format_rating(g.get('rating'))}\n"
            f"Hidden: {g.hidden} | Fav: {g.favorite}\n\n"
            + (g.get("desc")[:200] + "…" if len(g.get("desc")) > 200 else g.get("desc"))
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
        for g in sel:
            g.set(field, "true" if value else "false")
        self._apply_filter()
        self._status(f"Set {field}={'true' if value else 'false'} on {len(sel)} games")

    def _delete_selected(self):
        sel = self._selected_game_objects()
        if not sel:
            return
        if not messagebox.askyesno(
            "Delete entries",
            f"Remove {len(sel)} entries from the gamelist?\n(Files on disk are NOT deleted.)"
        ):
            return
        self._gamelist.remove_games(sel)
        self._apply_filter()
        self._status(f"Deleted {len(sel)} entries")

    def _add_manual(self):
        if not self._gamelist:
            messagebox.showinfo("No gamelist", "Open a gamelist.xml first.")
            return
        # Create a blank game and open the editor
        g = self._gamelist.add_game({"path": "./newgame", "name": "New Game"})
        dlg = GameEditDialog(self, g, self._gamelist)
        self.wait_window(dlg)
        self._apply_filter()

    # ── ROM Scanner ───────────────────────────────────────────────────────────

    def _scan_roms(self):
        if not self._gamelist:
            messagebox.showinfo("No gamelist", "Open a gamelist.xml first.")
            return
        def on_add(count):
            self._apply_filter()
            self._status(f"Added {count} ROMs to gamelist (not saved yet)")
        RomScannerDialog(self, self._gamelist, on_add_cb=on_add)

    # ── Scraper ───────────────────────────────────────────────────────────────

    def _pick_platform(self) -> str | None:
        dlg = ctk.CTkToplevel(self)
        dlg.title("Select Platform")
        dlg.geometry("340x160")
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
        except FileNotFoundError as e:
            messagebox.showerror("Error", str(e))

    # ── Settings ──────────────────────────────────────────────────────────────

    def _open_settings(self):
        SettingsDialog(self)

    # ── Status bar helper ─────────────────────────────────────────────────────

    def _status(self, msg: str):
        self._status_var.set(msg)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
