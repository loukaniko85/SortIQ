#!/usr/bin/env python3
"""
SortIQ v1.3 — Intelligent media sorting & renaming. Amber on obsidian.
"""

import sys
import base64
import os
import json
import shutil
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QListWidgetItem, QLabel, QFileDialog,
    QMessageBox, QProgressBar, QComboBox, QLineEdit, QTextEdit,
    QCheckBox, QDialog, QInputDialog, QFrame, QSizePolicy,
    QAbstractItemView, QStackedWidget, QMenu, QRadioButton,
    QButtonGroup, QToolButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QTabWidget, QGroupBox, QTreeWidget,
    QTreeWidgetItem, QScrollArea,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QFileSystemWatcher
from PyQt6.QtGui import (
    QDragEnterEvent, QDropEvent, QColor, QPalette, QFont,
    QPainter, QBrush, QAction,
)

# ── Settings persistence ──────────────────────────────────────────────────────
SETTINGS_PATH = Path.home() / ".sortiq" / "settings.json"

def load_settings() -> dict:
    # Migrate settings from old ~/.mediarenamer path (pre-SortIQ installs)
    _old_path = Path.home() / ".mediarenamer" / "settings.json"
    if not SETTINGS_PATH.exists() and _old_path.exists():
        try:
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            import shutil as _shutil
            _shutil.copy2(_old_path, SETTINGS_PATH)
        except Exception:
            pass
    try:
        if SETTINGS_PATH.exists():
            return json.loads(SETTINGS_PATH.read_text())
    except Exception:
        pass
    return {}

def save_settings(data: dict):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Write with owner-only permissions (0o600) so API keys are not world-readable.
    # Use os.open to set mode atomically on creation; on existing files chmod after.
    text = json.dumps(data, indent=2)
    fd = os.open(str(SETTINGS_PATH), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)

_s = load_settings()
for _env, _key in [
    ("TMDB_API_KEY",          "tmdb_api_key"),
    ("TVDB_API_KEY",          "tvdb_api_key"),
    ("OPENSUBTITLES_API_KEY", "opensubtitles_api_key"),
]:
    if _s.get(_key):
        os.environ.setdefault(_env, _s[_key])

try:
    from core.matcher import MediaMatcher
    from core.renamer import FileRenamer
    from core.subtitle_fetcher import SubtitleFetcher
    from core.history import RenameHistory
    from core.presets import PresetManager
    from core.artwork import ArtworkDownloader
    from core.metadata_writer import MetadataWriter
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from core.matcher import MediaMatcher
    from core.renamer import FileRenamer
    from core.subtitle_fetcher import SubtitleFetcher
    from core.history import RenameHistory
    from core.presets import PresetManager
    from core.artwork import ArtworkDownloader
    from core.metadata_writer import MetadataWriter

from core.nfo_writer import NFOWriter
from core.duplicate_finder import scan_directory_for_duplicates, find_exact_duplicates, human_size, wasted_space

# ── Embedded app icon ────────────────────────────────────────────────────────
_ICON_B64 = "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAB80lEQVR4nO2bQW7DIBBFf6vuLHWbo/QC3aWn6AmiHqTyCXqKdtcL9CjZVvK+mxBhCoYhg5kB3i4L45nHMJYCAINB19zlPrh8TJ+cgXAwvS4v1GdIAiQmHSJVRrIAN/nDaTpSgyrNeV6+7N8pEqIC7MQlJu2DImJTgMbkbWwRIQn3oYe1Jw+s4w71r6AA3yAaicXvFWBsaU/eYPLwVcE/Aa0l7+JKiC6BWpznhXW80ISKFQDwS/CxEiCx/M/zwibC1wtEV4BNqWpQIwAoI0GVAIBfwkPNl+di4jicppvHUlcBNhwToloARwWQloAUOBI3kARwvjhGqLy5Y1C1BEpMgBoBpapPfA8ovexEV8AePUesgL0arlgBezEE1A6gNqSvwPfb70+pQHJ4fn98unWM7itgCKgdQG1IPYBjzUmj+wpoTgD1X6LmBAA0CU0KANI3VJoVYIhJaF4AsC2hCwFAWILKjZFcLvEfAVzPDnVTAQ7X3e9eBfRZAZe/2VZnCMVujORC3VDpogK2Jq55AbGqFb8xkkvqcl1VgDlP6x421kYoeZOXfW64uSVAbdRBAdqrwMU3+4BHQM61E814K6CVXmAIzT6Q0AO0S9hKHtgQYD+gVUIseYB4ZwiQdY44RMpVGcO4NUZ5gZZ7g5QvWfc3Rwe98wf568dEIlGvAAAAAABJRU5ErkJggg=="

def _app_icon():
    """Return a QIcon from the embedded base64 PNG."""
    from PyQt6.QtGui import QPixmap, QIcon
    from PyQt6.QtCore import QByteArray
    data = QByteArray(base64.b64decode(_ICON_B64))
    pm = QPixmap(); pm.loadFromData(data, "PNG")
    return QIcon(pm)

# ── Palette ───────────────────────────────────────────────────────────────────
C_BG        = "#0A0C12"
C_SURFACE   = "#11141D"
C_PANEL     = "#161923"
C_BORDER    = "#252A38"
C_BORDER2   = "#1E2330"
C_AMBER     = "#F59E0B"
C_AMBER_DIM = "#92600A"
C_AMBER_GLO = "#FCD34D"
C_TEXT      = "#E8EAF0"
C_TEXT_DIM  = "#6B7280"
C_TEXT_MID  = "#9CA3AF"
C_SUCCESS   = "#10B981"
C_ERROR     = "#EF4444"
C_BLUE      = "#3B82F6"
C_BLUE_DIM  = "#1D4ED8"
C_GREEN     = "#22C55E"
C_GREEN_DIM = "#15803D"

STYLESHEET = """
QMainWindow, QWidget { background: #0A0C12; color: #E8EAF0;
    font-family: "Segoe UI","SF Pro Display","Helvetica Neue",sans-serif; font-size: 13px; }

/* ── Base button ── */
QPushButton { background: #11141D; color: #9CA3AF; border: 1px solid #252A38;
    border-radius: 6px; padding: 7px 16px; font-size: 12px; font-weight: 500; }
QPushButton:hover { background: #161923; color: #E8EAF0; border-color: #92600A; }
QPushButton:pressed { background: #0A0C12; }
QPushButton:disabled { color: #252A38; border-color: #1E2330; }

/* ── Match button — vivid blue ── */
QPushButton#match {
    background: #3B82F6; color: #FFFFFF; border: none;
    font-weight: 700; font-size: 13px; padding: 9px 24px;
    border-radius: 7px; letter-spacing: 0.3px; }
QPushButton#match:hover { background: #60A5FA; }
QPushButton#match:pressed { background: #1D4ED8; }
QPushButton#match:disabled { background: #1e3a5f; color: #3a5a8a; }

/* ── Rename button — vivid green ── */
QPushButton#rename {
    background: #22C55E; color: #FFFFFF; border: none;
    font-weight: 700; font-size: 13px; padding: 9px 24px;
    border-radius: 7px; letter-spacing: 0.3px; }
QPushButton#rename:hover { background: #4ADE80; }
QPushButton#rename:pressed { background: #15803D; }
QPushButton#rename:disabled { background: #14532d; color: #166534; }

/* ── Ghost button ── */
QPushButton#ghost { background: transparent; color: #6B7280; border: 1px solid #1E2330;
    border-radius: 6px; padding: 6px 14px; font-size: 12px; }
QPushButton#ghost:hover { color: #F59E0B; border-color: #92600A; background: rgba(245,158,11,0.06); }

/* ── Danger button ── */
QPushButton#danger { background: transparent; color: #EF4444;
    border: 1px solid rgba(239,68,68,0.3); border-radius: 6px; padding: 6px 14px; }
QPushButton#danger:hover { background: rgba(239,68,68,0.1); border-color: #EF4444; }

/* ── Icon button ── */
QPushButton#icon_btn { background: transparent; border: none; color: #6B7280;
    padding: 4px 8px; border-radius: 4px; font-size: 14px; }
QPushButton#icon_btn:hover { color: #F59E0B; background: rgba(245,158,11,0.08); }

/* ── Dry-run button ── */
QPushButton#dryrun { background: rgba(245,158,11,0.1); color: #F59E0B;
    border: 1px solid #92600A; border-radius: 6px; padding: 7px 16px; font-size: 12px; font-weight: 600; }
QPushButton#dryrun:hover { background: rgba(245,158,11,0.18); }
QPushButton#dryrun:disabled { color: #92600A; background: rgba(245,158,11,0.04); }

/* ── Inputs ── */
QLineEdit { background: #11141D; color: #E8EAF0; border: 1px solid #252A38;
    border-radius: 6px; padding: 7px 10px; selection-background-color: #92600A; }
QLineEdit:focus { border-color: #F59E0B; background: #161923; }
QLineEdit:disabled { color: #6B7280; background: #0A0C12; }
QLineEdit#search { padding-left: 28px; }

QComboBox { background: #11141D; color: #E8EAF0; border: 1px solid #252A38;
    border-radius: 6px; padding: 6px 10px; min-width: 130px; }
QComboBox:hover { border-color: #92600A; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow { border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid #6B7280; margin-right: 6px; }
QComboBox QAbstractItemView { background: #161923; color: #E8EAF0;
    border: 1px solid #252A38; selection-background-color: #92600A; outline: none; }

/* ── Radio buttons ── */
QRadioButton { color: #9CA3AF; spacing: 6px; }
QRadioButton::indicator { width: 14px; height: 14px; border-radius: 7px;
    border: 1px solid #252A38; background: #11141D; }
QRadioButton::indicator:checked { background: #F59E0B; border-color: #F59E0B; }
QRadioButton:hover { color: #E8EAF0; }

/* ── Lists ── */
QListWidget { background: #11141D; color: #E8EAF0; border: 1px solid #252A38;
    border-radius: 8px; padding: 4px; outline: none; }
QListWidget::item { padding: 6px 10px; border-radius: 5px; color: #9CA3AF; margin: 1px 2px; }
QListWidget::item:selected { background: rgba(245,158,11,0.12); color: #E8EAF0; }
QListWidget::item:hover:!selected { background: rgba(255,255,255,0.03); color: #E8EAF0; }

/* ── Progress ── */
QProgressBar { background: #11141D; border: none; border-radius: 4px; height: 6px; color: transparent; }
QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
    stop:0 #92600A, stop:1 #FCD34D); border-radius: 4px; }

/* ── Scrollbars ── */
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: #252A38; border-radius: 4px; min-height: 32px; }
QScrollBar::handle:vertical:hover { background: #92600A; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 8px; }
QScrollBar::handle:horizontal { background: #252A38; border-radius: 4px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Log / text area ── */
QTextEdit { background: #0A0C12; color: #6B7280; border: 1px solid #1E2330;
    border-radius: 6px; padding: 8px;
    font-family: "JetBrains Mono","Fira Code","Consolas",monospace; font-size: 11px;
    selection-background-color: #92600A; }

/* ── Checkboxes ── */
QCheckBox { color: #9CA3AF; spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid #252A38; background: #11141D; }
QCheckBox::indicator:checked { background: #F59E0B; border-color: #F59E0B; }
QCheckBox::indicator:hover { border-color: #92600A; }
QCheckBox:hover { color: #E8EAF0; }

/* ── Misc ── */
QFrame[frameShape="4"], QFrame[frameShape="5"] { color: #252A38; }
QSplitter::handle { background: #252A38; width: 1px; }
QToolTip { background: #161923; color: #E8EAF0; border: 1px solid #92600A;
    border-radius: 4px; padding: 4px 8px; font-size: 12px; }
QDialog { background: #161923; }
QMenu { background: #161923; color: #E8EAF0; border: 1px solid #252A38;
    border-radius: 6px; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 4px; }
QMenu::item:selected { background: rgba(245,158,11,0.12); color: #E8EAF0; }
QMenu::separator { height: 1px; background: #252A38; margin: 4px 8px; }
QLabel#section_title { color: #6B7280; font-size: 10px; font-weight: 600; letter-spacing: 1.2px; }
QLabel#dimmed { color: #6B7280; font-size: 12px; }
QLabel#stat_ok  { color: #22C55E; font-size: 11px; font-weight: 600; }
QLabel#stat_err { color: #EF4444; font-size: 11px; font-weight: 600; }
QLabel#stat_dim { color: #6B7280; font-size: 11px; }
"""

# ── Workers ───────────────────────────────────────────────────────────────────

class MatchWorker(QThread):
    progress   = pyqtSignal(int)
    matched    = pyqtSignal(int, object, str)
    status     = pyqtSignal(str)
    finished   = pyqtSignal(int, int)
    hard_error = pyqtSignal(str)

    def __init__(self, files, data_source, naming_scheme, matcher, renamer, hint_names=None):
        super().__init__()
        self.files = files; self.data_source = data_source
        self.naming_scheme = naming_scheme; self.matcher = matcher; self.renamer = renamer
        self.hint_names = hint_names  # optional cleaned filenames for matching (parallel to files)
        self._hard_error_fired = False
        self._should_stop = False

    def stop(self):
        """Request the worker to stop at the next opportunity."""
        self._should_stop = True

    def run(self):
        total = len(self.files); matched_count = 0
        for i, fp in enumerate(self.files):
            if self._should_stop:
                break
            try:
                # If hint_names provided (scene clean mode), use a fake path for matching
                match_path = fp
                if self.hint_names and self.hint_names[i]:
                    # Build a fake path with the cleaned name so matcher parses it correctly
                    cleaned = self.hint_names[i]
                    ext = os.path.splitext(fp)[1]
                    match_path = os.path.join(os.path.dirname(fp), cleaned + ext)
                mi = self.matcher.match_file(match_path, self.data_source, extract_media_info=True)
                if mi:
                    nn = self.renamer.generate_new_name(fp, mi, self.naming_scheme)
                    matched_count += 1
                    self.status.emit(f"\u2713  {os.path.basename(fp)}  \u2192  {mi.get('title','?')} ({mi.get('year','')})")
                else:
                    nn = f"[no match]  {os.path.basename(fp)}"
                    self.status.emit(f"\u2717  No match: {os.path.basename(fp)}")
                self.matched.emit(i, mi, nn)
            except Exception as e:
                err = str(e)
                self.status.emit(f"\u26a0  {os.path.basename(fp)}: {err}")
                self.matched.emit(i, None, f"[error]  {os.path.basename(fp)}")
                if not self._hard_error_fired:
                    self._hard_error_fired = True
                    self.hard_error.emit(err)
            self.progress.emit(int((i+1)/total*100))
        self.finished.emit(matched_count, total)


class FolderScanWorker(QThread):
    """Background worker to scan a folder for media files without blocking the UI."""
    files_found = pyqtSignal(list)
    status      = pyqtSignal(str)

    MEDIA_EXTS = frozenset({'.mp4', '.mkv', '.avi', '.mov', '.m4v', '.mpg', '.mpeg', '.flv', '.wmv'})

    def __init__(self, paths):
        super().__init__()
        self.paths = paths  # list of file or folder paths

    def run(self):
        found = []
        try:
            for path in self.paths:
                if os.path.isdir(path):
                    self.status.emit(f"\u27f3  Scanning {os.path.basename(path)}\u2026")
                    for p in sorted(Path(path).rglob("*")):
                        if p.suffix.lower() in self.MEDIA_EXTS and p.is_file():
                            found.append(str(p))
                elif os.path.isfile(path):
                    if Path(path).suffix.lower() in self.MEDIA_EXTS:
                        found.append(path)
        except Exception as e:
            self.status.emit(f"\u26a0  Scan error: {e}")
        self.files_found.emit(found)


class SubtitleWorker(QThread):
    """Background worker for subtitle fetching."""
    status   = pyqtSignal(str)
    finished = pyqtSignal(int, int)  # (fetched, total)

    def __init__(self, files, language="en"):
        super().__init__()
        self.files    = files
        self.language = language

    def run(self):
        fetcher = SubtitleFetcher()
        fetched = 0
        total   = len(self.files)
        for fp in self.files:
            try:
                sub = fetcher.fetch_subtitle(fp, language=self.language)
                if sub:
                    fetched += 1
                    self.status.emit(f"\u2b07  {os.path.basename(sub)}")
                else:
                    self.status.emit(f"\u2717  No subtitle: {os.path.basename(fp)}")
            except Exception as e:
                self.status.emit(f"\u26a0  {os.path.basename(fp)}: {e}")
        self.finished.emit(fetched, total)


