"""
main_qt.py — Gamelistify PySide6 frontend.
Drop-in replacement for main.py. All backend modules are shared.
"""
import os
import sys

from PySide6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel,
    QSize, QThread, Signal, QObject, QTimer,
)
from PySide6.QtGui import (
    QPixmap, QColor, QFont, QAction, QKeySequence,
    QIcon, QPainter, QBrush,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter,
    QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QTableView, QHeaderView, QAbstractItemView,
    QLabel, QLineEdit, QTextEdit, QCheckBox, QComboBox,
    QPushButton, QToolBar, QStatusBar, QDialog,
    QDialogButtonBox, QFileDialog, QMessageBox,
    QScrollArea, QFrame, QSizePolicy, QProgressBar,
    QGroupBox, QSpinBox, QMenu, QMenuBar, QTabWidget,
    QListWidget, QListWidgetItem, QPlainTextEdit,
)

from settings import settings
from gamelist_parser import GameList, Game
from config import GAME_FIELDS, BOOL_FIELDS, MEDIA_FIELDS, SCRAPER_PLATFORMS
from rom_scanner import scan_roms, diff_against_gamelist
from scraper_bridge import (
    ScraperJob, build_skyscraper_bulk_command,
    build_skyscraper_command, write_skyscraper_credentials, find_skyscraper_bin,
)

# ── Palette ────────────────────────────────────────────────────────────────────

QSS = """
QMainWindow, QDialog, QWidget {
    background-color: #0f1923;
    color: #dce3ec;
    font-family: "Segoe UI", "Inter", "Helvetica Neue", sans-serif;
    font-size: 13px;
}

/* ── Toolbar ── */
QToolBar {
    background-color: #0a1520;
    border-bottom: 1px solid #1e3050;
    padding: 4px 6px;
    spacing: 4px;
}
QToolBar QToolButton {
    background-color: #162030;
    color: #dce3ec;
    border: 1px solid #1e3050;
    border-radius: 5px;
    padding: 5px 12px;
    font-size: 12px;
}
QToolBar QToolButton:hover  { background-color: #1e3050; }
QToolBar QToolButton:pressed { background-color: #0d2540; }

/* ── MenuBar ── */
QMenuBar {
    background-color: #0a1520;
    color: #dce3ec;
    border-bottom: 1px solid #1e3050;
    padding: 2px 0;
}
QMenuBar::item:selected { background-color: #1e3050; border-radius: 3px; }
QMenu {
    background-color: #111f30;
    color: #dce3ec;
    border: 1px solid #1e3050;
    border-radius: 6px;
    padding: 4px 0;
}
QMenu::item { padding: 6px 28px 6px 16px; }
QMenu::item:selected { background-color: #1e3050; }
QMenu::separator { height: 1px; background: #1e3050; margin: 4px 0; }

/* ── Table ── */
QTableView {
    background-color: #0d1a27;
    alternate-background-color: #111f2e;
    color: #dce3ec;
    gridline-color: #1a2d42;
    border: none;
    selection-background-color: #1a4060;
    selection-color: #ffffff;
    outline: none;
}
QTableView::item { padding: 4px 8px; border: none; }
QTableView::item:selected { background-color: #1a4060; }
QHeaderView::section {
    background-color: #0a1520;
    color: #8aafcc;
    border: none;
    border-right: 1px solid #1e3050;
    border-bottom: 1px solid #1e3050;
    padding: 6px 10px;
    font-weight: 600;
    font-size: 12px;
    letter-spacing: 0.03em;
}
QHeaderView::section:hover { background-color: #162030; color: #dce3ec; }
QHeaderView::section:checked { background-color: #1a4060; }

/* ── Scrollbars ── */
QScrollBar:vertical {
    background: #0d1a27;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #2a4a6a;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #3a6a9a; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #0d1a27;
    height: 8px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #2a4a6a;
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover { background: #3a6a9a; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Inputs ── */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background-color: #111f2e;
    color: #dce3ec;
    border: 1px solid #1e3050;
    border-radius: 5px;
    padding: 5px 8px;
    selection-background-color: #1a4060;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #3a7ab8;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #111f2e;
    color: #dce3ec;
    border: 1px solid #1e3050;
    selection-background-color: #1a4060;
}
QSpinBox::up-button, QSpinBox::down-button { background: #162030; border: none; }

/* ── Buttons ── */
QPushButton {
    background-color: #162a40;
    color: #dce3ec;
    border: 1px solid #1e3050;
    border-radius: 5px;
    padding: 6px 16px;
    font-size: 13px;
}
QPushButton:hover  { background-color: #1e3a54; border-color: #2a5a80; }
QPushButton:pressed { background-color: #0d2030; }
QPushButton:disabled { color: #3a5060; border-color: #1a2a3a; }

QPushButton#btn_accent {
    background-color: #c0392b;
    color: #ffffff;
    border: none;
}
QPushButton#btn_accent:hover { background-color: #e04030; }

QPushButton#btn_primary {
    background-color: #1a4a7a;
    color: #ffffff;
    border: none;
}
QPushButton#btn_primary:hover { background-color: #2a5a9a; }

QPushButton#btn_success {
    background-color: #1a6a3a;
    color: #ffffff;
    border: none;
}
QPushButton#btn_success:hover { background-color: #2a8a4a; }

/* ── GroupBox ── */
QGroupBox {
    border: 1px solid #1e3050;
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 8px;
    color: #8aafcc;
    font-weight: 600;
    font-size: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 10px;
}

/* ── CheckBox ── */
QCheckBox { color: #dce3ec; spacing: 6px; }
QCheckBox::indicator {
    width: 15px; height: 15px;
    border: 1px solid #2a4a6a;
    border-radius: 3px;
    background: #111f2e;
}
QCheckBox::indicator:checked {
    background: #1a4a7a;
    border-color: #3a7ab8;
    image: none;
}

/* ── Splitter ── */
QSplitter::handle {
    background-color: #1e3050;
    width: 2px;
    height: 2px;
}
QSplitter::handle:hover { background-color: #3a7ab8; }

/* ── Status bar ── */
QStatusBar {
    background-color: #0a1520;
    color: #5a8aaa;
    border-top: 1px solid #1e3050;
    font-size: 12px;
    padding: 2px 8px;
}

/* ── Dialogs ── */
QDialogButtonBox QPushButton { min-width: 80px; }

/* ── Tab ── */
QTabWidget::pane {
    border: 1px solid #1e3050;
    border-radius: 0 6px 6px 6px;
    background-color: #0f1923;
}
QTabBar::tab {
    background-color: #0a1520;
    color: #5a8aaa;
    border: 1px solid #1e3050;
    border-bottom: none;
    border-radius: 5px 5px 0 0;
    padding: 6px 16px;
    margin-right: 2px;
}
QTabBar::tab:selected { background-color: #0f1923; color: #dce3ec; }
QTabBar::tab:hover    { background-color: #162030; color: #dce3ec; }

/* ── Frames / panels ── */
QFrame#side_panel {
    background-color: #0a1520;
    border-left: 1px solid #1e3050;
}
QFrame#preview_frame {
    background-color: #0d1a27;
    border: 1px solid #1e3050;
    border-radius: 6px;
}
QLabel#preview_img {
    background-color: #0d1a27;
    border-radius: 4px;
}
"""

