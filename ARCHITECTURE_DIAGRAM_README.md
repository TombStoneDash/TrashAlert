# Architecture Diagram Generation

This directory contains architecture diagram resources for TrashAlert.

## Files

1. **ARCHITECTURE_DIAGRAM.txt** - Detailed ASCII/text-based architecture diagrams
2. **generate_diagram.py** - Python script to generate visual PNG diagram

## Generating the Visual Diagram

### Option 1: Using Python Script (Recommended)

```bash
# Install Pillow
pip install pillow

# Run generator
python3 generate_diagram.py
```

This will create `ARCHITECTURE_DIAGRAM.png` with a professional visual diagram.

### Option 2: Online Diagramming Tools

Use the text diagram as reference and recreate in:

1. **draw.io** (https://app.diagrams.net)
   - Free, professional quality
   - Export as PNG, SVG, PDF
   - Recommended for presentations

2. **Excalidraw** (https://excalidraw.com)
   - Hand-drawn style
   - Great for informal presentations
   - Export as PNG or SVG

3. **Lucidchart** (https://www.lucidchart.com)
   - Professional diagramming
   - Team collaboration
   - Export options

### Option 3: Screenshot Text Diagram

```bash
# View in terminal with nice font
cat ARCHITECTURE_DIAGRAM.txt

# Take screenshot or use:
# - iTerm2 (Mac): Cmd+Shift+4, select window
# - Windows: Snipping Tool
# - Linux: gnome-screenshot or scrot
```

## Diagram Contents

The architecture diagram includes:

1. **Client Layer** - Web, iOS, Android, API integrations
2. **Infrastructure Layer** - Nginx reverse proxy, SSL, rate limiting
3. **Application Layer** - FastAPI, business logic, caching
4. **Data Layer** - PostgreSQL database schema
5. **External Sources** - OSM, municipal websites, hauler APIs

Plus:
- Data flow diagrams (lookup, report, consensus)
- Deployment architecture
- Security layers
- Monitoring setup

## For Investors/Presentations

Recommended approach:
1. Generate PNG using Python script
2. Import to PowerPoint/Keynote
3. Add annotations specific to your pitch
4. Export as high-quality PDF

## Customization

Edit `generate_diagram.py` to customize:
- Colors (COLOR_* variables)
- Layout (box positions)
- Content (labels and descriptions)
- Size (width, height variables)

## Questions?

The text diagram in `ARCHITECTURE_DIAGRAM.txt` is comprehensive and can be used as-is for technical documentation.