class RenameWorker(QThread):
    progress           = pyqtSignal(int)
    status             = pyqtSignal(str)
    finished           = pyqtSignal(bool, str)
    operation_complete = pyqtSignal(str, str, dict)

    def __init__(self, files, matches, output_dir, naming_scheme,
                 download_artwork=False, write_metadata=False,
                 dry_run=False, copy_mode=False,
                 write_nfo=False, download_fanart=False,
                 on_conflict="skip"):
        super().__init__()
        self.files=files; self.matches=matches; self.output_dir=output_dir
        self.naming_scheme=naming_scheme; self.download_artwork=download_artwork
        self.write_metadata=write_metadata; self.dry_run=dry_run; self.copy_mode=copy_mode
        self.write_nfo=write_nfo; self.download_fanart=download_fanart
        self.on_conflict=on_conflict

    def run(self):
        try:
            renamer     = FileRenamer(self.naming_scheme)
            artwork_dl  = ArtworkDownloader() if (self.download_artwork or self.download_fanart) else None
            meta_wr     = MetadataWriter()    if self.write_metadata   else None
            nfo_wr      = NFOWriter()         if self.write_nfo        else None
            total       = len(self.files)
            renamed     = 0
            skipped     = 0
            conflicts   = 0

            mode_label = "DRY RUN" if self.dry_run else ("COPY" if self.copy_mode else "MOVE")

            for i, (fp, mi) in enumerate(zip(self.files, self.matches)):
                if not mi:
                    self.progress.emit(int((i+1)/total*100))
                    continue

                new_name  = renamer.generate_new_name(fp, mi, self.naming_scheme)
                dest_base = Path(self.output_dir) if self.output_dir else Path(fp).parent
                dest      = dest_base / new_name
                dest.parent.mkdir(parents=True, exist_ok=True)

                if dest.exists() and dest != Path(fp):
                    if self.on_conflict == "skip":
                        conflicts += 1
                        self.status.emit(f"\u26a0  [{mode_label}] Conflict skipped — exists: {dest.name}")
                        self.progress.emit(int((i+1)/total*100))
                        continue
                    elif self.on_conflict == "suffix":
                        # Make unique: add (1), (2)… before extension
                        stem = dest.stem; sfx = dest.suffix; parent = dest.parent
                        n = 1
                        while dest.exists() and dest != Path(fp):
                            dest = parent / f"{stem} ({n}){sfx}"; n += 1
                    # on_conflict == "overwrite": fall through

                if self.dry_run:
                    self.status.emit(f"\u25b6  [DRY RUN] {os.path.basename(fp)} \u2192 {dest.name}")
                    renamed += 1
                    self.progress.emit(int((i+1)/total*100))
                    continue

                try:
                    if self.copy_mode:
                        shutil.copy2(fp, str(dest))
                    else:
                        shutil.move(fp, str(dest))

                    renamed += 1
                    self.status.emit(f"\u2713  [{mode_label}] {os.path.basename(fp)} \u2192 {dest.name}")

                    poster_path = None
                    if artwork_dl:
                        if self.download_artwork:
                            p = artwork_dl.download_poster(mi, str(dest.parent))
                            if p:
                                poster_path = p
                                self.status.emit(f"   \U0001f5bc  Poster: {os.path.basename(p)}")
                                # Also save Kodi/Jellyfin standard name: folder.jpg
                                kodi_poster = dest.parent / "folder.jpg"
                                if not kodi_poster.exists():
                                    try:
                                        shutil.copy2(p, str(kodi_poster))
                                    except Exception:
                                        pass
                        if self.download_fanart:
                            fa = artwork_dl.download_fanart(mi, str(dest.parent))
                            if fa:
                                # Also save as standard fanart.jpg
                                kodi_fanart = dest.parent / "fanart.jpg"
                                if not kodi_fanart.exists():
                                    try:
                                        shutil.copy2(fa, str(kodi_fanart))
                                    except Exception:
                                        pass
                                self.status.emit(f"   \U0001f304  Fanart: {os.path.basename(fa)}")

                    if meta_wr:
                        if meta_wr.write_metadata(str(dest), mi, poster_path):
                            self.status.emit(f"   \U0001f3f7  Metadata written")

                    if nfo_wr:
                        nfo = nfo_wr.write(str(fp), mi, str(dest))
                        if nfo:
                            self.status.emit(f"   \U0001f4c4  NFO: {os.path.basename(nfo)}")
                        # Write tvshow.nfo in show root if it's a TV episode.
                        # Hierarchical scheme (Show/Season XX/file.mkv) → go up 2 levels.
                        # Flat scheme (outdir/file.mkv) → go up 1 level.
                        if mi.get("type") == "tv":
                            parent_name = dest.parent.name.lower()
                            if parent_name.startswith("season") or parent_name.startswith("s0"):
                                show_dir = dest.parent.parent
                            else:
                                show_dir = dest.parent
                            tvshow_nfo = show_dir / "tvshow.nfo"
                            if not tvshow_nfo.exists():
                                nfo_wr.write_tvshow(str(show_dir), mi)

                    self.operation_complete.emit(fp, str(dest), mi)

                except Exception as e:
                    skipped += 1
                    self.status.emit(f"\u2717  Failed: {os.path.basename(fp)} — {e}")

                self.progress.emit(int((i+1)/total*100))

            parts = [f"{renamed} renamed"]
            if conflicts: parts.append(f"{conflicts} conflict(s) skipped")
            if skipped:   parts.append(f"{skipped} error(s)")
            suffix = " (dry run — no files changed)" if self.dry_run else ""
            self.finished.emit(True, "Done — " + ", ".join(parts) + suffix)

        except Exception as e:
            self.finished.emit(False, f"Error: {e}")


# ── Settings dialog ───────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._build(); self._load()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)

        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: none; background: #161923; }
            QTabBar::tab { background: #0A0C12; color: #6B7280; padding: 10px 22px;
                           border: none; font-size: 12px; font-weight: 600; }
            QTabBar::tab:selected { background: #161923; color: #F59E0B;
                                    border-bottom: 2px solid #F59E0B; }
            QTabBar::tab:hover:!selected { color: #E8EAF0; background: #11141D; }
        """)

        # ── API Keys tab ──────────────────────────────────────────────────────
        keys_widget = QWidget()
        layout = QVBoxLayout(keys_widget)
        layout.setSpacing(18); layout.setContentsMargins(28,24,28,20)

        sub = QLabel("Keys are stored locally in  ~/.sortiq/settings.json  and sent only to their respective APIs.")
        sub.setWordWrap(True); sub.setStyleSheet("color: #6B7280; font-size: 12px;")
        layout.addWidget(sub)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); sep.setStyleSheet("color: #252A38;")
        layout.addWidget(sep)

        grid = QVBoxLayout(); grid.setSpacing(14)

        def make_row(label, placeholder, link_url, link_label):
            box = QVBoxLayout(); box.setSpacing(4)
            top = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #9CA3AF; font-weight:600; font-size:12px; min-width:160px;")
            top.addWidget(lbl)
            field = QLineEdit(); field.setPlaceholderText(placeholder)
            field.setEchoMode(QLineEdit.EchoMode.Password)
            top.addWidget(field)
            box.addLayout(top)
            hint = QLabel(f'<a href="{link_url}" style="color:#92600A; text-decoration:none; font-size:11px;">\u2197 {link_label}</a>')
            hint.setOpenExternalLinks(True); hint.setContentsMargins(164,0,0,0)
            box.addWidget(hint)
            container = QWidget(); container.setLayout(box)
            grid.addWidget(container)
            return field

        self.tmdb_field = make_row("TMDB API Key *", "Paste v3 API key here\u2026",
            "https://www.themoviedb.org/settings/api", "Get free key at themoviedb.org")
        self.tvdb_field = make_row("TVDB API Key", "Optional",
            "https://thetvdb.com/dashboard/account/apikey", "thetvdb.com")
        self.osub_field = make_row("OpenSubtitles Key", "Optional \u2014 for subtitle fetching",
            "https://www.opensubtitles.com/consumers", "opensubtitles.com (free key, 10-20/day)")
        self.fanart_field = make_row("FanArt.tv API Key", "Optional \u2014 for HD logos, clearart, disc art",
            "https://fanart.tv/get-an-api-key/", "Get free client key at fanart.tv")
        layout.addLayout(grid)

        self.show_cb = QCheckBox("Show keys while editing")
        self.show_cb.setStyleSheet("color: #6B7280; font-size:12px;")
        self.show_cb.toggled.connect(self._toggle_echo)
        layout.addWidget(self.show_cb)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine); sep2.setStyleSheet("color: #252A38;")
        layout.addWidget(sep2)
        note = QLabel("* Required for file matching.")
        note.setStyleSheet("color: #6B7280; font-size:11px;"); layout.addWidget(note)

        btns = QHBoxLayout(); btns.addStretch()
        cancel = QPushButton("Cancel"); cancel.setObjectName("ghost"); cancel.clicked.connect(self.reject)
        save = QPushButton("Save Keys"); save.setObjectName("match"); save.clicked.connect(self._save)
        btns.addWidget(cancel); btns.addWidget(save)
        layout.addLayout(btns)
        tabs.addTab(keys_widget, "\U0001f511  API Keys")

        # ── About tab ─────────────────────────────────────────────────────────
        about_widget = QWidget()
        av = QVBoxLayout(about_widget)
        av.setContentsMargins(40, 30, 40, 30); av.setSpacing(0)
        av.addStretch(1)

        logo = QLabel("\u25c6")
        logo.setStyleSheet("color: #F59E0B; font-size: 48px; border: none;")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av.addWidget(logo)

        app_name = QLabel("SortIQ")
        app_name.setStyleSheet("color: #E8EAF0; font-size: 26px; font-weight: 800; letter-spacing: -0.5px; border: none;")
        app_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av.addWidget(app_name)

        version_lbl = QLabel("v1.3  —  The open-source FileBot alternative")
        version_lbl.setStyleSheet("color: #6B7280; font-size: 13px; border: none;")
        version_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av.addWidget(version_lbl)

        av.addSpacing(28)
        sep_about = QFrame(); sep_about.setFrameShape(QFrame.Shape.HLine)
        sep_about.setStyleSheet("color: #252A38; margin: 0 60px;")
        av.addWidget(sep_about)
        av.addSpacing(24)

        credit = QLabel(
            "Built by <b style=\'color:#F59E0B;\'>loukaniko</b>"
            " with a little help from his <b style=\'color:#6B7280;\'>LLM</b>"
        )
        credit.setStyleSheet("color: #9CA3AF; font-size: 14px; border: none;")
        credit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av.addWidget(credit)
        av.addSpacing(14)

        desc = QLabel(
            "Rename and organise your movies, TV shows and Anime.\n"
            "Powered by TheMovieDB, TheTVDB and AniDB."
        )
        desc.setStyleSheet("color: #6B7280; font-size: 12px; border: none;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        av.addWidget(desc)
        av.addSpacing(24)

        features = QLabel(
            "\u2713  Batch rename with naming scheme presets\n"
            "\u2713  Dry-run preview before committing\n"
            "\u2713  Copy or move — keep your originals\n"
            "\u2713  REST API with Swagger UI\n"
            "\u2713  Async batch jobs with webhook callbacks\n"
            "\u2713  Checksum generation (MD5/SHA1/SHA256)\n"
            "\u2713  Artwork download & MP4/MKV metadata embed\n"
            "\u2713  Subtitle fetching via OpenSubtitles\n"
            "\u2713  Undo / redo — nothing is permanent"
        )
        features.setStyleSheet("color: #6B7280; font-size: 11px; line-height: 1.8; border: none;")
        features.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av.addWidget(features)
        av.addSpacing(24)

        # Show API link only when running inside Docker (API is only available there)
        _in_docker  = bool(os.environ.get("RUNNING_IN_DOCKER"))
        _in_appimage = bool(os.environ.get("APPIMAGE"))
        if _in_docker:
            _api_port = os.environ.get("API_PORT", "8060")
            api_lbl = QLabel(
                f'REST API + Swagger: <a href="http://localhost:{_api_port}/docs" style="color:#F59E0B;">localhost:{_api_port}/docs</a>'
                f'  <span style="color:#4B5563;">(or your-host-ip:{_api_port}/docs)</span>'
            )
            api_lbl.setStyleSheet("color: #6B7280; font-size: 11px; border: none;")
            api_lbl.setOpenExternalLinks(True)
            api_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            av.addWidget(api_lbl)
        elif _in_appimage:
            api_lbl = QLabel("Running as AppImage — GUI only (no REST API)")
            api_lbl.setStyleSheet("color: #4B5563; font-size: 11px; border: none; font-style: italic;")
            api_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            av.addWidget(api_lbl)
        else:
            api_lbl = QLabel(
                'Run via Docker to enable the REST API '
                '(<a href="https://github.com/loukaniko/sortiq" style="color:#92600A;">docs</a>)'
            )
            api_lbl.setStyleSheet("color: #4B5563; font-size: 11px; border: none;")
            api_lbl.setOpenExternalLinks(True)
            api_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            av.addWidget(api_lbl)

        av.addStretch(2)
        close_btn = QPushButton("Close"); close_btn.setObjectName("ghost")
        close_btn.setFixedWidth(100); close_btn.clicked.connect(self.reject)
        close_row = QHBoxLayout(); close_row.addStretch(); close_row.addWidget(close_btn); close_row.addStretch()
        av.addLayout(close_row)
        tabs.addTab(about_widget, "\u2139  About")

        outer.addWidget(tabs)

    def _toggle_echo(self, show):
        m = QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password
        for f in (self.tmdb_field, self.tvdb_field, self.osub_field, self.fanart_field):
            f.setEchoMode(m)

    def _load(self):
        s = load_settings()
        self.tmdb_field.setText(s.get("tmdb_api_key",""))
        self.tvdb_field.setText(s.get("tvdb_api_key",""))
        self.osub_field.setText(s.get("opensubtitles_api_key",""))
        self.fanart_field.setText(s.get("fanart_api_key",""))

    def _save(self):
        s = load_settings()
        s["tmdb_api_key"]          = self.tmdb_field.text().strip()
        s["tvdb_api_key"]          = self.tvdb_field.text().strip()
        s["opensubtitles_api_key"] = self.osub_field.text().strip()
        s["fanart_api_key"]        = self.fanart_field.text().strip()
        save_settings(s)
        if s["tmdb_api_key"]:          os.environ["TMDB_API_KEY"]          = s["tmdb_api_key"]
        if s["tvdb_api_key"]:          os.environ["TVDB_API_KEY"]          = s["tvdb_api_key"]
        if s["opensubtitles_api_key"]: os.environ["OPENSUBTITLES_API_KEY"] = s["opensubtitles_api_key"]
        if s["fanart_api_key"]:        os.environ["FANART_API_KEY"]        = s["fanart_api_key"]
        self.accept()


# ── Drop zone ─────────────────────────────────────────────────────────────────

class DropZone(QWidget):
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._hover = False

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): self._hover = True; self.update(); e.acceptProposedAction()
    def dragLeaveEvent(self, e): self._hover = False; self.update()
    def dropEvent(self, e):
        self._hover = False; self.update()
        self.files_dropped.emit([u.toLocalFile() for u in e.mimeData().urls()])
        e.acceptProposedAction()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        from PyQt6.QtCore import Qt as Qtc
        from PyQt6.QtGui import QPen
        pen = QPen(QColor(C_AMBER if self._hover else C_BORDER))
        pen.setStyle(Qtc.PenStyle.DashLine); pen.setWidth(1)
        p.setPen(pen)
        p.setBrush(QBrush(QColor(C_AMBER + "18" if self._hover else C_SURFACE)))
        p.drawRoundedRect(self.rect().adjusted(8,8,-8,-8), 12, 12)
        p.setPen(QColor(C_AMBER if self._hover else C_TEXT_DIM))
        f = QFont(); f.setPointSize(26); p.setFont(f)
        p.drawText(self.rect().adjusted(0,-36,0,-36), Qtc.AlignmentFlag.AlignCenter, "\u2B07")
        f2 = QFont(); f2.setPointSize(11); f2.setWeight(QFont.Weight.Medium); p.setFont(f2)
        p.setPen(QColor(C_TEXT if self._hover else C_TEXT_MID))
        p.drawText(self.rect().adjusted(0,20,0,20), Qtc.AlignmentFlag.AlignCenter, "Drop files or folders here")
        f3 = QFont(); f3.setPointSize(9); p.setFont(f3)
        p.setPen(QColor(C_TEXT_DIM))
        p.drawText(self.rect().adjusted(0,52,0,52), Qtc.AlignmentFlag.AlignCenter,
                   "mp4  \u00b7  mkv  \u00b7  avi  \u00b7  mov  \u00b7  m4v  \u00b7  wmv")


# ── Batch Jobs Dialog ─────────────────────────────────────────────────────────

class JobPollerThread(QThread):
    """Polls the API for job list updates every 2 seconds."""
    jobs_updated = pyqtSignal(list)
    error        = pyqtSignal(str)

    def __init__(self, api_base: str):
        super().__init__()
        self._api_base = api_base
        self._running  = True

    def stop(self): self._running = False

    def run(self):
        import time as _time
        import urllib.request
        import json as _json
        while self._running:
            try:
                with urllib.request.urlopen(f"{self._api_base}/jobs", timeout=3) as r:
                    self.jobs_updated.emit(_json.loads(r.read()))
            except Exception as e:
                self.error.emit(str(e))
            _time.sleep(2)


class BatchJobsDialog(QDialog):
    """
    Batch Jobs panel — submit directory jobs to the FastAPI backend
    and monitor their live progress without leaving the GUI.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Jobs")
        self.setMinimumSize(860, 600)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._api_port = os.environ.get("API_PORT", "8060")
        self._api_base = f"http://localhost:{self._api_port}/api/v1"
        self._selected_job_id: str = ""
        self._poller = None
        self._build()
        self._start_poller()

    def closeEvent(self, e):
        if self._poller:
            self._poller.stop()
            self._poller.quit()
            self._poller.wait(2000)  # Wait up to 2 s to prevent use-after-free
        super().closeEvent(e)

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build(self):
        outer = QVBoxLayout(self); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)

        # ── Top bar ───────────────────────────────────────────────────────────
        topbar = QWidget(); topbar.setStyleSheet(f"background:{C_PANEL}; border-bottom:1px solid {C_BORDER};")
        topbar.setFixedHeight(52)
        th = QHBoxLayout(topbar); th.setContentsMargins(18,0,18,0); th.setSpacing(10)
        ttl = QLabel("\u25a6  Batch Jobs")
        ttl.setStyleSheet(f"font-size:15px; font-weight:700; color:{C_TEXT};")
        th.addWidget(ttl)
        api_badge = QLabel(f"API: {self._api_base}")
        api_badge.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        th.addWidget(api_badge)
        th.addStretch()
        refresh_btn = QPushButton("\u21bb Refresh"); refresh_btn.setObjectName("ghost")
        refresh_btn.setFixedHeight(28); refresh_btn.clicked.connect(self._refresh)
        th.addWidget(refresh_btn)
        close_btn = QPushButton("Close"); close_btn.setObjectName("ghost")
        close_btn.setFixedHeight(28); close_btn.clicked.connect(self.close)
        th.addWidget(close_btn)
        outer.addWidget(topbar)

        # ── Main split ────────────────────────────────────────────────────────
        splitter_widget = QWidget(); splitter_widget.setStyleSheet(f"background:{C_BG};")
        sh = QHBoxLayout(splitter_widget); sh.setContentsMargins(0,0,0,0); sh.setSpacing(0)

        # Left — submit form
        left = QWidget(); left.setFixedWidth(320)
        left.setStyleSheet(f"background:{C_SURFACE}; border-right:1px solid {C_BORDER};")
        lv = QVBoxLayout(left); lv.setContentsMargins(16,16,16,12); lv.setSpacing(10)

        submit_lbl = QLabel("SUBMIT NEW JOB"); submit_lbl.setObjectName("section_title")
        lv.addWidget(submit_lbl)

        dir_lbl = QLabel("Directory or file paths (one per line):")
        dir_lbl.setStyleSheet(f"color:{C_TEXT_MID}; font-size:11px;")
        lv.addWidget(dir_lbl)

        self._paths_edit = QTextEdit()
        self._paths_edit.setPlaceholderText("/media/Downloads/Movies\n/media/Downloads/TV")
        self._paths_edit.setFixedHeight(90)
        self._paths_edit.setStyleSheet(
            f"background:{C_BG}; color:{C_TEXT}; border:1px solid {C_BORDER}; "
            f"border-radius:6px; padding:6px; font-size:12px; font-family:monospace;"
        )
        lv.addWidget(self._paths_edit)

        browse_row = QHBoxLayout(); browse_row.setSpacing(6)
        browse_dir_btn = QPushButton("\U0001f4c2  Browse dir"); browse_dir_btn.setObjectName("ghost")
        browse_dir_btn.setFixedHeight(28)
        browse_dir_btn.clicked.connect(self._browse_dir)
        browse_row.addWidget(browse_dir_btn); browse_row.addStretch()
        lv.addLayout(browse_row)

        scheme_lbl = QLabel("Naming scheme:"); scheme_lbl.setStyleSheet(f"color:{C_TEXT_MID}; font-size:11px;")
        lv.addWidget(scheme_lbl)
        self._scheme_edit = QLineEdit("{n} ({y})")
        lv.addWidget(self._scheme_edit)

        outdir_lbl = QLabel("Output directory (blank = rename in place):")
        outdir_lbl.setStyleSheet(f"color:{C_TEXT_MID}; font-size:11px;")
        lv.addWidget(outdir_lbl)
        od_row = QHBoxLayout(); od_row.setSpacing(6)
        self._outdir_edit = QLineEdit()
        self._outdir_edit.setPlaceholderText("/media/Movies")
        od_row.addWidget(self._outdir_edit)
        browse_out_btn = QPushButton("\u2026"); browse_out_btn.setObjectName("ghost")
        browse_out_btn.setFixedWidth(32); browse_out_btn.setFixedHeight(32)
        browse_out_btn.clicked.connect(self._browse_out)
        od_row.addWidget(browse_out_btn)
        lv.addLayout(od_row)

        src_lbl2 = QLabel("Data source:"); src_lbl2.setStyleSheet(f"color:{C_TEXT_MID}; font-size:11px;")
        lv.addWidget(src_lbl2)
        self._src_combo = QComboBox()
        self._src_combo.addItems(["TheMovieDB","TheTVDB","AniDB"])
        lv.addWidget(self._src_combo)

        op_lbl = QLabel("Operation:"); op_lbl.setStyleSheet(f"color:{C_TEXT_MID}; font-size:11px;")
        lv.addWidget(op_lbl)
        op_row = QHBoxLayout(); op_row.setSpacing(12)
        self._move_radio2 = QRadioButton("Move"); self._move_radio2.setChecked(True)
        self._copy_radio2 = QRadioButton("Copy")
        self._bg2 = QButtonGroup(self); self._bg2.addButton(self._move_radio2); self._bg2.addButton(self._copy_radio2)
        op_row.addWidget(self._move_radio2); op_row.addWidget(self._copy_radio2); op_row.addStretch()
        lv.addLayout(op_row)

        opts_row = QHBoxLayout(); opts_row.setSpacing(12)
        self._dry_run_cb2  = QCheckBox("Dry Run"); self._dry_run_cb2.setStyleSheet(f"color:{C_AMBER}; font-size:11px;")
        self._artwork_cb2  = QCheckBox("Artwork")
        self._meta_cb2     = QCheckBox("Metadata")
        opts_row.addWidget(self._dry_run_cb2); opts_row.addWidget(self._artwork_cb2)
        opts_row.addWidget(self._meta_cb2); opts_row.addStretch()
        lv.addLayout(opts_row)

        webhook_lbl = QLabel("Webhook URL (optional):")
        webhook_lbl.setStyleSheet(f"color:{C_TEXT_MID}; font-size:11px;")
        lv.addWidget(webhook_lbl)
        self._webhook_edit = QLineEdit()
        self._webhook_edit.setPlaceholderText("https://your-server/hooks/sortiq")
        lv.addWidget(self._webhook_edit)

        lv.addStretch()

        self._submit_btn = QPushButton("\u25b6  Submit Job")
        self._submit_btn.setObjectName("match"); self._submit_btn.setFixedHeight(40)
        self._submit_btn.clicked.connect(self._submit_job)
        lv.addWidget(self._submit_btn)
        sh.addWidget(left)

        # Right — job list + detail
        right = QWidget(); right.setStyleSheet(f"background:{C_BG};")
        rv = QVBoxLayout(right); rv.setContentsMargins(12,12,12,12); rv.setSpacing(8)

        list_lbl = QLabel("JOBS"); list_lbl.setObjectName("section_title"); rv.addWidget(list_lbl)

        self._job_list = QListWidget()
        self._job_list.setFixedHeight(180)
        self._job_list.currentRowChanged.connect(self._on_job_selected)
        rv.addWidget(self._job_list)

        # Job detail area
        detail_lbl = QLabel("JOB DETAIL"); detail_lbl.setObjectName("section_title"); rv.addWidget(detail_lbl)

        self._progress2 = QProgressBar(); self._progress2.setVisible(False); self._progress2.setFixedHeight(6)
        rv.addWidget(self._progress2)

        self._detail_lbl = QLabel("Select a job to view its log and results.")
        self._detail_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px; padding:4px;")
        self._detail_lbl.setWordWrap(True)
        rv.addWidget(self._detail_lbl)

        self._job_log = QTextEdit(); self._job_log.setReadOnly(True)
        rv.addWidget(self._job_log, stretch=1)

        cancel_row = QHBoxLayout(); cancel_row.setSpacing(8)
        self._cancel_btn = QPushButton("\u2715  Cancel Job"); self._cancel_btn.setObjectName("danger")
        self._cancel_btn.setFixedHeight(32); self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._cancel_job)
        self._delete_btn = QPushButton("\U0001f5d1  Delete Record"); self._delete_btn.setObjectName("ghost")
        self._delete_btn.setFixedHeight(32); self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._delete_job)
        cancel_row.addWidget(self._cancel_btn); cancel_row.addWidget(self._delete_btn); cancel_row.addStretch()
        rv.addLayout(cancel_row)
        sh.addWidget(right)

        outer.addWidget(splitter_widget, stretch=1)

        # Status bar
        self._statusbar = QLabel("  Ready")
        self._statusbar.setStyleSheet(f"background:{C_PANEL}; color:{C_TEXT_DIM}; "
                                       f"font-size:11px; border-top:1px solid {C_BORDER}; padding:4px 12px;")
        self._statusbar.setFixedHeight(26)
        outer.addWidget(self._statusbar)

    # ── Poller ────────────────────────────────────────────────────────────────
    def _start_poller(self):
        self._poller = JobPollerThread(self._api_base)
        self._poller.jobs_updated.connect(self._on_jobs_updated)
        self._poller.error.connect(lambda e: self._statusbar.setText(f"  API error: {e}"))
        self._poller.start()

    def _refresh(self):
        try:
            import urllib.request, json as _json
            with urllib.request.urlopen(f"{self._api_base}/jobs", timeout=3) as r:
                self._on_jobs_updated(_json.loads(r.read()))
        except Exception as e:
            self._statusbar.setText(f"  Refresh failed: {e}")

    def _on_jobs_updated(self, jobs: list):
        prev = self._selected_job_id
        self._job_list.clear()
        for job in jobs:
            status = job.get("status","?")
            pct    = job.get("progress",{}).get("percent", 0)
            renamed = job.get("renamed_count", 0)
            total   = job.get("file_count", 0)
            icons   = {"pending":"\u23f3","running":"\u27f3","completed":"\u2713","failed":"\u2717","cancelled":"\u2014"}
            icon    = icons.get(status,"?")
            colours = {"pending": C_TEXT_DIM, "running": C_AMBER, "completed": C_SUCCESS, "failed": C_ERROR, "cancelled": C_TEXT_DIM}
            text    = f"{icon}  [{status.upper():12}]  {renamed}/{total} files  {pct:.0f}%  — id:{job['job_id'][:8]}…"
            item    = QListWidgetItem(text)
            item.setForeground(QColor(colours.get(status, C_TEXT_MID)))
            item.setData(Qt.ItemDataRole.UserRole, job)
            self._job_list.addItem(item)
        # Restore selection
        for i in range(self._job_list.count()):
            d = self._job_list.item(i).data(Qt.ItemDataRole.UserRole)
            if d and d.get("job_id") == prev:
                self._job_list.setCurrentRow(i)
                break
        n = self._job_list.count()
        self._statusbar.setText(f"  {n} job{'s' if n!=1 else ''} — auto-refreshing every 2s")

    def _on_job_selected(self, row):
        if row < 0: return
        item = self._job_list.item(row)
        if not item: return
        job = item.data(Qt.ItemDataRole.UserRole)
        if not job: return
        self._selected_job_id = job.get("job_id","")
        status  = job.get("status") or "unknown"
        pct     = job.get("progress",{}).get("percent",0)
        renamed = job.get("renamed_count",0)
        errors  = job.get("error_count",0)
        confl   = job.get("conflict_count",0)
        total   = job.get("file_count",0)
        self._detail_lbl.setText(
            f"Job: {self._selected_job_id}   Status: {status.upper()}   "
            f"{renamed}/{total} renamed   {errors} errors   {confl} conflicts"
        )
        running = status == "running"
        self._progress2.setVisible(running or status == "pending")
        self._progress2.setValue(int(pct))
        self._cancel_btn.setEnabled(status in ("pending","running"))
        self._delete_btn.setEnabled(status not in ("pending","running"))
        # Fetch detail log
        try:
            import urllib.request, json as _json
            with urllib.request.urlopen(f"{self._api_base}/jobs/{self._selected_job_id}", timeout=3) as r:
                detail = _json.loads(r.read())
            log_lines = detail.get("log", [])
            self._job_log.setPlainText("\n".join(log_lines))
            self._job_log.verticalScrollBar().setValue(self._job_log.verticalScrollBar().maximum())
        except Exception as e:
            self._job_log.setPlainText(f"Could not fetch log: {e}")

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Directory to Process", "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog)
        if d:
            cur = self._paths_edit.toPlainText().strip()
            self._paths_edit.setPlainText((cur + "\n" + d).strip())

    def _browse_out(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog)
        if d: self._outdir_edit.setText(d)

    def _submit_job(self):
        raw = self._paths_edit.toPlainText().strip()
        if not raw:
            QMessageBox.warning(self, "No Paths", "Enter at least one directory or file path.")
            return
        files = [p.strip() for p in raw.splitlines() if p.strip()]
        payload = {
            "files":            files,
            "naming_scheme":    self._scheme_edit.text().strip() or "{n} ({y})",
            "output_dir":       self._outdir_edit.text().strip() or None,
            "operation":        "copy" if self._copy_radio2.isChecked() else "move",
            "data_source":      self._src_combo.currentText(),
            "dry_run":          self._dry_run_cb2.isChecked(),
            "download_artwork": self._artwork_cb2.isChecked(),
            "write_metadata":   self._meta_cb2.isChecked(),
            "webhook_url":      self._webhook_edit.text().strip() or None,
        }
        try:
            import urllib.request, json as _json
            data = _json.dumps(payload).encode()
            req  = urllib.request.Request(f"{self._api_base}/jobs",
                                          data=data, method="POST",
                                          headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                job = _json.loads(r.read())
            self._statusbar.setText(f"  Job submitted: {job['job_id']}")
            QTimer.singleShot(500, self._refresh)
        except Exception as e:
            QMessageBox.critical(self, "Submit Failed", str(e))

    def _cancel_job(self):
        if not self._selected_job_id: return
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self._api_base}/jobs/{self._selected_job_id}/cancel",
                method="POST", data=b""
            )
            urllib.request.urlopen(req, timeout=5)
            self._statusbar.setText(f"  Cancelled: {self._selected_job_id[:8]}…")
            QTimer.singleShot(300, self._refresh)
        except Exception as e:
            QMessageBox.critical(self, "Cancel Failed", str(e))

    def _delete_job(self):
        if not self._selected_job_id: return
        try:
            import urllib.request
            req = urllib.request.Request(
                f"{self._api_base}/jobs/{self._selected_job_id}",
                method="DELETE"
            )
            urllib.request.urlopen(req, timeout=5)
            self._selected_job_id = ""
            self._job_log.clear()
            self._detail_lbl.setText("Job deleted.")
            QTimer.singleShot(300, self._refresh)
        except Exception as e:
            QMessageBox.critical(self, "Delete Failed", str(e))