# ── Colour roles for row painting ─────────────────────────────────────────────
COL_HIDDEN  = QColor("#3a3a5a")
COL_FAV     = QColor("#4a3a00")
COL_HIDDEN_TEXT = QColor("#6060a0")
COL_FAV_TEXT    = QColor("#e8c84a")
COL_NORMAL_TEXT = QColor("#dce3ec")
COL_MUTED_TEXT  = QColor("#5a8aaa")


# ── Table model ───────────────────────────────────────────────────────────────

COLUMNS = [
    ("name",        "Name",       280),
    ("genre",       "Genre",      120),
    ("developer",   "Developer",  150),
    ("releasedate", "Year",        70),
    ("rating",      "Rating",      90),
    ("players",     "Players",     60),
    ("hidden",      "Hidden",      60),
    ("favorite",    "Fav",         50),
]
COL_KEYS   = [c[0] for c in COLUMNS]
COL_LABELS = [c[1] for c in COLUMNS]
COL_WIDTHS = [c[2] for c in COLUMNS]


def _rating_stars(raw: str) -> str:
    try:
        v = float(raw)
        n = int(round(v * 5))
        return "★" * n + "☆" * (5 - n)
    except Exception:
        return raw or ""


class GameListModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self._games: list[Game] = []

    def set_games(self, games: list[Game]):
        self.beginResetModel()
        self._games = games
        self.endResetModel()

    def game_at(self, row: int) -> Game:
        return self._games[row]

    def rowCount(self, parent=QModelIndex()):
        return len(self._games)

    def columnCount(self, parent=QModelIndex()):
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return COL_LABELS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        g = self._games[index.row()]
        col = COL_KEYS[index.column()]

        if role == Qt.DisplayRole:
            if col == "hidden":
                return "●" if g.hidden else ""
            if col == "favorite":
                return "★" if g.favorite else ""
            if col == "rating":
                return _rating_stars(g.get("rating"))
            if col == "releasedate":
                return g.get("releasedate", "")[:4]
            if col == "name":
                prefix = "⊘ " if g.hidden else ""
                return prefix + g.name
            return g.get(col, "")

        if role == Qt.ForegroundRole:
            if g.hidden and g.favorite:
                return QBrush(QColor("#806a20"))
            if g.hidden:
                return QBrush(COL_HIDDEN_TEXT)
            if g.favorite:
                return QBrush(COL_FAV_TEXT)
            if col in ("hidden", "favorite", "rating"):
                return QBrush(COL_MUTED_TEXT)
            return QBrush(COL_NORMAL_TEXT)

        if role == Qt.BackgroundRole:
            if g.hidden:
                return QBrush(COL_HIDDEN)
            if g.favorite:
                return QBrush(COL_FAV)
            return None

        if role == Qt.TextAlignmentRole:
            if col in ("hidden", "favorite", "rating", "players", "releasedate"):
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        if role == Qt.UserRole:
            return g

        return None

    def flags(self, index):
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable


