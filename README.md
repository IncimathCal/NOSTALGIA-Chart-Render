# NOSTALGIA Chart Render

A Python library for rendering static chart preview images from NOSTALGIA (Konami piano rhythm game) chart XML files.

---

## About This Project

This project was created with the assistance of **Claude Code** (Anthropic's AI coding assistant). The codebase, architecture decisions, and documentation were developed through iterative human-AI collaboration.

---

## Requirements

- Python 3.10+
- [Pillow](https://python-pillow.org/) >= 9.0.0 (image processing)
- [NumPy](https://numpy.org/) >= 1.21.0 (trill gradient layer computation)

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Purpose

This library converts NOSTALGIA chart XML files into high-resolution PNG static images ("chart planes") that visualize:

- All notes (Normal, Long, Glissando, Trill) with game-accurate textures
- Glissando chain connections with parallelogram links
- BPM changes and beat lines
- Variable speed zones
- Combo milestone markers (every 100 notes)
- Song metadata header (cover, title, artist, difficulty, level)

The output is a horizontally-tiled segmented image suitable for sharing or printing.

---

## Usage

### Quick Start

1. **Configure paths** in `render_chart.py`:

```python
# Path to your NOSTALGIA "contents" folder
CONTENTS_DIR = r"F:\NOSTALGIA\contents"

# Path to the assets folder (included in this repo)
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# Output directory
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
```

2. **Run the script**:

```bash
python render_chart.py <basename> <difficulty_number>
```

Difficulty numbers: `0=Normal`, `1=Hard`, `2=Expert`, `3=Real`

Examples:

```bash
python render_chart.py m_l0061_felys 3         # Real
python render_chart.py m_t0052_summerdiary 2   # Expert
python render_chart.py m_n0004_masumi 0        # Normal
```

### Using as a Library

```python
from NOSTALGIAChartRender import parse_chart, Renderer, set_assets_dir

set_assets_dir("./assets")

chart = parse_chart("path/to/chart.xml")
renderer = Renderer(
    chart=chart,
    song_title="Song Title",
    artist="Artist Name",
    difficulty="Expert",
    cover_path="./assets/covers/cover.jpg",
    level="12",
)
renderer.save("output.png")
```

---

## Project Structure

```
NOSTALGIAChartRender/
├── NOSTALGIAChartRender/      # Python library
│   ├── __init__.py
│   ├── element.py              # Data models (Chart, Note, Timing)
│   ├── parser.py               # XML parser
│   ├── render.py               # Rendering engine
│   ├── rhythm.py               # Rhythm analysis
│   ├── texture_loader.py       # Texture loading & caching
│   ├── theme.py                # Theme configuration
│   └── 谱面格式解析.md          # Full XML format documentation (Chinese)
├── assets/
│   ├── notes/                  # Note textures (merged from game sources)
│   └── covers/                 # Song cover images
├── output/                     # Default output directory
├── render_chart.py             # CLI entry point
├── requirements.txt            # Python dependencies
├── CLAUDE.md                   # Developer guide
└── README.md                   # This file
```

---

## Documentation

- **`谱面格式解析.md`** — Complete documentation of the NOSTALGIA chart XML format (in Chinese), covering all 6 top-level nodes and their fields.
- **`CLAUDE.md`** — Developer guide covering architecture, coordinate system, rendering pipeline, texture priorities, extension guides, and known issues.

---

## Notes

- You must own a legitimate copy of NOSTALGIA to obtain the `contents` folder and chart XML files.
- The `assets/notes/` textures were merged from multiple game texture sources (`data_op2/texture/notes_00/`, `notes_01/`, `data/texture/notes/`, and custom `output_assets/`) with correct search priority.
- Real difficulty levels are displayed with a `-10` offset (e.g., Real 12 → displayed as "Real 2").

---

## License

This is a fan-made tool for personal/educational use. All game assets and trademarks belong to Konami.