# ── Main window ───────────────────────────────────────────────────────────────



# ── Duplicate Finder Dialog ───────────────────────────────────────────────────

class DuplicateScanWorker(QThread):
    """Background worker to scan for duplicate files."""
    result  = pyqtSignal(list, int)   # (groups, total_scanned)
    status  = pyqtSignal(str)

    def __init__(self, directory: str, mode: str = "exact"):
        super().__init__()
        self.directory = directory
        self.mode = mode

    def run(self):
        try:
            self.status.emit(f"Scanning {self.directory}…")
            groups, total = scan_directory_for_duplicates(self.directory, self.mode)
            self.result.emit(groups, total)
        except Exception as e:
            self.status.emit(f"Scan error: {e}")
            self.result.emit([], 0)


class DuplicateFinderDialog(QDialog):
    """Find duplicate video files by exact hash or size proximity."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Duplicate File Finder")
        self.setMinimumSize(820, 560)
        self._worker = None
        self._groups = []
        self._build()

    def _build(self):
        v = QVBoxLayout(self)
        v.setSpacing(10); v.setContentsMargins(16, 14, 16, 14)

        # Toolbar row
        top = QHBoxLayout()
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("Select directory to scan…")
        browse = QPushButton("Browse…")
        browse.setFixedWidth(80)
        browse.clicked.connect(self._browse)
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Exact duplicates (hash)", "Probable duplicates (size ±5%)"])
        self._mode_combo.setFixedWidth(220)
        scan_btn = QPushButton("▶  Scan")
        scan_btn.setObjectName("rename")
        scan_btn.setFixedWidth(90)
        scan_btn.clicked.connect(self._scan)
        top.addWidget(QLabel("Directory:"))
        top.addWidget(self._dir_edit, stretch=1)
        top.addWidget(browse)
        top.addWidget(self._mode_combo)
        top.addWidget(scan_btn)
        v.addLayout(top)

        # Status
        self._status_lbl = QLabel("Choose a directory and click Scan.")
        self._status_lbl.setStyleSheet("color: #888; font-size: 11px;")
        v.addWidget(self._status_lbl)

        # Results table
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["File", "Size", "Group"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        v.addWidget(self._table, stretch=1)

        # Footer
        foot = QHBoxLayout()
        self._summary_lbl = QLabel("")
        self._summary_lbl.setStyleSheet("font-size: 11px; color: #ccc;")
        del_btn = QPushButton("🗑  Delete Selected")
        del_btn.setObjectName("ghost")
        del_btn.clicked.connect(self._delete_selected)
        close_btn = QPushButton("Close")
        close_btn.setObjectName("ghost")
        close_btn.clicked.connect(self.close)
        foot.addWidget(self._summary_lbl, stretch=1)
        foot.addWidget(del_btn)
        foot.addWidget(close_btn)
        v.addLayout(foot)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Directory to Scan", "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog)
        if d:
            self._dir_edit.setText(d)

    def _scan(self):
        directory = self._dir_edit.text().strip()
        if not directory or not os.path.isdir(directory):
            QMessageBox.warning(self, "No Directory", "Please choose a valid directory first.")
            return
        if self._worker is not None and self._worker.isRunning():
            return  # Scan already in progress — ignore the second click
        mode = "exact" if self._mode_combo.currentIndex() == 0 else "probable"
        self._status_lbl.setText("Scanning… please wait.")
        self._table.setRowCount(0)
        self._worker = DuplicateScanWorker(directory, mode)
        self._worker.result.connect(self._on_result)
        self._worker.status.connect(lambda s: self._status_lbl.setText(s))
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_result(self, groups, total):
        self._groups = groups
        self._table.setRowCount(0)
        if not groups:
            self._status_lbl.setText(f"No duplicates found in {total} file(s) scanned.")
            self._summary_lbl.setText("")
            return
        total_dupes = sum(len(g) for g in groups)
        wasted = wasted_space(groups)
        self._status_lbl.setText(
            f"Found {total_dupes} duplicate file(s) in {len(groups)} group(s) "
            f"({human_size(wasted)} wasted) — scanned {total} file(s)."
        )
        row = 0
        for g_idx, group in enumerate(groups, 1):
            for path in group:
                self._table.insertRow(row)
                try:
                    size = human_size(os.path.getsize(path))
                except OSError:
                    size = "?"
                self._table.setItem(row, 0, QTableWidgetItem(path))
                self._table.setItem(row, 1, QTableWidgetItem(size))
                grp_item = QTableWidgetItem(f"#{g_idx}")
                grp_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row, 2, grp_item)
                row += 1

    def _delete_selected(self):
        rows = sorted(set(i.row() for i in self._table.selectedItems()), reverse=True)
        if not rows:
            return
        paths = [self._table.item(r, 0).text() for r in rows if self._table.item(r, 0)]
        confirm = QMessageBox.question(
            self, "Delete Files",
            "Permanently delete {} file(s)?\n\n".format(len(paths)) + "\n".join(paths[:5]) + ("\n…" if len(paths) > 5 else ""),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        deleted = 0
        for path in paths:
            try:
                os.remove(path)
                deleted += 1
            except OSError as e:
                QMessageBox.warning(self, "Delete Error", f"Could not delete:\n{path}\n{e}")
        for row in rows:
            self._table.removeRow(row)
        self._status_lbl.setText(f"Deleted {deleted} file(s).")


# ── Watch Folder Dialog ───────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# Missing Episodes Dialog
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Sonarr / Radarr integration
# ─────────────────────────────────────────────────────────────────────────────
class SonarrRadarrWorker(QThread):
    """Fetch wanted/missing lists from Sonarr and/or Radarr."""
    result_ready = pyqtSignal(list)
    error        = pyqtSignal(str)
    status       = pyqtSignal(str)

    def __init__(self, sonarr_url, sonarr_key, radarr_url, radarr_key):
        super().__init__()
        self.sonarr_url = sonarr_url.rstrip("/")
        self.sonarr_key = sonarr_key
        self.radarr_url = radarr_url.rstrip("/")
        self.radarr_key = radarr_key

    def _headers(self, key):
        return {"X-Api-Key": key, "Accept": "application/json"}

    def _get(self, base_url, key, path, params=None):
        import requests
        r = requests.get(f"{base_url}{path}", headers=self._headers(key),
                         params=params or {}, timeout=10)
        r.raise_for_status()
        try:
            return r.json()
        except ValueError as exc:
            raise ValueError(f"Invalid JSON response from {path}: {exc}") from exc

    def run(self):
        import requests
        results = []

        if self.sonarr_url and self.sonarr_key:
            try:
                self.status.emit("Connecting to Sonarr…")
                page, page_size = 1, 100
                while True:
                    data = self._get(self.sonarr_url, self.sonarr_key,
                                     "/api/v3/wanted/missing",
                                     {"page": page, "pageSize": page_size, "sortKey": "series.title"})
                    records = data.get("records", [])
                    for rec in records:
                        series = rec.get("series", {})
                        results.append({
                            "source":    "Sonarr",
                            "type":      "tv",
                            "title":     series.get("title", "?"),
                            "season":    rec.get("seasonNumber"),
                            "episode":   rec.get("episodeNumber"),
                            "ep_title":  rec.get("title", ""),
                            "monitored": rec.get("monitored", True),
                            "series_id": series.get("id"),
                            "ep_id":     rec.get("id"),
                        })
                    if len(records) < page_size:
                        break
                    page += 1
                n = len([r for r in results if r["source"] == "Sonarr"])
                self.status.emit(f"Sonarr: {n} wanted episode(s)")
            except requests.exceptions.ConnectionError:
                self.error.emit(f"Cannot connect to Sonarr at {self.sonarr_url}")
            except requests.exceptions.HTTPError as e:
                self.error.emit(f"Sonarr HTTP {e.response.status_code}: check API key")
            except Exception as e:
                self.error.emit(f"Sonarr: {e}")

        if self.radarr_url and self.radarr_key:
            try:
                self.status.emit("Connecting to Radarr…")
                page, page_size = 1, 100
                while True:
                    data = self._get(self.radarr_url, self.radarr_key,
                                     "/api/v3/wanted/missing",
                                     {"page": page, "pageSize": page_size})
                    records = data.get("records", [])
                    for rec in records:
                        results.append({
                            "source":    "Radarr",
                            "type":      "movie",
                            "title":     rec.get("title", "?"),
                            "year":      rec.get("year"),
                            "tmdb_id":   rec.get("tmdbId"),
                            "monitored": rec.get("monitored", True),
                            "movie_id":  rec.get("id"),
                        })
                    if len(records) < page_size:
                        break
                    page += 1
                n = len([r for r in results if r["source"] == "Radarr"])
                self.status.emit(f"Radarr: {n} wanted movie(s)")
            except requests.exceptions.ConnectionError:
                self.error.emit(f"Cannot connect to Radarr at {self.radarr_url}")
            except requests.exceptions.HTTPError as e:
                self.error.emit(f"Radarr HTTP {e.response.status_code}: check API key")
            except Exception as e:
                self.error.emit(f"Radarr: {e}")

        self.result_ready.emit(results)


class ProwlarrSearchWorker(QThread):
    """Send automatic search requests to Prowlarr for a list of wanted items."""
    progress = pyqtSignal(int, int)   # done, total
    status   = pyqtSignal(str)
    done     = pyqtSignal(int)        # number of requests sent

    def __init__(self, items, prowlarr_url, prowlarr_key,
                 sonarr_url, sonarr_key, radarr_url, radarr_key):
        super().__init__()
        self.items        = items          # list of result dicts from SonarrRadarrWorker
        self.prowlarr_url = prowlarr_url.rstrip("/")
        self.prowlarr_key = prowlarr_key
        self.sonarr_url   = sonarr_url.rstrip("/")
        self.sonarr_key   = sonarr_key
        self.radarr_url   = radarr_url.rstrip("/")
        self.radarr_key   = radarr_key

    def _headers(self, key):
        return {"X-Api-Key": key, "Content-Type": "application/json"}

    def run(self):
        import requests
        sent = 0
        total = len(self.items)

        for i, item in enumerate(self.items):
            try:
                if item["source"] == "Sonarr" and item.get("ep_id"):
                    # Trigger Sonarr episode search via Sonarr's own command API
                    r = requests.post(
                        f"{self.sonarr_url}/api/v3/command",
                        headers=self._headers(self.sonarr_key),
                        json={"name": "EpisodeSearch", "episodeIds": [item["ep_id"]]},
                        timeout=10,
                    )
                    if r.ok:
                        sent += 1
                        self.status.emit(f"▶ Sonarr search: {item['title']} S{item.get('season',0):02d}E{item.get('episode',0):02d}")
                    else:
                        self.status.emit(f"⚠ Sonarr search failed {r.status_code}: {item['title']}")

                elif item["source"] == "Radarr" and item.get("movie_id"):
                    # Trigger Radarr movie search
                    r = requests.post(
                        f"{self.radarr_url}/api/v3/command",
                        headers=self._headers(self.radarr_key),
                        json={"name": "MoviesSearch", "movieIds": [item["movie_id"]]},
                        timeout=10,
                    )
                    if r.ok:
                        sent += 1
                        self.status.emit(f"▶ Radarr search: {item['title']}")
                    else:
                        self.status.emit(f"⚠ Radarr search failed {r.status_code}: {item['title']}")

            except Exception as e:
                self.status.emit(f"⚠ {item.get('title', '?')}: {e}")

            self.progress.emit(i + 1, total)

        self.done.emit(sent)


class SonarrRadarrDialog(QDialog):
    """Show Sonarr / Radarr / Prowlarr wanted lists and trigger downloads."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sonarr / Radarr / Prowlarr — Wanted & Download")
        self.setMinimumSize(900, 620)
        self._results = []
        self._build()
        self._load_settings()

    def _build(self):
        v = QVBoxLayout(self); v.setSpacing(8); v.setContentsMargins(16, 14, 16, 14)

        desc = QLabel(
            "Connects to Sonarr and/or Radarr to fetch <b>wanted/missing</b> content, "
            "then triggers automatic searches through Sonarr/Radarr (which use Prowlarr as their indexer)."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        v.addWidget(desc)

        # Settings in two columns: Sonarr/Radarr left, Prowlarr right
        cols = QHBoxLayout(); cols.setSpacing(10)

        def make_group(title, fields):
            """fields = [(label, attr_name, placeholder, default)]"""
            grp = QGroupBox(title)
            grp.setStyleSheet(
                f"QGroupBox {{ color:{C_TEXT_DIM}; font-size:10px; font-weight:600;"
                f" border:1px solid {C_BORDER}; border-radius:4px;"
                f" margin-top:8px; padding-top:12px; }}"
            )
            gl = QVBoxLayout(grp); gl.setSpacing(5)
            for label, attr, placeholder, default in fields:
                row = QHBoxLayout(); row.setSpacing(6)
                lbl = QLabel(label); lbl.setFixedWidth(80)
                lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px;")
                edit = QLineEdit(); edit.setPlaceholderText(placeholder); edit.setText(default)
                setattr(self, attr, edit)
                row.addWidget(lbl); row.addWidget(edit, stretch=1)
                gl.addLayout(row)
            return grp

        arr_grp = make_group("Sonarr & Radarr", [
            ("Sonarr URL",  "_sonarr_url", "http://localhost:8989", "http://localhost:8989"),
            ("Sonarr Key",  "_sonarr_key", "API key from Settings → Security", ""),
            ("Radarr URL",  "_radarr_url", "http://localhost:7878", "http://localhost:7878"),
            ("Radarr Key",  "_radarr_key", "API key from Settings → Security", ""),
        ])
        prow_grp = make_group("Prowlarr (optional — for direct search trigger)", [
            ("Prowlarr URL","_prowlarr_url", "http://localhost:9696", "http://localhost:9696"),
            ("Prowlarr Key","_prowlarr_key", "API key from Prowlarr Settings → General", ""),
        ])
        cols.addWidget(arr_grp, stretch=2)
        cols.addWidget(prow_grp, stretch=1)
        v.addLayout(cols)

        # Status
        self._status_lbl = QLabel("Enter connection details and click Fetch Wanted.")
        self._status_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        v.addWidget(self._status_lbl)

        # Progress bar (for download operations)
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setFixedHeight(4)
        v.addWidget(self._progress)

        # Results tree — extra "Select" column
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Title", "Season/Ep", "Episode Title", "Source", ""])
        self._tree.setColumnWidth(0, 260); self._tree.setColumnWidth(1, 80)
        self._tree.setColumnWidth(2, 220); self._tree.setColumnWidth(3, 70)
        self._tree.setColumnWidth(4, 30)
        self._tree.header().setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px;")
        self._tree.setSortingEnabled(True)
        v.addWidget(self._tree, stretch=1)

        # Filter row
        fr = QHBoxLayout()
        fr.addWidget(QLabel("Filter:"))
        self._filter = QLineEdit(); self._filter.setPlaceholderText("Type to filter…")
        self._filter.textChanged.connect(self._apply_filter)
        fr.addWidget(self._filter, stretch=1)
        self._count_lbl = QLabel("0 items")
        self._count_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        fr.addWidget(self._count_lbl)
        v.addLayout(fr)

        # Action buttons
        foot = QHBoxLayout(); foot.setSpacing(8)

        fetch_btn = QPushButton("↻  Fetch Wanted")
        fetch_btn.setObjectName("match"); fetch_btn.clicked.connect(self._fetch)

        self._dl_sel_btn = QPushButton("▶  Download Selected")
        self._dl_sel_btn.setObjectName("ghost"); self._dl_sel_btn.setEnabled(False)
        self._dl_sel_btn.setToolTip("Trigger Sonarr/Radarr search for selected items")
        self._dl_sel_btn.clicked.connect(self._download_selected)

        self._dl_all_btn = QPushButton("▶▶  Download All Missing")
        self._dl_all_btn.setObjectName("rename"); self._dl_all_btn.setEnabled(False)
        self._dl_all_btn.setToolTip("Trigger Sonarr/Radarr search for every item in the list")
        self._dl_all_btn.clicked.connect(self._download_all)

        save_btn = QPushButton("💾  Save")
        save_btn.setObjectName("ghost"); save_btn.clicked.connect(self._save_settings)

        export_btn = QPushButton("Export CSV")
        export_btn.setObjectName("ghost"); export_btn.clicked.connect(self._export_csv)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("ghost"); close_btn.clicked.connect(self.close)

        foot.addWidget(fetch_btn)
        foot.addWidget(self._dl_sel_btn)
        foot.addWidget(self._dl_all_btn)
        foot.addStretch()
        foot.addWidget(save_btn)
        foot.addWidget(export_btn)
        foot.addWidget(close_btn)
        v.addLayout(foot)

        # Enable select-download on tree selection change
        self._tree.itemSelectionChanged.connect(
            lambda: self._dl_sel_btn.setEnabled(bool(self._tree.selectedItems()))
        )

    # ── Settings ──────────────────────────────────────────────────

    def _load_settings(self):
        s = load_settings()
        for attr, key in [
            ("_sonarr_url",   "sonarr_url"),
            ("_sonarr_key",   "sonarr_key"),
            ("_radarr_url",   "radarr_url"),
            ("_radarr_key",   "radarr_key"),
            ("_prowlarr_url", "prowlarr_url"),
            ("_prowlarr_key", "prowlarr_key"),
        ]:
            val = s.get(key, "")
            if val:
                getattr(self, attr).setText(val)

    def _save_settings(self):
        s = load_settings()
        for attr, key in [
            ("_sonarr_url",   "sonarr_url"),
            ("_sonarr_key",   "sonarr_key"),
            ("_radarr_url",   "radarr_url"),
            ("_radarr_key",   "radarr_key"),
            ("_prowlarr_url", "prowlarr_url"),
            ("_prowlarr_key", "prowlarr_key"),
        ]:
            s[key] = getattr(self, attr).text().strip()
        save_settings(s)
        self._status_lbl.setText("✓ Settings saved")

    # ── Fetch ─────────────────────────────────────────────────────

    def _fetch(self):
        if hasattr(self, '_worker') and self._worker is not None and self._worker.isRunning():
            return  # Fetch already in progress
        self._tree.clear(); self._results = []
        self._dl_all_btn.setEnabled(False); self._dl_sel_btn.setEnabled(False)
        self._status_lbl.setText("Fetching…")
        self._worker = SonarrRadarrWorker(
            self._sonarr_url.text().strip(), self._sonarr_key.text().strip(),
            self._radarr_url.text().strip(), self._radarr_key.text().strip(),
        )
        self._worker.result_ready.connect(self._on_results)
        self._worker.status.connect(self._status_lbl.setText)
        self._worker.error.connect(lambda e: self._status_lbl.setText(f"⚠ {e}"))
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_results(self, results):
        self._results = results
        self._populate(results)
        self._dl_all_btn.setEnabled(bool(results))

    def _populate(self, results):
        self._tree.clear()
        from collections import defaultdict
        sonarr = [r for r in results if r["source"] == "Sonarr"]
        radarr = [r for r in results if r["source"] == "Radarr"]

        if sonarr:
            root = QTreeWidgetItem(self._tree)
            root.setText(0, f"📺 Sonarr — {len(sonarr)} missing episode(s)")
            root.setForeground(0, QColor(C_AMBER))
            root.setExpanded(True)
            by_show = defaultdict(list)
            for r in sonarr:
                by_show[r["title"]].append(r)
            for show_title, eps in sorted(by_show.items()):
                show_item = QTreeWidgetItem(root)
                show_item.setText(0, show_title)
                show_item.setText(3, f"{len(eps)} missing")
                show_item.setForeground(3, QColor(C_TEXT_DIM))
                show_item.setExpanded(True)
                for ep in sorted(eps, key=lambda x: (x.get("season", 0), x.get("episode", 0))):
                    it = QTreeWidgetItem(show_item)
                    it.setText(0, show_title)
                    s, e = ep.get("season", 0), ep.get("episode", 0)
                    it.setText(1, f"S{s:02d}E{e:02d}")
                    it.setText(2, ep.get("ep_title", ""))
                    it.setText(3, "Sonarr")
                    it.setData(0, Qt.ItemDataRole.UserRole, ep)

        if radarr:
            root = QTreeWidgetItem(self._tree)
            root.setText(0, f"🎬 Radarr — {len(radarr)} missing movie(s)")
            root.setForeground(0, QColor(C_AMBER))
            root.setExpanded(True)
            for r in sorted(radarr, key=lambda x: x["title"]):
                it = QTreeWidgetItem(root)
                it.setText(0, f"{r['title']} ({r.get('year', '?')})")
                it.setText(1, "—")
                it.setText(2, "Movie")
                it.setText(3, "Radarr")
                it.setData(0, Qt.ItemDataRole.UserRole, r)

        total = len(results)
        self._count_lbl.setText(f"{total} item(s)")
        self._status_lbl.setText(
            f"✓ {len(sonarr)} missing TV episode(s), {len(radarr)} missing movie(s)"
            if results else "✓ Nothing missing — your collection is complete!"
        )

    # ── Download triggers ─────────────────────────────────────────

    def _download_selected(self):
        items = []
        for qt_item in self._tree.selectedItems():
            data = qt_item.data(0, Qt.ItemDataRole.UserRole)
            if data:
                items.append(data)
        if not items:
            QMessageBox.information(self, "Nothing Selected", "Select individual episode/movie rows first.")
            return
        self._trigger_downloads(items)

    def _download_all(self):
        if not self._results:
            return
        reply = QMessageBox.question(
            self, "Download All Missing",
            f"Trigger Sonarr/Radarr automatic search for all {len(self._results)} missing item(s)?\n\n"
            "This sends search commands to Sonarr/Radarr — it will not immediately download anything; "
            "the apps will search their configured indexers (e.g. Prowlarr) and grab the best match.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._trigger_downloads(self._results)

    def _trigger_downloads(self, items):
        if hasattr(self, '_dl_worker') and self._dl_worker is not None and self._dl_worker.isRunning():
            return  # Download trigger already in progress
        self._progress.setVisible(True); self._progress.setValue(0)
        self._dl_all_btn.setEnabled(False); self._dl_sel_btn.setEnabled(False)
        self._status_lbl.setText(f"Sending {len(items)} search request(s)…")

        self._dl_worker = ProwlarrSearchWorker(
            items,
            self._prowlarr_url.text().strip(), self._prowlarr_key.text().strip(),
            self._sonarr_url.text().strip(),   self._sonarr_key.text().strip(),
            self._radarr_url.text().strip(),   self._radarr_key.text().strip(),
        )
        self._dl_worker.progress.connect(
            lambda done, total: self._progress.setValue(int(done / total * 100))
        )
        self._dl_worker.status.connect(self._status_lbl.setText)
        self._dl_worker.done.connect(self._on_downloads_done)
        self._dl_worker.finished.connect(self._dl_worker.deleteLater)
        self._dl_worker.start()

    def _on_downloads_done(self, sent):
        self._progress.setVisible(False)
        self._dl_all_btn.setEnabled(bool(self._results))
        self._status_lbl.setText(
            f"✓ Triggered {sent} search request(s) — check Sonarr/Radarr Activity for progress"
        )

    # ── Filter / Export ───────────────────────────────────────────

    def _apply_filter(self, text):
        text = text.lower()
        filtered = (
            [r for r in self._results
             if text in r.get("title", "").lower()
             or text in r.get("ep_title", "").lower()]
            if text else self._results
        )
        self._populate(filtered)

    def _export_csv(self):
        if not self._results:
            QMessageBox.information(self, "No Data", "Fetch data first."); return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "wanted.csv", "CSV (*.csv)",
            options=QFileDialog.Option.DontUseNativeDialog)
        if not path:
            return
        import csv
        fieldnames = ["source", "type", "title", "season", "episode", "ep_title", "year", "tmdb_id"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader(); w.writerows(self._results)
        self._status_lbl.setText(f"✓ Exported to {path}")


class MissingEpisodesWorker(QThread):
    """Fetch full episode lists from TMDB and find gaps."""
    result_ready = pyqtSignal(list)   # list of (show, season, missing_eps)
    error        = pyqtSignal(str)

    def __init__(self, matches, tmdb_key, base_url):
        super().__init__()
        self.matches  = matches   # list of mi dicts (may contain None)
        self.tmdb_key = tmdb_key
        self.base_url = base_url

    def run(self):
        import requests, collections
        # Group episodes we HAVE by (title, tmdb_id, season)
        have = collections.defaultdict(set)
        show_names = {}
        for mi in self.matches:
            if not mi: continue
            if mi.get("type") != "tv": continue
            tid = mi.get("tmdb_id"); s = mi.get("season"); e = mi.get("episode")
            if not (tid and s is not None and e is not None): continue
            key = (tid, s)
            have[key].add(e)
            show_names[tid] = mi.get("title", "Unknown Show")

        results = []
        seen_seasons = set()
        for (tid, season), owned_eps in sorted(have.items()):
            if (tid, season) in seen_seasons: continue
            seen_seasons.add((tid, season))
            title = show_names.get(tid, "?")
            try:
                r = requests.get(
                    f"{self.base_url}/tv/{tid}/season/{season}",
                    params={"api_key": self.tmdb_key, "language": "en-US"},
                    timeout=10
                )
                if r.status_code != 200:
                    continue
                all_eps = {ep["episode_number"] for ep in r.json().get("episodes", [])}
                missing = sorted(all_eps - owned_eps)
                if missing:
                    results.append({
                        "title":   title,
                        "tmdb_id": tid,
                        "season":  season,
                        "owned":   sorted(owned_eps),
                        "total":   len(all_eps),
                        "missing": missing,
                    })
            except Exception as e:
                self.error.emit(str(e))
        self.result_ready.emit(results)


class MissingSonarrWorker(QThread):
    """Send season-pack search commands to Sonarr for missing episodes found by
    MissingEpisodesWorker. Sonarr will then use Prowlarr (or any configured
    indexer) to find and download the missing episodes automatically."""

    progress = pyqtSignal(int, int)   # done, total
    status   = pyqtSignal(str)
    done     = pyqtSignal(int)        # number of commands sent

    def __init__(self, results, sonarr_url, sonarr_key):
        super().__init__()
        # results = list of dicts from MissingEpisodesWorker:
        #   {"title", "tmdb_id", "season", "owned", "total", "missing"}
        self.results    = results
        self.sonarr_url = sonarr_url.rstrip("/")
        self.sonarr_key = sonarr_key

    def _headers(self):
        return {"X-Api-Key": self.sonarr_key, "Content-Type": "application/json",
                "Accept": "application/json"}

    def _get_series_id(self, session, tmdb_id):
        """Look up Sonarr series ID from TMDB ID via Sonarr's /api/v3/series endpoint."""
        try:
            r = session.get(f"{self.sonarr_url}/api/v3/series",
                            headers=self._headers(), timeout=10)
            r.raise_for_status()
            for s in r.json():
                if s.get("tmdbId") == tmdb_id:
                    return s["id"]
        except Exception:
            pass
        return None

    def run(self):
        import requests
        sent  = 0
        total = len(self.results)
        session = requests.Session()

        for i, r in enumerate(self.results):
            title  = r.get("title", "?")
            season = r.get("season", 0)
            tmdb_id = r.get("tmdb_id")

            try:
                # Resolve Sonarr series ID from TMDB ID
                series_id = self._get_series_id(session, tmdb_id)
                if series_id is None:
                    self.status.emit(
                        f"⚠ '{title}' not found in Sonarr — "
                        "add it to Sonarr first, then rescan."
                    )
                    self.progress.emit(i + 1, total)
                    continue

                # SeasonSearch triggers Sonarr to search all missing eps in the season.
                # Sonarr routes the request through Prowlarr and grabs the best match.
                resp = session.post(
                    f"{self.sonarr_url}/api/v3/command",
                    headers=self._headers(),
                    json={"name": "SeasonSearch",
                          "seriesId": series_id,
                          "seasonNumber": season},
                    timeout=10,
                )
                if resp.ok:
                    sent += 1
                    missing_count = len(r.get("missing", []))
                    self.status.emit(
                        f"▶ Sonarr: searching Season {season:02d} of '{title}' "
                        f"({missing_count} missing ep(s))"
                    )
                else:
                    self.status.emit(
                        f"⚠ Sonarr returned {resp.status_code} for '{title}' S{season:02d}"
                    )

            except requests.exceptions.ConnectionError:
                self.status.emit(f"⚠ Cannot connect to Sonarr at {self.sonarr_url}")
                break
            except Exception as e:
                self.status.emit(f"⚠ {title}: {e}")

            self.progress.emit(i + 1, total)

        self.done.emit(sent)


class MissingEpisodesDialog(QDialog):
    """Show which episodes are missing and optionally send searches to Sonarr/Prowlarr."""

    def __init__(self, matches, matcher, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Missing Episodes")
        self.setMinimumSize(860, 560)
        self.matches  = matches
        self.matcher  = matcher
        self._results = []      # list of result dicts from worker
        self._build()
        self._load_arr_settings()
        tv_count = sum(1 for m in matches if m and m.get("type") == "tv")
        if tv_count:
            self._scan()
        else:
            self._status.setText("No TV show matches found. Match some TV episodes first.")

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        v = QVBoxLayout(self); v.setSpacing(8); v.setContentsMargins(16, 14, 16, 14)

        desc = QLabel(
            "Compares your matched TV episodes against the full TMDB episode list "
            "and shows exactly what you are missing. "
            "Use the Sonarr connection below to trigger automatic searches for missing episodes."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        v.addWidget(desc)

        # ── Sonarr connection row ─────────────────────────────────────────────
        arr_row = QHBoxLayout(); arr_row.setSpacing(6)
        sonarr_lbl = QLabel("Sonarr:")
        sonarr_lbl.setFixedWidth(52)
        sonarr_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px; font-weight:600;")
        self._arr_url = QLineEdit(); self._arr_url.setPlaceholderText("http://localhost:8989")
        self._arr_url.setFixedWidth(200)
        self._arr_key = QLineEdit(); self._arr_key.setPlaceholderText("API key")
        self._arr_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._arr_key.setFixedWidth(220)
        self._save_arr_btn = QPushButton("Save")
        self._save_arr_btn.setObjectName("ghost")
        self._save_arr_btn.setFixedWidth(50)
        self._save_arr_btn.clicked.connect(self._save_arr_settings)
        arr_row.addWidget(sonarr_lbl)
        arr_row.addWidget(self._arr_url)
        arr_row.addWidget(self._arr_key)
        arr_row.addWidget(self._save_arr_btn)
        arr_row.addStretch()
        v.addLayout(arr_row)

        # ── Status + progress ─────────────────────────────────────────────────
        self._status = QLabel("Scanning…")
        self._status.setStyleSheet(f"color:{C_AMBER}; font-size:11px;")
        v.addWidget(self._status)

        self._progress = QProgressBar()
        self._progress.setFixedHeight(3)
        self._progress.setVisible(False)
        v.addWidget(self._progress)

        # ── Results tree ──────────────────────────────────────────────────────
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Show / Season", "Missing Episodes", "Have / Total", ""])
        self._tree.setColumnWidth(0, 240)
        self._tree.setColumnWidth(1, 300)
        self._tree.setColumnWidth(2, 90)
        self._tree.setColumnWidth(3, 30)
        self._tree.header().setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px;")
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        v.addWidget(self._tree, stretch=1)

        # ── Footer buttons ────────────────────────────────────────────────────
        foot = QHBoxLayout(); foot.setSpacing(8)

        refresh_btn = QPushButton("↻  Rescan")
        refresh_btn.setObjectName("ghost")
        refresh_btn.clicked.connect(self._scan)

        self._send_sel_btn = QPushButton("▶  Search Selected in Sonarr")
        self._send_sel_btn.setObjectName("ghost")
        self._send_sel_btn.setEnabled(False)
        self._send_sel_btn.setToolTip(
            "Select season rows then click to trigger Sonarr automatic search "
            "for all missing episodes in those seasons"
        )
        self._send_sel_btn.clicked.connect(self._send_selected)

        self._send_all_btn = QPushButton("▶▶  Search All Missing in Sonarr")
        self._send_all_btn.setObjectName("match")
        self._send_all_btn.setEnabled(False)
        self._send_all_btn.setToolTip(
            "Trigger Sonarr automatic search for every missing episode in the list"
        )
        self._send_all_btn.clicked.connect(self._send_all)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("ghost")
        close_btn.clicked.connect(self.close)

        foot.addWidget(refresh_btn)
        foot.addStretch()
        foot.addWidget(self._send_sel_btn)
        foot.addWidget(self._send_all_btn)
        foot.addWidget(close_btn)
        v.addLayout(foot)

    # ── Settings ──────────────────────────────────────────────────────────────

    def _load_arr_settings(self):
        s = load_settings()
        url = s.get("sonarr_url", "")
        key = s.get("sonarr_key", "")
        if url: self._arr_url.setText(url)
        if key: self._arr_key.setText(key)

    def _save_arr_settings(self):
        s = load_settings()
        s["sonarr_url"] = self._arr_url.text().strip()
        s["sonarr_key"] = self._arr_key.text().strip()
        save_settings(s)
        self._status.setText("✓ Sonarr settings saved")

    # ── TMDB scan ─────────────────────────────────────────────────────────────

    def _scan(self):
        if hasattr(self, '_worker') and self._worker is not None and self._worker.isRunning():
            return  # TMDB scan already in progress
        self._tree.clear()
        self._results = []
        self._send_all_btn.setEnabled(False)
        self._send_sel_btn.setEnabled(False)
        self._status.setText("Scanning TMDB for complete episode lists…")
        key  = getattr(self.matcher, "tmdb_api_key", "") or os.environ.get("TMDB_API_KEY", "")
        base = getattr(self.matcher, "tmdb_base_url", "https://api.themoviedb.org/3")
        if not key:
            self._status.setText("No TMDB API key — add it in Settings.")
            return
        self._worker = MissingEpisodesWorker(self.matches, key, base)
        self._worker.result_ready.connect(self._on_results)
        self._worker.error.connect(lambda e: self._status.setText(f"Error: {e}"))
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_results(self, results):
        self._results = results
        self._tree.clear()
        if not results:
            self._status.setText("✓ No missing episodes found — your collection is complete!")
            return
        total_missing = sum(len(r["missing"]) for r in results)
        self._status.setText(
            f"Found {total_missing} missing episode(s) across {len(results)} season(s). "
            f"Use Sonarr buttons to trigger automatic searches."
        )
        for r in results:
            root = QTreeWidgetItem(self._tree)
            root.setText(0, f"{r['title']}  —  Season {r['season']}")
            root.setText(2, f"{len(r['owned'])} / {r['total']}")
            root.setForeground(0, QColor(C_TEXT))
            root.setExpanded(True)
            # Store full result dict for Sonarr dispatch
            root.setData(0, Qt.ItemDataRole.UserRole, r)

            # Build compact range notation: E01  E03-E05  E09
            eps = r["missing"]
            chunks = []
            start = end = eps[0]
            for ep in eps[1:]:
                if ep == end + 1:
                    end = ep
                else:
                    chunks.append(f"E{start:02d}" if start == end else f"E{start:02d}–E{end:02d}")
                    start = end = ep
            chunks.append(f"E{start:02d}" if start == end else f"E{start:02d}–E{end:02d}")
            range_str = "  ".join(chunks)

            missing_item = QTreeWidgetItem(root)
            missing_item.setText(1, range_str)
            missing_item.setText(2, f"{len(eps)} missing")
            missing_item.setForeground(1, QColor(C_ERROR))
            missing_item.setForeground(2, QColor(C_AMBER))

        has_sonarr = bool(self._arr_url.text().strip() and self._arr_key.text().strip())
        self._send_all_btn.setEnabled(has_sonarr)
        self._send_sel_btn.setEnabled(has_sonarr)
        if not has_sonarr:
            self._status.setText(
                self._status.text() +
                " — Enter Sonarr URL and API key above to enable search triggers."
            )

    # ── Sonarr dispatch ───────────────────────────────────────────────────────

    def _get_arr_creds(self):
        url = self._arr_url.text().strip().rstrip("/")
        key = self._arr_key.text().strip()
        if not url or not key:
            QMessageBox.warning(self, "Sonarr Not Configured",
                "Enter your Sonarr URL and API key above first.")
            return None, None
        return url, key

    def _send_selected(self):
        """Collect season-level results from selected tree rows and dispatch."""
        selected_results = []
        for item in self._tree.selectedItems():
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and "missing" in data:
                selected_results.append(data)
        if not selected_results:
            QMessageBox.information(self, "Nothing Selected",
                "Select one or more show/season rows (the top-level rows).")
            return
        total = sum(len(r["missing"]) for r in selected_results)
        url, key = self._get_arr_creds()
        if not url: return
        reply = QMessageBox.question(self, "Search Selected in Sonarr",
            f"Trigger Sonarr automatic search for {total} missing episode(s) "
            f"across {len(selected_results)} season(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._dispatch_sonarr(selected_results, url, key)

    def _send_all(self):
        if not self._results: return
        total = sum(len(r["missing"]) for r in self._results)
        url, key = self._get_arr_creds()
        if not url: return
        reply = QMessageBox.question(self, "Search All Missing in Sonarr",
            f"Trigger Sonarr automatic search for all {total} missing episode(s)?\n\n"
            "Sonarr will query Prowlarr and all configured indexers and grab the best match.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._dispatch_sonarr(self._results, url, key)

    def _dispatch_sonarr(self, results, sonarr_url, sonarr_key):
        """Use MissingSonarrWorker to send season-pack search commands to Sonarr."""
        if hasattr(self, '_sonarr_worker') and self._sonarr_worker is not None and self._sonarr_worker.isRunning():
            return  # Already dispatching
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._send_all_btn.setEnabled(False)
        self._send_sel_btn.setEnabled(False)
        self._status.setText("Sending search commands to Sonarr…")
        self._sonarr_worker = MissingSonarrWorker(results, sonarr_url, sonarr_key)
        self._sonarr_worker.progress.connect(
            lambda done, total: self._progress.setValue(int(done / total * 100))
        )
        self._sonarr_worker.status.connect(self._status.setText)
        self._sonarr_worker.done.connect(self._on_sonarr_done)
        self._sonarr_worker.finished.connect(self._sonarr_worker.deleteLater)
        self._sonarr_worker.start()

    def _on_sonarr_done(self, sent):
        self._progress.setVisible(False)
        has_sonarr = bool(self._arr_url.text().strip() and self._arr_key.text().strip())
        self._send_all_btn.setEnabled(has_sonarr and bool(self._results))
        self._send_sel_btn.setEnabled(has_sonarr and bool(self._results))
        self._status.setText(
            f"✓ Triggered {sent} Sonarr search command(s) — check Sonarr Activity tab for progress"
        )


class WatchFolderDialog(QDialog):
    """Monitor a folder and auto-add new files to the main window."""

    files_detected = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Watch Folder")
        self.setMinimumSize(540, 320)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_dir_changed)
        self._watched_dir = ""
        self._known_files: set = set()  # track files already emitted to avoid duplicates
        self._build()

    def closeEvent(self, e):
        if self._watched_dir:
            self._watcher.removePath(self._watched_dir)
        super().closeEvent(e)

    def _build(self):
        v = QVBoxLayout(self)
        v.setSpacing(10); v.setContentsMargins(16, 14, 16, 14)

        desc = QLabel(
            "SortIQ will automatically detect new video files placed into "
            "the watched folder and add them to your file list for matching."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #aaa; font-size: 11px;")
        v.addWidget(desc)

        row = QHBoxLayout()
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("Folder to watch…")
        self._dir_edit.setReadOnly(True)
        browse = QPushButton("Browse…")
        browse.setFixedWidth(80)
        browse.clicked.connect(self._browse)
        row.addWidget(QLabel("Watch folder:"))
        row.addWidget(self._dir_edit, stretch=1)
        row.addWidget(browse)
        v.addLayout(row)

        self._status_lbl = QLabel("Not watching.")
        self._status_lbl.setStyleSheet("color: #888; font-size: 11px;")
        v.addWidget(self._status_lbl)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(120)
        self._log.setStyleSheet("font-size: 11px; background: #111; color: #aaa;")
        v.addWidget(self._log)

        foot = QHBoxLayout()
        self._toggle_btn = QPushButton("▶  Start Watching")
        self._toggle_btn.setObjectName("rename")
        self._toggle_btn.clicked.connect(self._toggle)
        clear_btn = QPushButton("Clear Log")
        clear_btn.setObjectName("ghost")
        clear_btn.clicked.connect(self._log.clear)
        close_btn = QPushButton("Close")
        close_btn.setObjectName("ghost")
        close_btn.clicked.connect(self.close)
        foot.addWidget(self._toggle_btn)
        foot.addWidget(clear_btn)
        foot.addStretch()
        foot.addWidget(close_btn)
        v.addLayout(foot)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Folder to Watch", "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog)
        if d:
            self._dir_edit.setText(d)

    def _toggle(self):
        if self._watched_dir:
            self._watcher.removePath(self._watched_dir)
            self._watched_dir = ""
            self._known_files.clear()
            self._toggle_btn.setText("▶  Start Watching")
            self._status_lbl.setText("Not watching.")
            self._status_lbl.setStyleSheet("color: #888; font-size: 11px;")
        else:
            d = self._dir_edit.text().strip()
            if not d or not os.path.isdir(d):
                QMessageBox.warning(self, "No Folder", "Please choose a valid folder first.")
                return
            self._watched_dir = d
            # Snapshot existing files so we only emit *new* ones later
            VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".m4v", ".wmv", ".flv", ".webm"}
            self._known_files = {
                os.path.join(d, f) for f in os.listdir(d)
                if os.path.isfile(os.path.join(d, f)) and Path(f).suffix.lower() in VIDEO_EXT
            }
            self._watcher.addPath(d)
            self._toggle_btn.setText("⏹  Stop Watching")
            self._status_lbl.setText(f"Watching: {d}")
            self._status_lbl.setStyleSheet("color: #4caf50; font-size: 11px; font-weight: bold;")
            self._log.append(f"▶ Started watching: {d} ({len(self._known_files)} existing file(s) ignored)")

    def _on_dir_changed(self, path):
        VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".m4v", ".wmv", ".flv", ".webm"}
        # Suffixes used by browsers/downloaders for in-progress transfers — skip these
        # so half-written files are not queued for matching.
        PARTIAL_EXT = {".part", ".crdownload", ".tmp", ".download", ".partial", ".!ut"}
        new_files = []
        try:
            for f in os.listdir(path):
                p = Path(f)
                # Skip known partial-download extensions entirely
                if p.suffix.lower() in PARTIAL_EXT:
                    continue
                # Also skip files whose stem ends with a partial marker
                if p.suffix.lower() in VIDEO_EXT:
                    fp = os.path.join(path, f)
                    if os.path.isfile(fp) and fp not in self._known_files:
                        new_files.append(fp)
                        self._known_files.add(fp)
        except OSError:
            return
        if new_files:
            self._log.append(f"+ {len(new_files)} new file(s) detected")
            for f in new_files:
                self._log.append(f"  {os.path.basename(f)}")
            self.files_detected.emit(new_files)

class SortIQApp(QMainWindow):
    def __init__(self):
        super().__init__()
        # Explicitly set window flags so decorations (minimize/maximise/close)
        # are always present — critical for AppImage on X11 and Wayland.
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowSystemMenuHint |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowTitle("SortIQ")
        self.setWindowIcon(_app_icon())
        self.setMinimumSize(960, 660); self.resize(1380, 840)
        self.files=[]; self.matches=[]
        self.matcher=MediaMatcher(); self.renamer=FileRenamer()
        self.history=RenameHistory(); self.preset_manager=PresetManager()
        # Worker references — always initialize so hasattr checks aren't needed
        self.match_worker = None
        self._scan_worker = None
        # Sources for which the "uses TMDB backend" warning has already been shown
        self._warned_sources: set = set()
        # Batch undo tracking — set to None until first rename batch runs
        self._batch_start_op_idx = None
        # Map of {source_path: dest_path} populated by _on_op_complete for "Show in folder"
        self._rename_dests: dict = {}
        self._build_ui()
        self.setAcceptDrops(True)

    def _build_ui(self):
        root = QWidget(); self.setCentralWidget(root)
        vbox = QVBoxLayout(root); vbox.setContentsMargins(0,0,0,0); vbox.setSpacing(0)
        vbox.addWidget(self._header())
        vbox.addWidget(self._body(), stretch=1)
        vbox.addWidget(self._footer())

    # ── Header ────────────────────────────────────────────────────
    def _header(self):
        bar = QWidget(); bar.setFixedHeight(58)
        bar.setStyleSheet(f"QWidget {{ background:{C_PANEL}; border-bottom:1px solid {C_BORDER}; }}")
        h = QHBoxLayout(bar); h.setContentsMargins(20,0,16,0); h.setSpacing(12)

        dot = QLabel("\u25c6")
        dot.setStyleSheet(f"color:{C_AMBER}; font-size:16px; border:none;")
        h.addWidget(dot)
        title = QLabel("SortIQ")
        title.setStyleSheet(f"color:{C_TEXT}; font-size:16px; font-weight:700; letter-spacing:-0.5px; border:none;")
        h.addWidget(title)
        badge = QLabel("v1.3")
        badge.setStyleSheet(f"color:{C_AMBER_DIM}; background:rgba(245,158,11,0.1); border:1px solid {C_AMBER_DIM}; border-radius:3px; padding:1px 5px; font-size:9px; font-weight:700; letter-spacing:1px;")
        h.addWidget(badge)
        h.addStretch()

        # Stats bar
        self.stat_matched = QLabel("—")
        self.stat_matched.setObjectName("stat_dim")
        self.stat_matched.setToolTip("Matched files")
        h.addWidget(self.stat_matched)

        sep0 = QFrame(); sep0.setFrameShape(QFrame.Shape.VLine)
        sep0.setStyleSheet(f"color:{C_BORDER}; margin:14px 2px;")
        h.addWidget(sep0)

        src_lbl = QLabel("Source")
        src_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px; border:none;")
        h.addWidget(src_lbl)
        self.data_source_combo = QComboBox()
        self.data_source_combo.addItems(["TheMovieDB","TheTVDB","AniDB"])
        self.data_source_combo.setFixedWidth(120)
        self.data_source_combo.setToolTip(
            "TheMovieDB — fully supported\n"
            "TheTVDB / AniDB — uses TheMovieDB as backend (native integration coming)"
        )
        self.data_source_combo.currentTextChanged.connect(self._on_source_changed)
        h.addWidget(self.data_source_combo)

        lang_lbl = QLabel("Lang")
        lang_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px; border:none;")
        h.addWidget(lang_lbl)
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["en","fr","de","es","it","ja","ko","zh","pt","ru","nl","pl","sv","da","fi","nb"])
        self.lang_combo.setFixedWidth(60)
        self.lang_combo.setToolTip("Preferred language for metadata (ISO 639-1)")
        h.addWidget(self.lang_combo)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color:{C_BORDER}; margin:10px 4px;")
        h.addWidget(sep)

        settings_btn = QPushButton("\u2699  Settings")
        settings_btn.setObjectName("ghost"); settings_btn.setFixedHeight(32)
        settings_btn.clicked.connect(self._open_settings)
        h.addWidget(settings_btn)

        sep3 = QFrame(); sep3.setFrameShape(QFrame.Shape.VLine)
        sep3.setStyleSheet(f"color:{C_BORDER}; margin:10px 4px;")
        h.addWidget(sep3)

        dupes_btn = QPushButton("\U0001f50d  Duplicates")
        dupes_btn.setObjectName("ghost"); dupes_btn.setFixedHeight(32)
        dupes_btn.setToolTip("Find duplicate video files by content hash")
        dupes_btn.clicked.connect(self._open_duplicates)
        h.addWidget(dupes_btn)

        watch_btn = QPushButton("\U0001f441  Watch Folder")
        watch_btn.setObjectName("ghost"); watch_btn.setFixedHeight(32)
        watch_btn.setToolTip("Auto-detect new files dropped into a monitored folder")
        watch_btn.clicked.connect(self._open_watch_folder)
        h.addWidget(watch_btn)

        arr_btn = QPushButton("\U0001f4e1  Arr Suite")
        arr_btn.setObjectName("ghost"); arr_btn.setFixedHeight(32)
        arr_btn.setToolTip("Fetch missing content from Sonarr/Radarr and trigger downloads via Prowlarr")
        arr_btn.clicked.connect(self._open_sonarr_radarr)
        h.addWidget(arr_btn)

        # Batch jobs button — only shown when API is available (Docker)
        if os.environ.get("RUNNING_IN_DOCKER"):
            sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.VLine)
            sep2.setStyleSheet(f"color:{C_BORDER}; margin:10px 4px;")
            h.addWidget(sep2)
            self.jobs_btn = QPushButton("\u25a6  Batch Jobs")
            self.jobs_btn.setObjectName("ghost"); self.jobs_btn.setFixedHeight(32)
            self.jobs_btn.setToolTip("Submit and monitor async batch rename jobs via the REST API")
            self.jobs_btn.clicked.connect(self._open_jobs)
            h.addWidget(self.jobs_btn)

        return bar

    # ── Body ──────────────────────────────────────────────────────
    def _body(self):
        body = QWidget(); body.setStyleSheet(f"background:{C_BG};")
        h = QHBoxLayout(body); h.setContentsMargins(0,0,0,0); h.setSpacing(0)
        h.addWidget(self._left_panel(), stretch=5)
        div = QFrame(); div.setFrameShape(QFrame.Shape.VLine); div.setStyleSheet(f"color:{C_BORDER};")
        h.addWidget(div)
        h.addWidget(self._right_panel(), stretch=6)
        return body

    # ── Left panel ────────────────────────────────────────────────
    def _left_panel(self):
        panel = QWidget(); panel.setStyleSheet(f"background:{C_BG};")
        v = QVBoxLayout(panel); v.setContentsMargins(18,18,18,14); v.setSpacing(8)

        lbl = QLabel("INPUT FILES"); lbl.setObjectName("section_title"); v.addWidget(lbl)

        # Toolbar
        tb = QHBoxLayout(); tb.setSpacing(6)
        self.add_files_btn  = QPushButton("+ Files")
        self.add_folder_btn = QPushButton("+ Folder")
        self.remove_sel_btn = QPushButton("\u2212 Remove")
        self.remove_sel_btn.setObjectName("danger")
        self.clear_btn      = QPushButton("Clear All"); self.clear_btn.setObjectName("danger")
        for b in (self.add_files_btn, self.add_folder_btn, self.remove_sel_btn, self.clear_btn):
            b.setFixedHeight(30)
        self.add_files_btn.clicked.connect(self.add_files)
        self.add_folder_btn.clicked.connect(self.add_folder)
        self.remove_sel_btn.clicked.connect(self.remove_selected)
        self.clear_btn.clicked.connect(self.clear_files)
        tb.addWidget(self.add_files_btn); tb.addWidget(self.add_folder_btn)
        tb.addStretch()
        tb.addWidget(self.remove_sel_btn)
        tb.addWidget(self.clear_btn)
        v.addLayout(tb)

        # Search filter
        search_container = QWidget()
        search_container.setStyleSheet("background:transparent;")
        sl = QHBoxLayout(search_container); sl.setContentsMargins(0,0,0,0); sl.setSpacing(0)
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("\U0001f50d  Filter files…")
        self.filter_input.setObjectName("search")
        self.filter_input.textChanged.connect(self._apply_filter)
        sl.addWidget(self.filter_input)
        v.addWidget(search_container)

        # File list stack
        self.file_stack = QStackedWidget()
        self.drop_zone  = DropZone()
        self.drop_zone.files_dropped.connect(self.add_files_list)
        self.original_list = QListWidget()
        self.original_list.setAcceptDrops(False)  # Let main window handle external drops
        self.original_list.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.original_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.original_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.original_list.customContextMenuRequested.connect(self._file_context_menu)
        self.file_stack.addWidget(self.drop_zone)
        self.file_stack.addWidget(self.original_list)
        self.file_stack.setCurrentIndex(0)
        v.addWidget(self.file_stack, stretch=1)

        self.file_count_lbl = QLabel("No files loaded")
        self.file_count_lbl.setObjectName("dimmed")
        self.file_count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.file_count_lbl)

        # Match button — BLUE
        self.match_btn = QPushButton("\u25c8  Match Files")
        self.match_btn.setObjectName("match")
        self.match_btn.setFixedHeight(44)
        self.match_btn.clicked.connect(self.match_files)
        v.addWidget(self.match_btn)
        return panel

    # ── Right panel ───────────────────────────────────────────────
    def _right_panel(self):
        panel = QWidget(); panel.setStyleSheet(f"background:{C_BG};")
        v = QVBoxLayout(panel); v.setContentsMargins(18,18,18,14); v.setSpacing(8)

        # Naming scheme
        sl = QLabel("NAMING SCHEME"); sl.setObjectName("section_title"); v.addWidget(sl)
        sr = QHBoxLayout(); sr.setSpacing(8)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(self.preset_manager.list_presets())
        self.preset_combo.setFixedWidth(160)
        self.preset_combo.currentTextChanged.connect(self.load_preset)
        self.naming_scheme_input = QLineEdit("{n}.{y}.{vf}.{vc}.{af}")
        self.naming_scheme_input.textChanged.connect(self._refresh_preview)
        self.naming_scheme_input.setToolTip(
            "{n} title  \u00b7  {y} year  \u00b7  {vf} resolution  \u00b7  {vc} video codec\n"
            "{af} audio format  \u00b7  {ac} audio channels\n"
            "{s} season  \u00b7  {e} episode  \u00b7  {s00e00} S01E01  \u00b7  {t} ep title"
        )
        sp = QPushButton("Save"); sp.setObjectName("ghost"); sp.setFixedWidth(56)
        sp.clicked.connect(self.save_current_preset)
        sr.addWidget(self.preset_combo); sr.addWidget(self.naming_scheme_input, stretch=1); sr.addWidget(sp)
        v.addLayout(sr)

        legend = QLabel("{n} title  \u00b7  {y} year  \u00b7  {vf} res  \u00b7  {vc} video  \u00b7  {af} audio  \u00b7  {ac} channels  \u00b7  {s}{e} season/ep  \u00b7  {t} ep title")
        legend.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px;")
        legend.setWordWrap(True); v.addWidget(legend)

        # Output dir
        ol = QLabel("OUTPUT DIRECTORY"); ol.setObjectName("section_title"); v.addWidget(ol)
        or_ = QHBoxLayout(); or_.setSpacing(6)
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText("Leave empty to rename files in place")
        browse_btn = QPushButton("Browse\u2026"); browse_btn.setObjectName("ghost")
        browse_btn.setFixedWidth(80); browse_btn.clicked.connect(self.browse_output_dir)
        or_.addWidget(self.output_dir_input); or_.addWidget(browse_btn)
        v.addLayout(or_)

        # Options row
        optl = QLabel("OPTIONS"); optl.setObjectName("section_title"); v.addWidget(optl)
        opt = QHBoxLayout(); opt.setSpacing(16)

        self.download_artwork_check = QCheckBox("Download Artwork")
        self.download_artwork_check.setToolTip("Download poster (folder.jpg) alongside renamed files")
        self.download_fanart_check  = QCheckBox("Download Fanart")
        self.download_fanart_check.setToolTip("Download backdrop/fanart (fanart.jpg) for Kodi/Jellyfin")
        self.write_metadata_check   = QCheckBox("Write Metadata")
        self.write_metadata_check.setToolTip("Embed metadata tags into MP4/M4V (mutagen) and MKV (mkvtoolnix) files")
        self.write_nfo_check        = QCheckBox("Write NFO")
        self.write_nfo_check.setToolTip("Generate Kodi/Jellyfin/Emby .nfo sidecar XML files")
        self.dry_run_check          = QCheckBox("Dry Run (preview only)")
        self.dry_run_check.setToolTip("Show what WOULD be renamed without changing any files")
        self.dry_run_check.setStyleSheet(f"color:{C_AMBER}; spacing:8px;")

        self.clean_scene_check = QCheckBox("Clean Scene Names")
        self.clean_scene_check.setToolTip(
            "Strip release-group tags from filenames before matching\n"
            "e.g. Movie.2023.1080p.BluRay.x264-GROUP → Movie 2023"
        )
        opt.addWidget(self.download_artwork_check)
        opt.addWidget(self.download_fanart_check)
        opt.addWidget(self.write_metadata_check)
        opt.addWidget(self.write_nfo_check)
        opt.addWidget(self.dry_run_check)
        opt.addWidget(self.clean_scene_check)
        opt.addStretch()
        v.addLayout(opt)

        # Copy vs Move + conflict resolution
        mode_row = QHBoxLayout(); mode_row.setSpacing(16)
        mode_lbl = QLabel("File operation:")
        mode_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        self.move_radio = QRadioButton("Move (rename in place)")
        self.copy_radio = QRadioButton("Copy (keep originals)")
        self.move_radio.setChecked(True)
        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self.move_radio)
        self._mode_group.addButton(self.copy_radio)
        mode_row.addWidget(mode_lbl)
        mode_row.addWidget(self.move_radio)
        mode_row.addWidget(self.copy_radio)
        mode_row.addStretch()

        conflict_lbl = QLabel("On conflict:")
        conflict_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:11px;")
        self.conflict_combo = QComboBox()
        self.conflict_combo.addItems(["Skip (keep existing)", "Rename with suffix", "Overwrite"])
        self.conflict_combo.setFixedWidth(160)
        self.conflict_combo.setToolTip(
            "Skip — leave existing file untouched (default)\n"
            "Rename with suffix — add (1), (2)… to make unique\n"
            "Overwrite — replace the existing file"
        )
        mode_row.addWidget(conflict_lbl)
        mode_row.addWidget(self.conflict_combo)
        v.addLayout(mode_row)

        # Preview list
        pr = QHBoxLayout()
        pvl = QLabel("RENAMED PREVIEW"); pvl.setObjectName("section_title"); pr.addWidget(pvl)
        pr.addStretch()

        # Subtitle language selector (separate from metadata language)
        sub_lang_lbl = QLabel("Sub lang:")
        sub_lang_lbl.setStyleSheet(f"color:{C_TEXT_DIM}; font-size:10px;")
        pr.addWidget(sub_lang_lbl)
        self.sub_lang_combo = QComboBox()
        self.sub_lang_combo.addItems(["en","fr","de","es","it","ja","ko","zh","pt","ru","nl","pl","sv","da","fi","nb"])
        self.sub_lang_combo.setFixedWidth(52)
        self.sub_lang_combo.setToolTip("Subtitle language to fetch from OpenSubtitles (ISO 639-1)")
        pr.addWidget(self.sub_lang_combo)

        self.fetch_subs_btn = QPushButton("\u2b07 Subtitles")
        self.fetch_subs_btn.setObjectName("ghost"); self.fetch_subs_btn.setFixedHeight(26)
        self.fetch_subs_btn.clicked.connect(self.fetch_subtitles)
        pr.addWidget(self.fetch_subs_btn)

        self.missing_eps_btn = QPushButton("\U0001f4cb Missing Episodes")
        self.missing_eps_btn.setObjectName("ghost"); self.missing_eps_btn.setFixedHeight(26)
        self.missing_eps_btn.setToolTip("Check TMDB for episodes you\'re missing from matched TV shows")
        self.missing_eps_btn.clicked.connect(self._open_missing_episodes)
        pr.addWidget(self.missing_eps_btn)
        v.addLayout(pr)

        self.new_names_list = QListWidget()
        self.new_names_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.new_names_list.customContextMenuRequested.connect(self._preview_context_menu)
        v.addWidget(self.new_names_list, stretch=1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False); self.progress_bar.setFixedHeight(6)
        v.addWidget(self.progress_bar)

        # Actions
        ar = QHBoxLayout(); ar.setSpacing(8)
        self.undo_btn = QPushButton("\u21a9 Undo"); self.undo_btn.setObjectName("ghost"); self.undo_btn.setFixedHeight(36)
        self.undo_btn.clicked.connect(self.undo_rename); self.undo_btn.setEnabled(self.history.can_undo())
        self.undo_btn.setToolTip("Undo last rename  (Ctrl+Z)")
        self.redo_btn = QPushButton("\u21aa Redo"); self.redo_btn.setObjectName("ghost"); self.redo_btn.setFixedHeight(36)
        self.redo_btn.clicked.connect(self.redo_rename); self.redo_btn.setEnabled(self.history.can_redo())
        self.redo_btn.setToolTip("Redo last undo  (Ctrl+Y)")
        self.undo_batch_btn = QPushButton("\u21ba Undo Batch"); self.undo_batch_btn.setObjectName("ghost")
        self.undo_batch_btn.setFixedHeight(36); self.undo_batch_btn.setEnabled(False)
        self.undo_batch_btn.clicked.connect(self.undo_batch)
        self.undo_batch_btn.setToolTip("Undo all renames from the last Rename run")

        # Rename button — GREEN
        self.rename_btn = QPushButton("\u25b6  Rename Files")
        self.rename_btn.setObjectName("rename")
        self.rename_btn.setFixedHeight(44)
        self.rename_btn.setEnabled(False)
        self.rename_btn.clicked.connect(self.rename_files)
        self.rename_btn.setToolTip("Rename matched files  (Ctrl+R)")

        ar.addWidget(self.undo_btn); ar.addWidget(self.redo_btn); ar.addWidget(self.undo_batch_btn)
        ar.addStretch()
        ar.addWidget(self.rename_btn)
        v.addLayout(ar)
        return panel

    # ── Footer ────────────────────────────────────────────────────
    def _footer(self):
        foot = QWidget(); foot.setFixedHeight(120)
        foot.setStyleSheet(f"QWidget {{ background:{C_BG}; border-top:1px solid {C_BORDER}; }}")
        v = QVBoxLayout(foot); v.setContentsMargins(18,8,18,8); v.setSpacing(4)
        row = QHBoxLayout()
        fl = QLabel("ACTIVITY LOG"); fl.setObjectName("section_title"); row.addWidget(fl)
        row.addStretch()
        exp = QPushButton("Export"); exp.setObjectName("icon_btn"); exp.setFixedHeight(22)
        exp.setToolTip("Save activity log to a text file")
        exp.clicked.connect(self._export_log); row.addWidget(exp)
        clr = QPushButton("Clear"); clr.setObjectName("icon_btn"); clr.setFixedHeight(22)
        clr.clicked.connect(lambda: self.status_text.clear()); row.addWidget(clr)
        v.addLayout(row)
        self.status_text = QTextEdit(); self.status_text.setReadOnly(True); v.addWidget(self.status_text)
        return foot

    # ── Drag & drop ───────────────────────────────────────────────
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
    def dropEvent(self, e):
        self.add_files_list([u.toLocalFile() for u in e.mimeData().urls()])
        e.acceptProposedAction()

    # ── Context menus ─────────────────────────────────────────────
    def _file_context_menu(self, pos):
        item = self.original_list.itemAt(pos)
        menu = QMenu(self)
        if item:
            open_act = QAction("\U0001f4c2  Open containing folder", self)
            open_act.triggered.connect(lambda: self._open_folder(item))
            menu.addAction(open_act)
            menu.addSeparator()
            rem_act = QAction("\u2212  Remove selected", self)
            rem_act.triggered.connect(self.remove_selected)
            menu.addAction(rem_act)
        add_act = QAction("+  Add files\u2026", self)
        add_act.triggered.connect(self.add_files)
        menu.addAction(add_act)
        folder_act = QAction("+  Add folder\u2026", self)
        folder_act.triggered.connect(self.add_folder)
        menu.addAction(folder_act)
        menu.exec(self.original_list.mapToGlobal(pos))

    def _preview_context_menu(self, pos):
        idx = self.new_names_list.indexAt(pos).row()
        if idx < 0 or idx >= len(self.files): return
        menu = QMenu(self)

        # "Show in folder" — opens the renamed output folder if the file has
        # already been processed, otherwise falls back to the source folder.
        fp = self.files[idx]
        rename_dests = getattr(self, '_rename_dests', {})
        show_path = rename_dests.get(fp, fp)
        folder = str(Path(show_path).parent)
        show_act = QAction("\U0001f4c2  Show in folder", self)
        show_act.triggered.connect(lambda _=None, f=folder: self._xdg_open(f))
        menu.addAction(show_act)
        menu.addSeparator()

        rematch_act = QAction("\U0001f50d  Search manually for this file", self)
        rematch_act.triggered.connect(lambda: self._manual_search(idx))
        menu.addAction(rematch_act)
        clear_act = QAction("\u2715  Clear match for this file", self)
        clear_act.triggered.connect(lambda: self._clear_match(idx))
        menu.addAction(clear_act)
        menu.exec(self.new_names_list.mapToGlobal(pos))

    def _xdg_open(self, path: str):
        """Open *path* in the system file manager (cross-platform)."""
        import subprocess, sys
        if sys.platform == "darwin":
            subprocess.run(["open", path])
        elif sys.platform == "win32":
            subprocess.run(["explorer", path])
        else:
            subprocess.run(["xdg-open", path])

    def _open_folder(self, item):
        idx = self.original_list.row(item)
        if 0 <= idx < len(self.files):
            self._xdg_open(str(Path(self.files[idx]).parent))

    def _manual_search(self, idx):
        """Let user type a manual search query for a specific file."""
        fp = self.files[idx]
        query, ok = QInputDialog.getText(
            self, "Manual Search",
            f"Search query for:\n{os.path.basename(fp)}\n\n"
            "Enter title (and optionally year, e.g. 'Inception 2010'):"
        )
        if not ok or not query.strip(): return

        import re
        q = query.strip()

        # IMDb ID shortcut — tt followed by digits
        if re.match(r'^tt\d+$', q, re.IGNORECASE):
            result = self.matcher.search_by_imdb_id(q)
            if not result:
                QMessageBox.information(self, "No Results", f"No TMDB match found for IMDb ID '{q}'.")
                return
            results = [result]
        else:
            # Simple search — strip year from end if provided
            parts = q.rsplit(None, 1)
            year = None
            title = q
            if len(parts) == 2 and re.match(r'^\d{4}$', parts[1]):
                title = parts[0]; year = int(parts[1])
            results = self.matcher.search_movies(title, year) or self.matcher.search_tv_shows(title)
        if not results:
            QMessageBox.information(self, "No Results", f"No results found for '{query}'.")
            return

        # Show picker
        choices = [f"{r['title']} ({r.get('year','?')})  [{r['type']}]" for r in results]
        choice, ok = QInputDialog.getItem(self, "Select Match", "Choose the correct match:", choices, 0, False)
        if not ok: return

        chosen = results[choices.index(choice)]
        try:
            new_name = self.renamer.generate_new_name(fp, chosen, self.naming_scheme_input.text())
        except Exception as exc:
            QMessageBox.critical(self, "Name Error", f"Could not generate filename:\n{exc}")
            return
        self.matches[idx] = chosen
        item = self.new_names_list.item(idx)
        if item:
            item.setText(new_name)
            item.setForeground(QColor(C_SUCCESS))
        self._log(f"\u270f  Manual match: {os.path.basename(fp)} \u2192 {chosen['title']}")
        matched = sum(1 for m in self.matches if m)
        self.rename_btn.setEnabled(matched > 0)
        self._update_stats()

    def _clear_match(self, idx):
        self.matches[idx] = None
        item = self.new_names_list.item(idx)
        item.setText(f"[cleared]  {os.path.basename(self.files[idx])}")
        item.setForeground(QColor(C_TEXT_DIM))
        matched = sum(1 for m in self.matches if m)
        self.rename_btn.setEnabled(matched > 0)
        self._update_stats()

    # ── File management ───────────────────────────────────────────
    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Media Files", "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.m4v *.mpg *.mpeg *.flv *.wmv);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog)
        if files: self.add_files_list(files)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Folder", "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog)
        if not folder: return
        self._log(f"\u27f3  Scanning folder: {os.path.basename(folder)}\u2026")
        self._scan_worker = FolderScanWorker([folder])
        self._scan_worker.files_found.connect(self._on_folder_scan_done)
        self._scan_worker.status.connect(self._log)
        self._scan_worker.start()

    def _on_folder_scan_done(self, found):
        if found:
            self.add_files_list(found)
        else:
            self._log("\u26a0  No media files found in selected folder.")

    def add_files_list(self, paths):
        # Split into files and dirs — dirs get scanned in a background thread
        dirs  = [p for p in paths if os.path.isdir(p)]
        files = [p for p in paths if not os.path.isdir(p)]

        # Add plain files immediately (fast, no I/O)
        if files:
            self._add_resolved_files(files)

        # Scan any dropped/added directories in background
        if dirs:
            self._log(f"\u27f3  Scanning {len(dirs)} folder(s)\u2026")
            self._scan_worker = FolderScanWorker(dirs)
            self._scan_worker.files_found.connect(self._add_resolved_files)
            self._scan_worker.status.connect(self._log)
            self._scan_worker.start()

    def _add_resolved_files(self, paths):
        """Add a flat list of file paths (no dirs) to the file list. Deduplicates."""
        added = 0
        existing = set(self.files)
        for path in paths:
            if path not in existing:
                existing.add(path)
                self.files.append(path)
                self._add_file_item(path)
                added += 1
        if added:
            self.matches.extend([None] * added)
            self._log(f"+ Added {added} file(s)")
            self._refresh_ui()

    def _add_file_item(self, path):
        item = QListWidgetItem(os.path.basename(path))
        item.setToolTip(path); item.setForeground(QColor(C_TEXT_MID))
        self.original_list.addItem(item)

    def remove_selected(self):
        rows = sorted([self.original_list.row(i) for i in self.original_list.selectedItems()], reverse=True)
        if not rows: return
        for r in rows:
            self.original_list.takeItem(r)
            self.files.pop(r)
            if r < len(self.matches): self.matches.pop(r)
            if r < self.new_names_list.count(): self.new_names_list.takeItem(r)
        self._log(f"\u2212  Removed {len(rows)} file(s)")
        self._refresh_ui(); self._update_stats()

    def _apply_filter(self, text):
        text = text.lower()
        for i in range(self.original_list.count()):
            item = self.original_list.item(i)
            item.setHidden(text not in item.text().lower())

    def _refresh_ui(self):
        n = len(self.files)
        self.file_count_lbl.setText(f"{n} file{'s' if n!=1 else ''} loaded")
        self.file_stack.setCurrentIndex(1 if n > 0 else 0)
        if n == 0: self.stat_matched.setText("—"); self.stat_matched.setObjectName("stat_dim")

    def clear_files(self):
        self.files.clear(); self.matches.clear()
        self.original_list.clear(); self.new_names_list.clear()
        self.rename_btn.setEnabled(False)
        self._refresh_ui(); self._log("\u2014 List cleared")

    def browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog)
        if d: self.output_dir_input.setText(d)

    def _open_duplicates(self):
        dlg = DuplicateFinderDialog(self)
        dlg.exec()

    def _open_watch_folder(self):
        dlg = WatchFolderDialog(self)
        dlg.files_detected.connect(self.add_files_list)
        dlg.exec()

    def _on_source_changed(self, source: str):
        """Show an info message when user picks TVDB or AniDB (both use TMDB backend).
        Only shown once per source per session to avoid repeated interruptions."""
        if source in ("TheTVDB", "AniDB") and source not in self._warned_sources:
            self._warned_sources.add(source)
            QMessageBox.information(
                self,
                f"{source} — Note",
                f"{source} is listed as a source option but currently uses TheMovieDB as its\n"
                "matching backend. Native integration is planned for a future release.\n\n"
                "Your match results will still be correct — TMDB covers the same catalogue.",
            )

    def _open_sonarr_radarr(self):
        dlg = SonarrRadarrDialog(self)
        dlg.exec()

    def _open_missing_episodes(self):
        if not any(m for m in self.matches if m and m.get("type") == "tv"):
            QMessageBox.information(self, "No TV Matches",
                "Match some TV show files first, then use this to check for missing episodes.")
            return
        dlg = MissingEpisodesDialog(self.matches, self.matcher, self)
        dlg.exec()

    @staticmethod
    def _clean_scene_name(filename: str) -> str:
        """Strip scene release tags for cleaner matching.
        e.g. Movie.2023.1080p.BluRay.x264-GROUP -> Movie 2023
        """
        import re
        stem = Path(filename).stem
        stem = re.sub(r'[._]', ' ', stem)
        TAGS = (
            r'\b(1080p|720p|480p|2160p|4K|UHD|HDR|SDR|BluRay|BDRip|BRRip)'
            r'|\b(WEB-?DL|WEBRip|HDTV|DVDRip|DVDScr|CAM|REMUX|RETAIL)'
            r'|\b(x264|x265|H264|H265|HEVC|AVC|xvid|divx|AV1)'
            r'|\b(AAC|AC3|DTS|DD5|DD2|MP3|FLAC|TrueHD|Atmos|EAC3)'
            r'|\b(PROPER|REPACK|EXTENDED|THEATRICAL|UNRATED|DIRECTORS CUT)'
            r'|\b(NF|AMZN|DSNP|HMAX|PCOK|ATVP|iP)'
            r'|\[.*?\]|\((?!\d{4}\))\S+\)'
        )
        stem = re.sub(TAGS, ' ', stem, flags=re.IGNORECASE)
        stem = re.sub(r' {2,}', ' ', stem).strip()
        return stem

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.matcher = MediaMatcher()
            key_preview = os.environ.get("TMDB_API_KEY","").strip()
            _bad = {"","YOUR_TMDB_API_KEY_HERE","YOUR_TMDB_API_KEY"}
            if key_preview and key_preview not in _bad:
                self._log(f"\u2713  API key active: \u2026{key_preview[-6:]}")
            else:
                self._log("\u26a0  No valid TMDB API key — check Settings.")

    def _open_jobs(self):
        """Open the Batch Jobs dialog (Docker only — requires API)."""
        dlg = BatchJobsDialog(self)
        dlg.exec()

    def _update_stats(self):
        total   = len(self.files)
        matched = sum(1 for m in self.matches if m)
        if total == 0:
            self.stat_matched.setText("—")
            self.stat_matched.setObjectName("stat_dim")
        elif matched == total:
            self.stat_matched.setText(f"\u2713 {matched}/{total} matched")
            self.stat_matched.setObjectName("stat_ok")
        elif matched > 0:
            self.stat_matched.setText(f"{matched}/{total} matched")
            self.stat_matched.setObjectName("stat_dim")
        else:
            self.stat_matched.setText(f"\u2717 0/{total} matched")
            self.stat_matched.setObjectName("stat_err")
        # Force style refresh
        self.stat_matched.style().unpolish(self.stat_matched)
        self.stat_matched.style().polish(self.stat_matched)

    # ── Matching ──────────────────────────────────────────────────
    def match_files(self):
        if not self.files:
            QMessageBox.warning(self,"No Files","Please add media files first."); return
        _BAD_KEYS = {"","YOUR_TMDB_API_KEY_HERE","YOUR_TMDB_API_KEY"}
        key = os.environ.get("TMDB_API_KEY","").strip()
        if key in _BAD_KEYS:
            reply = QMessageBox.warning(self,"TMDB API Key Missing",
                "No TMDB API key found.\n\nGo to Settings \u2192 paste your key.\n"
                "Get a free key at: https://www.themoviedb.org/settings/api\n\nOpen Settings now?",
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes: self._open_settings()
            return

        self._log(f"\u27f3  Matching {len(self.files)} file(s)\u2026")
        self.match_btn.setEnabled(False); self.rename_btn.setEnabled(False)
        self.progress_bar.setVisible(True); self.progress_bar.setValue(0)
        self.matches = [None]*len(self.files)
        self.new_names_list.clear()
        for _ in self.files:
            item = QListWidgetItem("\u2026"); item.setForeground(QColor(C_TEXT_DIM))
            self.new_names_list.addItem(item)

        # Scene name cleaning: strip release tags before matching
        hint_names = None
        if self.clean_scene_check.isChecked():
            hint_names = [self._clean_scene_name(fp) for fp in self.files]
            self._log(f"✦  Scene name cleaning enabled — stripped release tags from {len(self.files)} filename(s)")

        self.match_worker = MatchWorker(
            self.files, self.data_source_combo.currentText(),
            self.naming_scheme_input.text(), self.matcher, self.renamer,
            hint_names=hint_names)
        self.match_worker.progress.connect(self.progress_bar.setValue)
        self.match_worker.status.connect(self._log)
        self.match_worker.matched.connect(self._on_match_result)
        self.match_worker.finished.connect(self._on_match_finished)
        self.match_worker.hard_error.connect(self._on_match_hard_error)
        self.match_worker.finished.connect(self.match_worker.deleteLater)
        self.match_worker.start()

    def _on_match_result(self, idx, mi, nn):
        self.matches[idx] = mi
        item = self.new_names_list.item(idx); item.setText(nn)
        if mi:
            item.setForeground(QColor(C_TEXT))
        elif "[error]" in nn:
            item.setForeground(QColor(C_ERROR))
        else:
            item.setForeground(QColor(C_TEXT_DIM))
        self._update_stats()

    def _on_match_hard_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.match_btn.setEnabled(True)
        if self.match_worker is not None:
            self.match_worker.stop()  # Signal the loop to exit at next iteration
        if "401" in error_msg or "Unauthorized" in error_msg or "invalid" in error_msg.lower():
            reply = QMessageBox.critical(self,"Invalid API Key",
                "TMDB rejected the API key (401 Unauthorized).\n\n"
                "Copy your key directly from:\nhttps://www.themoviedb.org/settings/api\n\n"
                "Open Settings now?",
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes: self._open_settings()
        elif "Network" in error_msg or "Connection" in error_msg:
            QMessageBox.critical(self,"Network Error",
                f"Cannot reach TMDB:\n{error_msg}\n\n"
                "In Docker, ensure the container has internet:\n"
                "  docker run --network=host ...")
        else:
            QMessageBox.critical(self,"Match Error", error_msg)

    def _on_match_finished(self, matched, total):
        self.progress_bar.setVisible(False)
        self.match_btn.setEnabled(True)
        self.rename_btn.setEnabled(matched > 0)
        self._log(f"\u2713  Matched {matched}/{total} files.")
        self._update_stats()

    # ── Subtitles ─────────────────────────────────────────────────
    def fetch_subtitles(self):
        if not self.files:
            QMessageBox.warning(self, "No Files", "Please add files first."); return
        lang = self.sub_lang_combo.currentText()
        self._log(f"\u27f3  Fetching subtitles ({lang})\u2026")
        self.fetch_subs_btn.setEnabled(False)
        self._sub_worker = SubtitleWorker(self.files, language=lang)
        self._sub_worker.status.connect(self._log)
        self._sub_worker.finished.connect(self._on_subs_finished)
        self._sub_worker.finished.connect(self._sub_worker.deleteLater)
        self._sub_worker.start()

    def _on_subs_finished(self, fetched, total):
        self.fetch_subs_btn.setEnabled(True)
        self._log(f"\u2713  Subtitles: {fetched}/{total} downloaded.")

    # ── Rename ────────────────────────────────────────────────────
    def rename_files(self):
        if not self.files or not any(self.matches):
            QMessageBox.warning(self,"Nothing to Rename","Please match files first."); return
        matched = sum(1 for m in self.matches if m)
        dry_run = self.dry_run_check.isChecked()
        copy_mode = self.copy_radio.isChecked()

        mode_str = "DRY RUN (no files will be changed)" if dry_run else ("Copy" if copy_mode else "Move/rename")
        confirm = QMessageBox.question(self,"Confirm Rename",
            f"Mode: {mode_str}\n\nProcess {matched} matched file(s)?",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if confirm != QMessageBox.StandardButton.Yes: return

        self.progress_bar.setVisible(True); self.progress_bar.setValue(0)
        self.rename_btn.setEnabled(False); self.match_btn.setEnabled(False)
        # Record history position so "Undo Batch" can revert all ops in this run
        self._batch_start_op_idx = self.history.current_index

        conflict_map = {"Skip (keep existing)": "skip", "Overwrite": "overwrite", "Rename with suffix": "suffix"}
        on_conflict = conflict_map.get(self.conflict_combo.currentText(), "skip")

        self.worker = RenameWorker(
            self.files, self.matches,
            self.output_dir_input.text().strip() or None,
            self.naming_scheme_input.text(),
            download_artwork=self.download_artwork_check.isChecked(),
            write_metadata=self.write_metadata_check.isChecked(),
            dry_run=dry_run,
            copy_mode=copy_mode,
            write_nfo=self.write_nfo_check.isChecked(),
            download_fanart=self.download_fanart_check.isChecked(),
            on_conflict=on_conflict)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.status.connect(self._log)
        self.worker.operation_complete.connect(self._on_op_complete)
        self.worker.finished.connect(self._rename_finished)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _on_op_complete(self, orig, new, mi):
        self.history.add_operation(orig, new, mi); self._update_undo_redo()
        # Track rename destinations so "Show in folder" can open the output folder
        if not hasattr(self, '_rename_dests'):
            self._rename_dests = {}
        self._rename_dests[orig] = new

    def _rename_finished(self, ok, msg):
        self.progress_bar.setVisible(False)
        self.rename_btn.setEnabled(True); self.match_btn.setEnabled(True)
        self._log(("\u2713  " if ok else "\u2717  ") + msg); self._update_undo_redo()
        if not ok:
            QMessageBox.critical(self, "Rename Error", msg)
            return

        # Enable Undo Batch if any ops were recorded in this run
        if self._batch_start_op_idx is not None:
            ops_this_batch = self.history.current_index - self._batch_start_op_idx
        else:
            ops_this_batch = 0
        self.undo_batch_btn.setEnabled(ops_this_batch > 0)

        # Offer Sonarr/Radarr library refresh if configured and not a dry run
        if not self.dry_run_check.isChecked() and ok:
            settings = load_settings()
            sonarr_url = settings.get("sonarr_url", "").strip()
            radarr_url = settings.get("radarr_url", "").strip()
            has_tv     = any(m and m.get("type") == "tv"    for m in self.matches if m)
            has_movie  = any(m and m.get("type") == "movie" for m in self.matches if m)
            arr_targets = []
            if has_tv    and sonarr_url: arr_targets.append(("Sonarr", sonarr_url, settings.get("sonarr_key", "")))
            if has_movie and radarr_url: arr_targets.append(("Radarr", radarr_url, settings.get("radarr_key", "")))
            if arr_targets:
                names = " & ".join(t[0] for t in arr_targets)
                reply = QMessageBox.question(self, "Refresh Library?",
                    f"Trigger library scan in {names}?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes)
                if reply == QMessageBox.StandardButton.Yes:
                    self._trigger_arr_refresh(arr_targets)

    def _trigger_arr_refresh(self, arr_targets):
        """POST a RescanMovie / RefreshSeries command to Sonarr/Radarr."""
        import urllib.request, urllib.error
        for name, base_url, api_key in arr_targets:
            try:
                url     = base_url.rstrip("/") + "/api/v3/command"
                command = "RescanMovie" if name == "Radarr" else "RefreshSeries"
                body    = json.dumps({"name": command}).encode()
                req     = urllib.request.Request(url, data=body, method="POST")
                req.add_header("X-Api-Key", api_key)
                req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req, timeout=8):
                    self._log(f"\u2713  {name} library scan triggered")
            except Exception as exc:
                self._log(f"\u26a0  {name} refresh failed: {exc}")

    # ── Undo / Redo ───────────────────────────────────────────────
    def _update_undo_redo(self):
        self.undo_btn.setEnabled(self.history.can_undo())
        self.redo_btn.setEnabled(self.history.can_redo())

    def undo_rename(self):
        op = self.history.undo()
        if not op: return
        src, dst = op['new_path'], op['original_path']
        if not os.path.exists(src):
            # File was already moved or is missing — revert index so undo stays consistent
            self.history.revert_undo()
            QMessageBox.warning(self, "Undo Failed", f"File not found:\n{src}")
            return
        try:
            shutil.move(src, dst)
            self._log(f"\u21a9  Undone: {os.path.basename(src)}")
        except Exception as e:
            # Revert index — operation did not complete
            self.history.revert_undo()
            QMessageBox.critical(self, "Error", f"Undo failed: {e}")
        self._update_undo_redo()

    def redo_rename(self):
        op = self.history.redo()
        if not op: return
        src, dst = op['original_path'], op['new_path']
        if not os.path.exists(src):
            # Revert index — source is gone
            self.history.revert_redo()
            QMessageBox.warning(self, "Redo Failed", f"Source no longer exists:\n{src}")
            return
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            self._log(f"\u21aa  Redone: {os.path.basename(dst)}")
        except Exception as e:
            # Revert index — operation did not complete
            self.history.revert_redo()
            QMessageBox.critical(self, "Error", f"Redo failed: {e}")
        self._update_undo_redo()

    def undo_batch(self):
        """Undo all rename operations performed in the last Rename run."""
        target_idx = getattr(self, '_batch_start_op_idx', None)
        if target_idx is None or self.history.current_index <= target_idx:
            self.undo_batch_btn.setEnabled(False)
            return
        ops_to_undo = self.history.current_index - target_idx
        failed = 0
        for _ in range(ops_to_undo):
            op = self.history.undo()
            if not op:
                break
            src, dst = op['new_path'], op['original_path']
            if not os.path.exists(src):
                self.history.revert_undo()
                failed += 1
                continue
            try:
                shutil.move(src, dst)
                self._log(f"\u21a9  Batch undo: {os.path.basename(src)}")
            except Exception as e:
                self.history.revert_undo()
                self._log(f"\u26a0  Batch undo failed: {os.path.basename(src)} — {e}")
                failed += 1
        self._update_undo_redo()
        self.undo_batch_btn.setEnabled(False)
        self._log(f"\u2713  Batch undo complete ({ops_to_undo - failed} reversed{', ' + str(failed) + ' failed' if failed else ''})")

    # ── Log export ────────────────────────────────────────────────
    def _export_log(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Activity Log",
            str(Path.home() / "sortiq_log.txt"),
            "Text Files (*.txt)",
            options=QFileDialog.Option.DontUseNativeDialog)
        if path:
            Path(path).write_text(self.status_text.toPlainText(), encoding="utf-8")
            self._log(f"\u2713  Log exported to {path}")

    # ── Presets ───────────────────────────────────────────────────
    def load_preset(self, name):
        s = self.preset_manager.get_preset(name)
        if s:
            # Block signals to avoid double-refresh; setText triggers textChanged
            self.naming_scheme_input.blockSignals(True)
            self.naming_scheme_input.setText(s)
            self.naming_scheme_input.blockSignals(False)
            self._refresh_preview()

    def _refresh_preview(self):
        """Re-render the RENAMED PREVIEW list using cached match data + current scheme.
        Also detects rename conflicts (two files → same output path) and flags them.
        """
        if not self.files or not hasattr(self, 'matches') or not self.matches:
            return
        scheme = self.naming_scheme_input.text().strip() or "{n} ({y})"

        # First pass: generate all new names
        new_names = []
        for fp, mi in zip(self.files, self.matches):
            if mi:
                try:
                    nn = self.renamer.generate_new_name(fp, mi, scheme)
                except Exception:
                    nn = None
            else:
                nn = None
            new_names.append(nn)

        # Detect conflicts: same output name from different source files
        from collections import Counter
        name_counts = Counter(n for n in new_names if n)
        conflicts = {n for n, c in name_counts.items() if c > 1}

        # Second pass: update list items with colour coding
        for idx, (nn, item_) in enumerate(zip(new_names, [
                self.new_names_list.item(i) for i in range(self.new_names_list.count())])):
            if item_ is None: continue
            if nn is None: continue
            item_.setText(nn)
            if nn in conflicts:
                item_.setForeground(QColor(C_AMBER))
                item_.setToolTip("⚠ Rename conflict: another file will produce the same output name")
            else:
                item_.setForeground(QColor(C_TEXT))
                item_.setToolTip("")

        if conflicts:
            self._log(f"⚠  {len(conflicts)} rename conflict(s) detected — check amber items in preview")

    def save_current_preset(self):
        scheme = self.naming_scheme_input.text().strip()
        if not scheme: QMessageBox.warning(self,"Empty Scheme","Enter a naming scheme first."); return
        name,ok = QInputDialog.getText(self,"Save Preset","Preset name:")
        if ok and name:
            self.preset_manager.save_preset(name,scheme)
            self.preset_combo.clear(); self.preset_combo.addItems(self.preset_manager.list_presets())
            self.preset_combo.setCurrentText(name); self._log(f"\u2713  Preset saved: {name}")

    # ── Keyboard shortcuts ────────────────────────────────────────
    def keyPressEvent(self, event):
        mods = event.modifiers()
        key  = event.key()
        Ctrl = Qt.KeyboardModifier.ControlModifier
        if mods == Ctrl:
            if key == Qt.Key.Key_Z:
                if self.history.can_undo(): self.undo_rename()
                return
            if key == Qt.Key.Key_Y:
                if self.history.can_redo(): self.redo_rename()
                return
            if key == Qt.Key.Key_R:
                if self.rename_btn.isEnabled(): self.rename_files()
                return
            if key == Qt.Key.Key_M:
                if self.match_btn.isEnabled(): self.match_files()
                return
            if key == Qt.Key.Key_Comma:
                self._open_settings()
                return
        if key == Qt.Key.Key_Delete:
            if self.original_list.hasFocus():
                self.remove_selected()
            return
        if key == Qt.Key.Key_Escape:
            if self.match_worker is not None:
                self.match_worker.stop()
                self._log("\u23f9  Match cancelled by user")
            return
        super().keyPressEvent(event)

    def _log(self, msg):
        self.status_text.append(msg)
        self.status_text.verticalScrollBar().setValue(self.status_text.verticalScrollBar().maximum())


# ── Entry ─────────────────────────────────────────────────────────────────────

def main():
    # AppImage: set platform hints before QApplication is constructed so the
    # window manager can apply full decorations (minimize / maximize / close).
    # Prefer Wayland when WAYLAND_DISPLAY is set (covers Fedora/GNOME Wayland
    # sessions where DISPLAY is also set via XWayland). Fall back to xcb only
    # on pure X11 sessions. Qt 6.5+ xcb requires libxcb-cursor which may not
    # be installed; Wayland avoids that dependency entirely.
    if os.environ.get("APPIMAGE"):
        if not os.environ.get("QT_QPA_PLATFORM"):
            # Only override if not already set; respect user's choice.
            if os.environ.get("WAYLAND_DISPLAY"):
                os.environ["QT_QPA_PLATFORM"] = "wayland"
            elif os.environ.get("DISPLAY"):
                os.environ["QT_QPA_PLATFORM"] = "xcb"
        # Disable DPI scaling quirks that can strip window decorations on HiDPI
        os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "0")
        # Prevent Qt from loading qgnomeplatform/portal theme.
        # The portal file dialog (org.freedesktop.portal.FileChooser) sends a
        # D-Bus request that can hang indefinitely in an AppImage environment.
        # Clearing the platform theme forces Qt's own built-in file picker,
        # which needs no D-Bus. D-Bus itself stays alive so GNOME's
        # xdg-decoration protocol can apply window buttons (min/max/close).
        os.environ.setdefault("QT_QPA_PLATFORMTHEME", "")

    app = QApplication(sys.argv)
    app.setApplicationName("SortIQ")
    app.setDesktopFileName("sortiq")   # links running window → .desktop → taskbar icon on Linux
    app.setWindowIcon(_app_icon())
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,           QColor(C_BG))
    pal.setColor(QPalette.ColorRole.WindowText,       QColor(C_TEXT))
    pal.setColor(QPalette.ColorRole.Base,             QColor(C_SURFACE))
    pal.setColor(QPalette.ColorRole.AlternateBase,    QColor(C_PANEL))
    pal.setColor(QPalette.ColorRole.Text,             QColor(C_TEXT))
    pal.setColor(QPalette.ColorRole.Button,           QColor(C_PANEL))
    pal.setColor(QPalette.ColorRole.ButtonText,       QColor(C_TEXT))
    pal.setColor(QPalette.ColorRole.Highlight,        QColor(C_AMBER_DIM))
    pal.setColor(QPalette.ColorRole.HighlightedText,  QColor("#000"))
    pal.setColor(QPalette.ColorRole.ToolTipBase,      QColor(C_PANEL))
    pal.setColor(QPalette.ColorRole.ToolTipText,      QColor(C_TEXT))
    app.setPalette(pal)
    app.setStyleSheet(STYLESHEET)
    win = SortIQApp()

    # ── Docker: maximise to fill virtual display exactly ──────────────────────
    if os.environ.get("RUNNING_IN_DOCKER"):
        geo = os.environ.get("SORTIQ_GEOMETRY", "")
        if geo and "x" in geo:
            try:
                w, h = (int(x) for x in geo.split("x"))
                win.resize(w, h)
                win.move(0, 0)
            except ValueError:
                pass
        win.showMaximized()
    else:
        win.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