# ── Proxy model for filtering ─────────────────────────────────────────────────

class GameFilterProxy(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self._query = ""
        self._show_hidden = True
        self.setSortCaseSensitivity(Qt.CaseInsensitive)

    def set_query(self, q: str):
        self._query = q.lower()
        self.invalidateFilter()

    def set_show_hidden(self, v: bool):
        self._show_hidden = v
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        model: GameListModel = self.sourceModel()
        g = model.game_at(source_row)
        if not self._show_hidden and g.hidden:
            return False
        if self._query:
            haystack = (g.name + g.get("genre") + g.get("developer")).lower()
            return self._query in haystack
        return True


# ── Worker for scraper ────────────────────────────────────────────────────────

class ScraperWorker(QObject):
    line_ready = Signal(str)
    finished   = Signal(int)

    def __init__(self, cmd: list[str]):
        super().__init__()
        self._cmd = cmd
        self._job: ScraperJob | None = None

    def run(self):
        self._job = ScraperJob(
            self._cmd,
            progress_cb=lambda line: self.line_ready.emit(line),
            done_cb=lambda rc: self.finished.emit(rc),
        )
        self._job.run()

    def cancel(self):
        if self._job:
            self._job.cancel()


# ── Settings dialog ───────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(520, 340)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Skyscraper
        grp1 = QGroupBox("Skyscraper")
        f1 = QFormLayout(grp1)
        f1.setSpacing(8)
        self._sky_edit = QLineEdit(settings.get("skyscraper_bin", ""))
        btn_browse = QPushButton("Browse…")
        btn_browse.setFixedWidth(80)
        btn_browse.clicked.connect(self._browse_sky)
        row_sky = QHBoxLayout()
        row_sky.addWidget(self._sky_edit)
        row_sky.addWidget(btn_browse)
        f1.addRow("Binary path:", row_sky)
        layout.addWidget(grp1)

        # ScreenScraper
        grp2 = QGroupBox("ScreenScraper credentials")
        f2 = QFormLayout(grp2)
        f2.setSpacing(8)
        self._user_edit = QLineEdit(settings.get("screenscraper_user", ""))
        self._pass_edit = QLineEdit(settings.get("screenscraper_pass", ""))
        self._pass_edit.setEchoMode(QLineEdit.Password)
        f2.addRow("Username:", self._user_edit)
        f2.addRow("Password:", self._pass_edit)
        layout.addWidget(grp2)

        # Preview size
        grp3 = QGroupBox("Interface")
        f3 = QFormLayout(grp3)
        f3.setSpacing(8)
        self._prev_spin = QSpinBox()
        self._prev_spin.setRange(120, 600)
        self._prev_spin.setValue(settings.get("image_preview_size", 280))
        self._prev_spin.setSuffix(" px")
        f3.addRow("Preview image size:", self._prev_spin)
        layout.addWidget(grp3)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _browse_sky(self):
        path, _ = QFileDialog.getOpenFileName(self, "Locate Skyscraper binary")
        if path:
            self._sky_edit.setText(path)

    def _save(self):
        settings.set("skyscraper_bin", self._sky_edit.text())
        settings.set("screenscraper_user", self._user_edit.text())
        settings.set("screenscraper_pass", self._pass_edit.text())
        settings.set("image_preview_size", self._prev_spin.value())
        user = self._user_edit.text()
        pw   = self._pass_edit.text()
        if user and pw:
            write_skyscraper_credentials(user, pw)
        self.accept()


# ── Game edit dialog ──────────────────────────────────────────────────────────

class GameEditDialog(QDialog):
    def __init__(self, parent, game: Game, gamelist: GameList):
        super().__init__(parent)
        self.game = game
        self.gamelist = gamelist
        self.setWindowTitle(f"Edit — {game.name}")
        self.resize(900, 640)
        self._widgets: dict = {}
        self._preview_pix: QPixmap | None = None
        self._build()
        self._populate()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left: scrollable form ──────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setSpacing(8)
        form.setContentsMargins(16, 16, 16, 16)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Text / numeric fields
        text_fields = [f for f in GAME_FIELDS if f not in BOOL_FIELDS and f not in MEDIA_FIELDS]
        for field in text_fields:
            if field == "desc":
                w = QTextEdit()
                w.setFixedHeight(90)
            else:
                w = QLineEdit()
            form.addRow(field + ":", w)
            self._widgets[field] = w

        # Bool checkboxes in a row
        bool_row = QHBoxLayout()
        for field in sorted(BOOL_FIELDS):
            cb = QCheckBox(field)
            bool_row.addWidget(cb)
            self._widgets[field] = cb
        bool_row.addStretch()
        form.addRow("Flags:", bool_row)

        # Media path fields
        for field in sorted(MEDIA_FIELDS):
            edit = QLineEdit()
            btn  = QPushButton("…")
            btn.setFixedWidth(28)
            btn.clicked.connect(lambda checked=False, f=field, e=edit: self._browse_media(f, e))
            row = QHBoxLayout()
            row.addWidget(edit)
            row.addWidget(btn)
            row.setSpacing(4)
            container = QWidget()
            container.setLayout(row)
            form.addRow(field + ":", container)
            self._widgets[field] = edit

        scroll.setWidget(form_widget)
        root.addWidget(scroll, stretch=3)

        # ── Right: preview panel ───────────────────────────────────────────────
        right = QFrame()
        right.setObjectName("side_panel")
        right.setFixedWidth(260)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)

        self._preview = QLabel()
        self._preview.setObjectName("preview_img")
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setFixedSize(236, 236)
        self._preview.setText("No image")
        right_layout.addWidget(self._preview)

        btn_refresh = QPushButton("Refresh preview")
        btn_refresh.clicked.connect(self._refresh_preview)
        right_layout.addWidget(btn_refresh)

        right_layout.addWidget(QLabel("Orphan media:"))
        self._orphan_list = QPlainTextEdit()
        self._orphan_list.setReadOnly(True)
        self._orphan_list.setFixedHeight(120)
        right_layout.addWidget(self._orphan_list)

        btn_scan = QPushButton("Scan orphan media")
        btn_scan.clicked.connect(self._scan_orphans)
        right_layout.addWidget(btn_scan)
        right_layout.addStretch()

        root.addWidget(right, stretch=0)

        # ── Bottom buttons ─────────────────────────────────────────────────────
        btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addLayout(root)
        outer.addWidget(btn_box)
        # Replace the dialog's layout
        self.setLayout(outer)

    def _populate(self):
        for field, w in self._widgets.items():
            val = self.game.get(field)
            if isinstance(w, QTextEdit):
                w.setPlainText(val)
            elif isinstance(w, QCheckBox):
                w.setChecked(val.lower() in ("true", "1", "yes"))
            elif isinstance(w, QLineEdit):
                w.setText(val)
        self._refresh_preview()

    def _refresh_preview(self):
        img_raw = ""
        if "image" in self._widgets:
            img_raw = self._widgets["image"].text()
        if not img_raw:
            img_raw = self.game.get("image")
        abs_path = self.gamelist.resolve_media_path(img_raw)
        if abs_path:
            pix = QPixmap(abs_path)
            if not pix.isNull():
                pix = pix.scaled(236, 236, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._preview.setPixmap(pix)
                return
        self._preview.clear()
        self._preview.setText("No image")

    def _browse_media(self, field: str, edit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(
            self, f"Select {field}", "",
            "Images / Video (*.png *.jpg *.jpeg *.webp *.gif *.mp4 *.avi);;All (*.*)"
        )
        if path:
            try:
                rel = os.path.relpath(path, self.gamelist.base_dir)
                edit.setText("./" + rel.replace(os.sep, "/"))
            except ValueError:
                edit.setText(path)
            if field == "image":
                self._refresh_preview()

    def _scan_orphans(self):
        found = self.gamelist.find_orphan_media(self.game)
        if found:
            self._orphan_list.setPlainText("\n".join(found.keys()))
        else:
            self._orphan_list.setPlainText("(none found)")

    def _save(self):
        for field, w in self._widgets.items():
            if isinstance(w, QTextEdit):
                val = w.toPlainText().strip()
            elif isinstance(w, QCheckBox):
                val = "true" if w.isChecked() else "false"
            elif isinstance(w, QLineEdit):
                val = w.text().strip()
            else:
                continue
            self.game.set(field, val)
        self.accept()


# ── Scraper log dialog ────────────────────────────────────────────────────────

class ScraperDialog(QDialog):
    def __init__(self, parent, cmd: list[str], title="Scraping…"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 460)
        self._cmd = cmd
        self._thread: QThread | None = None
        self._worker: ScraperWorker | None = None
        self._build()
        QTimer.singleShot(100, self._start)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        cmd_label = QLabel(" ".join(self._cmd[:5]) + " …")
        cmd_label.setStyleSheet("color: #5a8aaa; font-size: 11px;")
        layout.addWidget(cmd_label)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Courier New", 10))
        layout.addWidget(self._log)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # indeterminate
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(
            "QProgressBar { background: #1e3050; border: none; border-radius: 2px; }"
            "QProgressBar::chunk { background: #3a7ab8; border-radius: 2px; }"
        )
        layout.addWidget(self._progress)

        self._status = QLabel("Running…")
        self._status.setStyleSheet("color: #5a8aaa; font-size: 12px;")
        layout.addWidget(self._status)

        row = QHBoxLayout()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("btn_accent")
        self._cancel_btn.clicked.connect(self._cancel)
        self._close_btn  = QPushButton("Close")
        self._close_btn.setObjectName("btn_primary")
        self._close_btn.clicked.connect(self.accept)
        self._close_btn.setEnabled(False)
        row.addStretch()
        row.addWidget(self._cancel_btn)
        row.addWidget(self._close_btn)
        layout.addLayout(row)

    def _start(self):
        self._worker = ScraperWorker(self._cmd)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.line_ready.connect(self._append)
        self._worker.finished.connect(self._done)
        self._thread.start()

    def _append(self, line: str):
        self._log.appendPlainText(line)

    def _done(self, rc: int):
        self._progress.setRange(0, 1)
        self._progress.setValue(1)
        if rc == 0:
            self._status.setText("✓ Completed successfully")
            self._status.setStyleSheet("color: #44cc88; font-size: 12px;")
        else:
            self._status.setText(f"✗ Finished with errors (exit code {rc})")
            self._status.setStyleSheet("color: #e04030; font-size: 12px;")
        self._cancel_btn.setEnabled(False)
        self._close_btn.setEnabled(True)
        if self._thread:
            self._thread.quit()

    def _cancel(self):
        if self._worker:
            self._worker.cancel()
        self._status.setText("Cancelled")
        self._status.setStyleSheet("color: #5a8aaa; font-size: 12px;")
        self._cancel_btn.setEnabled(False)
        self._close_btn.setEnabled(True)
        self._progress.setRange(0, 1)
        self._progress.setValue(0)

    def closeEvent(self, event):
        self._cancel()
        super().closeEvent(event)


# ── ROM scanner dialog ────────────────────────────────────────────────────────

class RomScannerDialog(QDialog):
    def __init__(self, parent, gamelist: GameList, on_add_cb):
        super().__init__(parent)
        self.gamelist = gamelist
        self.on_add_cb = on_add_cb
        self.setWindowTitle("Scan ROMs")
        self.resize(780, 520)
        self._results: list[dict] = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        top = QHBoxLayout()
        top.addWidget(QLabel("ROM directory:"))
        self._dir_edit = QLineEdit(self.gamelist.base_dir)
        top.addWidget(self._dir_edit, stretch=1)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse)
        btn_scan = QPushButton("Scan")
        btn_scan.setObjectName("btn_primary")
        btn_scan.clicked.connect(self._scan)
        top.addWidget(btn_browse)
        top.addWidget(btn_scan)
        layout.addLayout(top)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color: #5a8aaa; font-size: 12px;")
        layout.addWidget(self._count_label)

        # Table
        self._table = QTableView()
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setDefaultSectionSize(24)
        self._table.verticalHeader().hide()
        self._model = _RomScanModel()
        self._table.setModel(self._model)
        self._table.setColumnWidth(0, 260)
        layout.addWidget(self._table)

        btns = QHBoxLayout()
        btn_all  = QPushButton("Select All")
        btn_none = QPushButton("Select None")
        btn_add  = QPushButton("Add Selected to Gamelist")
        btn_add.setObjectName("btn_success")
        btn_all.clicked.connect(self._table.selectAll)
        btn_none.clicked.connect(self._table.clearSelection)
        btn_add.clicked.connect(self._add_selected)
        btns.addWidget(btn_all)
        btns.addWidget(btn_none)
        btns.addStretch()
        btns.addWidget(btn_add)
        layout.addLayout(btns)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "ROM directory", self._dir_edit.text())
        if d:
            self._dir_edit.setText(d)

    def _scan(self):
        all_roms = scan_roms(self._dir_edit.text())
        self._results = diff_against_gamelist(all_roms, self.gamelist)
        self._model.set_roms(self._results)
        self._count_label.setText(
            f"{len(self._results)} new ROM(s) found (not in gamelist)")

    def _add_selected(self):
        indexes = self._table.selectedIndexes()
        rows = sorted({i.row() for i in indexes})
        if not rows:
            QMessageBox.information(self, "Nothing selected", "Select at least one ROM.")
            return
        for row in rows:
            r = self._results[row]
            self.gamelist.add_game({"path": r["path"], "name": r["name"]})
        self.on_add_cb(len(rows))
        self.accept()


