"""
scraper_bridge.py — thin subprocess wrapper around the Skyscraper CLI.
Skyscraper handles ScreenScraper auth via its own config (~/.skyscraper/config.ini).
We write the credentials there before invoking it.
"""
import os
import subprocess
import shutil
import configparser
from pathlib import Path
from settings import settings
from config import SKYSCRAPER_CANDIDATES


def find_skyscraper_bin() -> str | None:
    stored = settings.get("skyscraper_bin", "")
    if stored and os.path.isfile(stored) and os.access(stored, os.X_OK):
        return stored
    for candidate in SKYSCRAPER_CANDIDATES:
        found = shutil.which(candidate)
        if found:
            return found
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def write_skyscraper_credentials(user: str, password: str):
    """Inject credentials into ~/.skyscraper/config.ini."""
    cfg_dir = Path.home() / ".skyscraper"
    cfg_dir.mkdir(exist_ok=True)
    cfg_file = cfg_dir / "config.ini"

    config = configparser.ConfigParser()
    if cfg_file.exists():
        config.read(str(cfg_file))

    if "screenscraper" not in config:
        config["screenscraper"] = {}
    config["screenscraper"]["userCreds"] = f"{user}:{password}"

    with open(str(cfg_file), "w") as f:
        config.write(f)


def build_skyscraper_command(
    platform: str,
    rom_path: str,
    roms_dir: str,
    media_dir: str | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    binary = find_skyscraper_bin()
    if not binary:
        raise FileNotFoundError("Skyscraper binary not found. Set path in Settings.")

    cmd = [
        binary,
        "-p", platform,
        "-s", "screenscraper",
        "-i", roms_dir,
    ]
    if media_dir:
        cmd += ["-a", media_dir]  # artwork output dir
    if extra_args:
        cmd += extra_args

    # Single ROM mode: pass the specific file
    cmd.append(rom_path)
    return cmd


def build_skyscraper_bulk_command(
    platform: str,
    roms_dir: str,
    media_dir: str | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    binary = find_skyscraper_bin()
    if not binary:
        raise FileNotFoundError("Skyscraper binary not found. Set path in Settings.")

    cmd = [
        binary,
        "-p", platform,
        "-s", "screenscraper",
        "-i", roms_dir,
    ]
    if media_dir:
        cmd += ["-a", media_dir]
    if extra_args:
        cmd += extra_args
    return cmd


def build_skyscraper_generate_command(
    platform: str,
    roms_dir: str,
    gamelist_output_dir: str,
    extra_args: list[str] | None = None,
) -> list[str]:
    """
    Generate gamelist.xml from Skyscraper's cache (second pass).
    """
    binary = find_skyscraper_bin()
    if not binary:
        raise FileNotFoundError("Skyscraper binary not found. Set path in Settings.")

    cmd = [
        binary,
        "-p", platform,
        "-i", roms_dir,
        "--flags", "unattend",
    ]
    if extra_args:
        cmd += extra_args
    return cmd


class ScraperJob:
    """
    Runs a Skyscraper command in a subprocess, calling progress_cb(line)
    for each stdout line and done_cb(returncode) when finished.
    Uses threading — do NOT call from the main thread without the callbacks.
    """

    def __init__(self, cmd: list[str], progress_cb=None, done_cb=None):
        self.cmd = cmd
        self.progress_cb = progress_cb or (lambda line: None)
        self.done_cb = done_cb or (lambda rc: None)
        self._proc: subprocess.Popen | None = None
        self._cancelled = False

    def run(self):
        import threading
        t = threading.Thread(target=self._run_inner, daemon=True)
        t.start()
        return t

    def _run_inner(self):
        try:
            self._proc = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in self._proc.stdout:
                if self._cancelled:
                    self._proc.terminate()
                    break
                self.progress_cb(line.rstrip())
            self._proc.wait()
            self.done_cb(self._proc.returncode)
        except Exception as e:
            self.progress_cb(f"[ERROR] {e}")
            self.done_cb(-1)

    def cancel(self):
        self._cancelled = True
        if self._proc:
            self._proc.terminate()
