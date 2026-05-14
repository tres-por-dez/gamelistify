# Gamelistify

> Manage your EmulationStation and RetroBat game libraries with a full-featured desktop GUI. Edit metadata, hide or delete entries in bulk, scan for unregistered ROMs, preview artwork, and scrape with Skyscraper — all without touching XML by hand.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-GPL%20v3-green?style=flat-square)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey?style=flat-square)
![Status](https://img.shields.io/badge/Status-Active-brightgreen?style=flat-square)

---

## What is it?

Gamelistify is a desktop editor for `gamelist.xml` files used by [EmulationStation](https://emulationstation.org/) and [RetroBat](https://www.retrobat.org/). It gives you direct control over your game library metadata without manually editing XML — including bulk operations, artwork preview, ROM scanning, and full [Skyscraper](https://github.com/Gemba/skyscraper) scraping integration.

---

## Features

### Gamelist editor
- Open any `gamelist.xml` from EmulationStation or RetroBat
- Sortable table with all game entries — click any column header to sort
- Real-time text filter by name, genre, or developer
- Toggle visibility of hidden entries (shown in muted color)
- Favorites highlighted in gold, hidden entries in grey
- Automatic `.bak` backup before every save

### Bulk actions
- **Hide / Unhide** multiple entries at once
- **Favorite / Unfavorite** in bulk
- **Delete entries** from the gamelist without touching files on disk
- Multi-select with `Ctrl+Click` and `Shift+Click`

### Individual game editor
- Full metadata editor for every `gamelist.xml` field
- Boolean flags (`hidden`, `favorite`, `kidgame`) as checkboxes
- Media fields (`image`, `video`, `marquee`, `wheel`, `fanart`…) with file browser
- Live image preview inside the editor
- **Orphan media scanner** — detects artwork files in subfolders that aren't mapped in the XML yet

### ROM scanner
- Scans a folder recursively for ROM files
- Shows only ROMs **not already present** in the current gamelist
- Individual or bulk selection before adding

### Skyscraper integration
- **Scrape selected games** — runs Skyscraper for each selected ROM
- **Bulk scrape** — runs Skyscraper across the entire ROM folder
- Platform selection dialog before each session
- Real-time log output with cancel support
- Credentials written automatically to `~/.skyscraper/config.ini`

### Settings
- Skyscraper binary path (with file browser)
- ScreenScraper username and password
- Image preview size

---

## Screenshots

> *(add screenshots here)*

---

## Requirements

- Python 3.11+
- [Skyscraper](https://github.com/Gemba/skyscraper) — for scraping (optional)

---

## Installation

```bash
git clone https://github.com/yourusername/gamelistify.git
cd gamelistify
pip install -r requirements.txt
python main.py
```

### Dependencies

```
customtkinter>=5.2.0
lxml>=5.0.0
Pillow>=10.0.0
```

---

## Usage

### Opening a gamelist

`File → Open gamelist.xml` or `Ctrl+O`. Navigate to your system's ROM folder (e.g. `~/RetroBat/roms/megadrive/gamelist.xml`).

### Bulk hide or delete

Select multiple games with `Ctrl+Click` or `Shift+Click`, then use the toolbar buttons or the `Edit` menu.

### Scanning for missing ROMs

`View → Scan ROMs` opens the scanner. It reads the current gamelist's folder, finds ROM files not present in the XML, and lets you select which ones to add.

### Scraping

Configure your Skyscraper binary and ScreenScraper credentials in `Tools → Settings` first. Then select games and use `Scrape → Scrape Selected` or `Scrape → Scrape All (bulk)`.

### Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+O` | Open gamelist |
| `Ctrl+S` | Save |
| `Ctrl+A` | Select all |
| `Enter` / `Double-click` | Edit selected game |
| `Delete` | Remove selected entries |

---

## Project structure

```
gamelistify/
├── main.py              # Main UI (CustomTkinter)
├── gamelist_parser.py   # XML parse/write (lxml)
├── rom_scanner.py       # ROM folder scanner
├── scraper_bridge.py    # Skyscraper CLI subprocess wrapper
├── settings.py          # Persistent settings (JSON)
├── config.py            # Constants, ROM extensions, platforms
└── requirements.txt
```

---

## Supported media subfolders

Gamelistify resolves artwork from these standard EmulationStation subfolders automatically:

`images` · `videos` · `marquees` · `wheels` · `fanart` · `screenshots` · `boxart` · `box2dfront` · `box2dback` · `box3d` · `snap` · `titles` · `media/images` · `media/videos` · `media/marquees` · `media/wheels`

---

## Supported platforms (for scraping)

amiga · amstradcpc · arcade · atari2600 · atari5200 · atari7800 · atarilynx · c64 · dreamcast · fba · gb · gba · gbc · genesis · mastersystem · megadrive · msx · n64 · nds · neogeo · nes · pcengine · psp · psx · saturn · scummvm · sega32x · segacd · snes · and more.

---

## Notes

- Deleting a gamelist entry **never** removes the ROM or artwork from disk
- The `.bak` backup is overwritten on each save — keep a manual copy before large bulk operations if needed
- Skyscraper's scraping flow has two passes (fetch → generate). Gamelistify runs the fetch pass. Use Skyscraper's `--flags unattend` or run the generate pass separately to update your gamelist after scraping
- Orphan media detection matches by ROM filename stem against all standard media subfolders

---

## Contributing

Pull requests are welcome. For significant changes, open an issue first to discuss what you'd like to change.

---

## License

[GNU General Public License v3.0](LICENSE)