class _RomScanModel(QAbstractTableModel):
    _headers = ["Name", "Path"]

    def __init__(self):
        super().__init__()
        self._roms: list[dict] = []

    def set_roms(self, roms):
        self.beginResetModel()
        self._roms = roms
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):    return len(self._roms)
    def columnCount(self, parent=QModelIndex()): return 2
    def headerData(self, s, o, r=Qt.DisplayRole):
        if o == Qt.Horizontal and r == Qt.DisplayRole:
            return self._headers[s]
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid(): return None
        r = self._roms[index.row()]
        if role == Qt.DisplayRole:
            return r["name"] if index.column() == 0 else r["path"]
        if role == Qt.ForegroundRole:
            return QBrush(COL_NORMAL_TEXT)
        return None


# ── Platform picker ───────────────────────────────────────────────────────────

class PlatformPickerDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Select platform")
        self.setFixedSize(340, 120)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(QLabel("Platform:"))
        self._combo = QComboBox()
        self._combo.addItems(SCRAPER_PLATFORMS)
        layout.addWidget(self._combo)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def platform(self) -> str:
        return self._combo.currentText()


# ── Side panel ────────────────────────────────────────────────────────────────

class SidePanel(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("side_panel")
        self.setMinimumWidth(200)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Preview image
        self._preview = QLabel()
        self._preview.setObjectName("preview_img")
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setMinimumSize(180, 180)
        self._preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._preview.setText("No selection")
        self._preview.setStyleSheet(
            "background: #0d1a27; border: 1px solid #1e3050; border-radius: 6px;"
            "color: #3a5a7a;"
        )
        layout.addWidget(self._preview)

        # Info box
        self._info = QPlainTextEdit()
        self._info.setReadOnly(True)
        self._info.setFont(QFont("Courier New", 10))
        self._info.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._info)

        # Buttons
        self._btn_edit = QPushButton("Edit…")
        self._btn_edit.setObjectName("btn_primary")
        self._btn_scrape = QPushButton("Scrape this game")
        layout.addWidget(self._btn_edit)
        layout.addWidget(self._btn_scrape)

    def update_game(self, game: Game | None, gamelist: GameList | None):
        if game is None or gamelist is None:
            self._preview.clear()
            self._preview.setText("No selection")
            self._info.clear()
            return

        # Image
        abs_img = gamelist.resolve_media_path(game.get("image"))
        if abs_img:
            pix = QPixmap(abs_img)
            if not pix.isNull():
                w = self._preview.width() or 240
                pix = pix.scaled(w, w, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self._preview.setPixmap(pix)
            else:
                self._preview.setText("No image")
        else:
            self._preview.clear()
            self._preview.setText("No image")

        # Info
        desc = game.get("desc")
        if len(desc) > 220:
            desc = desc[:220] + "…"
        info = (
            f"Name:   {game.name}\n"
            f"Genre:  {game.get('genre')}\n"
            f"Dev:    {game.get('developer')}\n"
            f"Pub:    {game.get('publisher')}\n"
            f"Year:   {game.get('releasedate', '')[:4]}\n"
            f"Rating: {_rating_stars(game.get('rating'))}\n"
            f"Hidden: {game.hidden}  Fav: {game.favorite}\n"
            f"\n{desc}"
        )
        self._info.setPlainText(info)


# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gamelistify — RetroBat / EmulationStation")
        self.resize(1400, 820)
        self._gamelist: GameList | None = None
        self._src_model  = GameListModel()
        self._proxy      = GameFilterProxy()
        self._proxy.setSourceModel(self._src_model)
        self._proxy.setSortRole(Qt.DisplayRole)
        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()

    # ── Menu ──────────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()

        fm = mb.addMenu("&File")
        self._act_open   = fm.addAction("Open gamelist.xml…",    self._open_file, QKeySequence.Open)
        self._act_save   = fm.addAction("Save",                  self._save,      QKeySequence.Save)
        self._act_saveas = fm.addAction("Save As…",              self._save_as)
        fm.addSeparator()
        fm.addAction("Reload from disk", self._reload)
        fm.addSeparator()
        self._recent_menu = fm.addMenu("Recent Files")
        self._update_recent_menu()
        fm.addSeparator()
        fm.addAction("Exit", self.close, QKeySequence.Quit)

        em = mb.addMenu("&Edit")
        em.addAction("Select All",       self._select_all,       QKeySequence.SelectAll)
        em.addAction("Invert Selection", self._invert_selection)
        em.addSeparator()
        em.addAction("Hide Selected",     lambda: self._bulk_flag("hidden",   True))
        em.addAction("Unhide Selected",   lambda: self._bulk_flag("hidden",   False))
        em.addAction("Favorite Selected", lambda: self._bulk_flag("favorite", True))
        em.addAction("Unfavorite Selected",lambda: self._bulk_flag("favorite",False))
        em.addSeparator()
        em.addAction("Delete Selected Entries…", self._delete_selected)
        em.addAction("Add Game Manually…",       self._add_manual)

        sm = mb.addMenu("&Scrape")
        sm.addAction("Scrape Selected…",  self._scrape_selected)
        sm.addAction("Scrape All (bulk)…",self._scrape_bulk)

        vm = mb.addMenu("&View")
        vm.addAction("Scan ROMs…", self._scan_roms)

        tm = mb.addMenu("&Tools")
        tm.addAction("Settings…", self._open_settings)

    def _update_recent_menu(self):
        self._recent_menu.clear()
        for path in settings.get("recent_files", []):
            self._recent_menu.addAction(path, lambda p=path: self._load_gamelist(p))

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        self.addToolBar(tb)

        def _btn(label, slot, obj_name=None, tooltip=None):
            b = QPushButton(label)
            if obj_name:
                b.setObjectName(obj_name)
            if tooltip:
                b.setToolTip(tooltip)
            b.clicked.connect(slot)
            tb.addWidget(b)
            return b

        _btn("Open",   self._open_file)
        _btn("Save",   self._save,    "btn_primary")
        _btn("Reload", self._reload)
        tb.addSeparator()
        _btn("Hide",     lambda: self._bulk_flag("hidden",   True))
        _btn("Unhide",   lambda: self._bulk_flag("hidden",   False))
        _btn("Fav ★",   lambda: self._bulk_flag("favorite", True))
        _btn("Unfav",    lambda: self._bulk_flag("favorite", False))
        _btn("Delete",   self._delete_selected, "btn_accent")
        tb.addSeparator()
        _btn("Scan ROMs",   self._scan_roms)
        _btn("Scrape Sel.", self._scrape_selected)
        _btn("Scrape All",  self._scrape_bulk)
        tb.addSeparator()

        # Show hidden toggle
        self._chk_hidden = QCheckBox("Show hidden")
        self._chk_hidden.setChecked(True)
        self._chk_hidden.stateChanged.connect(
            lambda s: self._proxy.set_show_hidden(bool(s)))
        tb.addWidget(self._chk_hidden)
        tb.addSeparator()

        # Search
        tb.addWidget(QLabel("  Filter:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("name / genre / developer…")
        self._search.setFixedWidth(220)
        self._search.textChanged.connect(self._proxy.set_query)
        tb.addWidget(self._search)

    # ── Central widget ────────────────────────────────────────────────────────

    def _build_central(self):
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)

        # ── Game table ────────────────────────────────────────────────────────
        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setWordWrap(False)
        self._table.verticalHeader().hide()
        self._table.verticalHeader().setDefaultSectionSize(26)
        self._table.horizontalHeader().setSortIndicatorShown(True)
        self._table.horizontalHeader().setHighlightSections(False)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._context_menu)

        # Column widths
        for i, w in enumerate(COL_WIDTHS):
            self._table.setColumnWidth(i, w)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        # Signals
        self._table.selectionModel().selectionChanged.connect(self._on_select)
        self._table.doubleClicked.connect(self._on_double_click)

        # Delete key
        from PySide6.QtGui import QShortcut
        QShortcut(QKeySequence.Delete, self._table, self._delete_selected)

        splitter.addWidget(self._table)

        # ── Side panel ────────────────────────────────────────────────────────
        self._side = SidePanel()
        self._side._btn_edit.clicked.connect(self._edit_selected)
        self._side._btn_scrape.clicked.connect(self._scrape_selected)
        splitter.addWidget(self._side)

        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([1050, 280])

        self.setCentralWidget(splitter)

    def _build_statusbar(self):
        self._status = QStatusBar()
        self._status.showMessage("No gamelist loaded.")
        self.setStatusBar(self._status)

    # ── File ops ──────────────────────────────────────────────────────────────

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open gamelist.xml",
            settings.get("last_gamelist_dir", os.path.expanduser("~")),
            "GameList XML (gamelist.xml);;XML (*.xml);;All (*.*)"
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
            self._refresh_table()
            self._status.showMessage(f"Loaded {len(gl)} entries — {path}")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    def _reload(self):
        if self._gamelist:
            self._load_gamelist(self._gamelist.xml_path)

    def _save(self):
        if not self._gamelist:
            return
        try:
            self._gamelist.save(backup=True)
            self._status.showMessage(
                f"Saved — backup at {self._gamelist.xml_path}.bak")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _save_as(self):
        if not self._gamelist:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save As", "gamelist.xml", "XML (*.xml)")
        if path:
            self._gamelist.save_as(path)
            self._status.showMessage(f"Saved as {path}")

    # ── Table refresh ─────────────────────────────────────────────────────────

    def _refresh_table(self):
        if not self._gamelist:
            return
        self._src_model.set_games(list(self._gamelist.games))
        count = self._proxy.rowCount()
        self._status.showMessage(f"{len(self._gamelist)} games loaded")

    # ── Selection ─────────────────────────────────────────────────────────────

    def _proxy_selected_games(self) -> list[Game]:
        rows = {idx.row() for idx in self._table.selectedIndexes()}
        games = []
        for row in sorted(rows):
            src_idx = self._proxy.mapToSource(self._proxy.index(row, 0))
            g = self._src_model.game_at(src_idx.row())
            games.append(g)
        return games

    def _select_all(self):
        self._table.selectAll()

    def _invert_selection(self):
        sel_model = self._table.selectionModel()
        all_rows = set(range(self._proxy.rowCount()))
        sel_rows = {i.row() for i in self._table.selectedIndexes()}
        self._table.clearSelection()
        for r in all_rows - sel_rows:
            self._table.selectRow(r)

    # ── Events ────────────────────────────────────────────────────────────────

    def _on_select(self):
        games = self._proxy_selected_games()
        if games:
            self._side.update_game(games[0], self._gamelist)

    def _on_double_click(self, index):
        self._edit_selected()

    def _context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("Edit…",             self._edit_selected)
        menu.addSeparator()
        menu.addAction("Hide",              lambda: self._bulk_flag("hidden",   True))
        menu.addAction("Unhide",            lambda: self._bulk_flag("hidden",   False))
        menu.addAction("Favorite",          lambda: self._bulk_flag("favorite", True))
        menu.addAction("Unfavorite",        lambda: self._bulk_flag("favorite", False))
        menu.addSeparator()
        menu.addAction("Delete entries…",   self._delete_selected)
        menu.addSeparator()
        menu.addAction("Scrape selected…",  self._scrape_selected)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    # ── Bulk actions ──────────────────────────────────────────────────────────

    def _edit_selected(self):
        games = self._proxy_selected_games()
        if not games or not self._gamelist:
            return
        dlg = GameEditDialog(self, games[0], self._gamelist)
        if dlg.exec():
            self._src_model.layoutChanged.emit()
            self._side.update_game(games[0], self._gamelist)

    def _bulk_flag(self, field: str, value: bool):
        games = self._proxy_selected_games()
        if not games:
            return
        for g in games:
            g.set(field, "true" if value else "false")
        self._src_model.layoutChanged.emit()
        self._status.showMessage(
            f"Set {field}={'true' if value else 'false'} on {len(games)} game(s)")

    def _delete_selected(self):
        games = self._proxy_selected_games()
        if not games:
            return
        reply = QMessageBox.question(
            self, "Delete entries",
            f"Remove {len(games)} entr{'y' if len(games)==1 else 'ies'} from the gamelist?\n"
            "(Files on disk are NOT deleted.)",
            QMessageBox.Yes | QMessageBox.Cancel
        )
        if reply != QMessageBox.Yes:
            return
        self._gamelist.remove_games(games)
        self._refresh_table()
        self._status.showMessage(f"Deleted {len(games)} entr{'y' if len(games)==1 else 'ies'}")

    def _add_manual(self):
        if not self._gamelist:
            QMessageBox.information(self, "No gamelist", "Open a gamelist.xml first.")
            return
        g = self._gamelist.add_game({"path": "./newgame", "name": "New Game"})
        dlg = GameEditDialog(self, g, self._gamelist)
        if dlg.exec():
            self._refresh_table()
        else:
            self._gamelist.remove_game(g)

    # ── ROM scanner ───────────────────────────────────────────────────────────

    def _scan_roms(self):
        if not self._gamelist:
            QMessageBox.information(self, "No gamelist", "Open a gamelist.xml first.")
            return
        def on_add(count):
            self._refresh_table()
            self._status.showMessage(f"Added {count} ROM(s) — not saved yet")
        RomScannerDialog(self, self._gamelist, on_add).exec()

    # ── Scraper ───────────────────────────────────────────────────────────────

    def _pick_platform(self) -> str | None:
        dlg = PlatformPickerDialog(self)
        return dlg.platform() if dlg.exec() else None

    def _ensure_sky(self) -> bool:
        if not find_skyscraper_bin():
            QMessageBox.critical(
                self, "Skyscraper not found",
                "Set the Skyscraper binary path in Tools → Settings.")
            return False
        user = settings.get("screenscraper_user", "")
        pw   = settings.get("screenscraper_pass", "")
        if user and pw:
            write_skyscraper_credentials(user, pw)
        return True

    def _scrape_selected(self):
        games = self._proxy_selected_games()
        if not games or not self._gamelist:
            return
        if not self._ensure_sky():
            return
        platform = self._pick_platform()
        if not platform:
            return
        roms_dir = self._gamelist.base_dir
        for g in games:
            rom_abs = (self._gamelist.resolve_media_path(g.path)
                       or os.path.join(roms_dir, g.path.lstrip("./")))
            try:
                cmd = build_skyscraper_command(platform, rom_abs, roms_dir)
                ScraperDialog(self, cmd, f"Scraping — {g.name}").exec()
            except FileNotFoundError as e:
                QMessageBox.critical(self, "Error", str(e))
                return

    def _scrape_bulk(self):
        if not self._gamelist:
            return
        if not self._ensure_sky():
            return
        platform = self._pick_platform()
        if not platform:
            return
        try:
            cmd = build_skyscraper_bulk_command(platform, self._gamelist.base_dir)
            ScraperDialog(self, cmd, f"Bulk Scrape — {platform}").exec()
        except FileNotFoundError as e:
            QMessageBox.critical(self, "Error", str(e))

    # ── Settings ──────────────────────────────────────────────────────────────

    def _open_settings(self):
        SettingsDialog(self).exec()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    app.setApplicationName("Gamelistify")
    app.setApplicationVersion("1.0.0")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())