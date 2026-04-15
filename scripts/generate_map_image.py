#!/usr/bin/env python3
"""Generate a street-level trash collection map image from Supabase data.

Produces a 4K (3840x2160) and 1080p (1920x1080) static image where every
address is a colored dot based on its collection day. At 274K+ San Diego
addresses, the dots are dense enough to trace residential streets.

Usage:
    python scripts/generate_map_image.py [--city san-diego] [--demo]

Requires:
    SUPABASE_URL and SUPABASE_KEY env vars (or use --demo for synthetic data)

Output:
    public/marketing/sd-collection-map-4k.png
    public/marketing/sd-collection-map-1080p.png
"""

import argparse
import csv
import logging
import math
import os
import sys
from pathlib import Path
from urllib.parse import quote

import requests
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "public" / "marketing"

# ---------------------------------------------------------------------------
# Color scheme — matches the spec
# ---------------------------------------------------------------------------
DAY_COLORS = {
    "monday":    (59, 130, 246),   # #3B82F6 blue
    "tuesday":   (34, 197, 94),    # #22C55E green
    "wednesday": (245, 158, 11),   # #F59E0B amber
    "thursday":  (139, 92, 246),   # #8B5CF6 purple
    "friday":    (239, 68, 68),    # #EF4444 red
    "saturday":  (249, 115, 22),   # #F97316 orange
    "sunday":    (107, 114, 128),  # #6B7280 gray
}

DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# ---------------------------------------------------------------------------
# Supabase fetching — paginated to get ALL addresses
# ---------------------------------------------------------------------------

SUPABASE_URL = os.getenv(
    "SUPABASE_URL",
    os.getenv("NEXT_PUBLIC_SUPABASE_URL", "https://qsuzfemakaaroeakyick.supabase.co"),
)
SUPABASE_KEY = os.getenv(
    "SUPABASE_KEY",
    os.getenv("SUPABASE_SERVICE_KEY", os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")),
)


def _supa_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }


def fetch_all_addresses(city_slug: str) -> list[dict]:
    """Fetch ALL addresses for a city from Supabase, paginated."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.error("SUPABASE_URL and SUPABASE_KEY must be set")
        return []

    supa_city = city_slug.replace("_", "-")
    select = "lat,lng,collection_day"
    base_url = (
        f"{SUPABASE_URL}/rest/v1/schedule_reports"
        f"?city=eq.{quote(supa_city)}"
        f"&select={select}"
        f"&lat=not.is.null&lng=not.is.null"
        f"&collection_day=not.is.null&collection_day=neq."
    )

    all_rows = []
    page_size = 1000
    offset = 0

    while True:
        url = f"{base_url}&limit={page_size}&offset={offset}"
        try:
            resp = requests.get(url, headers=_supa_headers(), timeout=30)
            resp.raise_for_status()
            rows = resp.json()
        except Exception as e:
            log.error(f"Supabase fetch failed at offset {offset}: {e}")
            break

        if not rows:
            break

        for r in rows:
            try:
                lat = float(r["lat"])
                lng = float(r["lng"])
                day = (r.get("collection_day") or "").strip().lower()
                if day and lat and lng:
                    all_rows.append({"lat": lat, "lng": lng, "day": day})
            except (ValueError, TypeError):
                continue

        log.info(f"  Fetched {len(all_rows)} addresses so far (page offset={offset})")
        if len(rows) < page_size:
            break
        offset += page_size

    log.info(f"Total addresses with coords + collection_day: {len(all_rows)}")
    return all_rows


def load_demo_data() -> list[dict]:
    """Load CSV data and assign synthetic collection days for demo mode."""
    csv_path = PROJECT_ROOT / "data" / "addresses_normalized.csv"
    if not csv_path.exists():
        log.error(f"CSV not found: {csv_path}")
        return []

    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                lat = float(row["lat"])
                lon = float(row["lon"])
            except (ValueError, KeyError):
                continue
            # Assign day based on longitude bucketing (mimics real zone patterns)
            bucket = int((lon + 180) * 1000) % 5
            day = DAY_ORDER[bucket]
            rows.append({"lat": lat, "lng": lon, "day": day})

    log.info(f"Loaded {len(rows)} demo addresses from CSV")
    return rows


# ---------------------------------------------------------------------------
# Mercator projection
# ---------------------------------------------------------------------------

def lat_to_mercator_y(lat: float) -> float:
    """Convert latitude to Mercator Y (in radians)."""
    lat_rad = math.radians(lat)
    return math.log(math.tan(math.pi / 4 + lat_rad / 2))


def project_points(
    addresses: list[dict],
    width: int,
    height: int,
    padding: int = 80,
) -> tuple[list[tuple[int, int, str]], dict]:
    """Project lat/lng to pixel coords. Returns (points, bounds)."""
    lats = [a["lat"] for a in addresses]
    lngs = [a["lng"] for a in addresses]

    lat_min, lat_max = min(lats), max(lats)
    lng_min, lng_max = min(lngs), max(lngs)

    # Add small margin to bounds
    lat_margin = (lat_max - lat_min) * 0.02
    lng_margin = (lng_max - lng_min) * 0.02
    lat_min -= lat_margin
    lat_max += lat_margin
    lng_min -= lng_margin
    lng_max += lng_margin

    # Mercator projection
    merc_y_min = lat_to_mercator_y(lat_min)
    merc_y_max = lat_to_mercator_y(lat_max)

    draw_w = width - 2 * padding
    draw_h = height - 2 * padding

    # Compute scale to fit both axes, preserving aspect ratio
    x_scale = draw_w / (lng_max - lng_min)
    y_scale = draw_h / (merc_y_max - merc_y_min)
    scale = min(x_scale, y_scale)

    # Center the map
    x_offset = padding + (draw_w - (lng_max - lng_min) * scale) / 2
    y_offset = padding + (draw_h - (merc_y_max - merc_y_min) * scale) / 2

    points = []
    for a in addresses:
        px = int(x_offset + (a["lng"] - lng_min) * scale)
        # Y is inverted (screen coords)
        merc_y = lat_to_mercator_y(a["lat"])
        py = int(y_offset + (merc_y_max - merc_y) * scale)
        points.append((px, py, a["day"]))

    bounds = {
        "lat_min": lat_min, "lat_max": lat_max,
        "lng_min": lng_min, "lng_max": lng_max,
    }
    return points, bounds


# ---------------------------------------------------------------------------
# Image rendering
# ---------------------------------------------------------------------------

def try_load_font(size: int):
    """Try to load a nice font, fall back to default."""
    font_paths = [
        # Windows
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        # macOS
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFCompact.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for p in font_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def try_load_bold_font(size: int):
    """Try to load a bold font, fall back to regular."""
    font_paths = [
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for p in font_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return try_load_font(size)


def render_map(
    points: list[tuple[int, int, str]],
    width: int,
    height: int,
    city_name: str,
    total_addresses: int,
) -> Image.Image:
    """Render the collection map image."""
    # Dark background
    img = Image.new("RGB", (width, height), (15, 23, 42))
    draw = ImageDraw.Draw(img)

    # Draw all address dots
    # Dot size scales with resolution
    dot_radius = max(1, width // 1920)
    log.info(f"Drawing {len(points)} dots at radius={dot_radius} on {width}x{height}...")

    for px, py, day in points:
        color = DAY_COLORS.get(day, (107, 114, 128))
        if dot_radius <= 1:
            img.putpixel((max(0, min(px, width - 1)), max(0, min(py, height - 1))), color)
        else:
            draw.ellipse(
                [px - dot_radius, py - dot_radius, px + dot_radius, py + dot_radius],
                fill=color,
            )

    # --- Legend box (bottom-left) ---
    legend_w = int(width * 0.14)
    legend_h = int(height * 0.28)
    legend_x = int(width * 0.02)
    legend_y = height - legend_h - int(height * 0.04)

    # Semi-transparent background
    overlay = Image.new("RGBA", (legend_w, legend_h), (15, 23, 42, 220))
    img.paste(
        Image.composite(overlay, Image.new("RGBA", overlay.size, (0, 0, 0, 0)), overlay).convert("RGB"),
        (legend_x, legend_y),
    )
    # Border
    draw.rectangle(
        [legend_x, legend_y, legend_x + legend_w, legend_y + legend_h],
        outline=(51, 65, 85), width=2,
    )

    font_title = try_load_bold_font(max(14, width // 160))
    font_item = try_load_font(max(12, width // 200))
    font_small = try_load_font(max(10, width // 260))

    # Legend title
    ty = legend_y + int(legend_h * 0.06)
    draw.text(
        (legend_x + int(legend_w * 0.08), ty),
        "COLLECTION DAY",
        fill=(148, 163, 184),
        font=font_title,
    )
    ty += int(legend_h * 0.12)

    # Legend items
    swatch_size = max(12, width // 240)
    item_gap = int(legend_h * 0.10)
    for day_name in DAY_ORDER:
        if day_name not in DAY_COLORS:
            continue
        color = DAY_COLORS[day_name]
        sx = legend_x + int(legend_w * 0.08)
        draw.rectangle(
            [sx, ty, sx + swatch_size, ty + swatch_size],
            fill=color,
            outline=(255, 255, 255, 30),
        )
        draw.text(
            (sx + swatch_size + int(legend_w * 0.06), ty - 1),
            day_name.capitalize(),
            fill=(226, 232, 240),
            font=font_item,
        )
        ty += item_gap

    # --- Title bar (top) ---
    bar_h = int(height * 0.06)
    draw.rectangle([0, 0, width, bar_h], fill=(15, 23, 42))
    draw.line([(0, bar_h), (width, bar_h)], fill=(51, 65, 85), width=2)

    font_brand = try_load_bold_font(max(20, width // 100))
    font_subtitle = try_load_font(max(14, width // 150))

    # Brand name
    bx = int(width * 0.02)
    by = int(bar_h * 0.2)
    draw.text((bx, by), "TrashAlert", fill=(56, 189, 248), font=font_brand)

    # Subtitle
    brand_bbox = draw.textbbox((bx, by), "TrashAlert", font=font_brand)
    sub_x = brand_bbox[2] + int(width * 0.015)
    draw.text(
        (sub_x, by + 4),
        f"{city_name} Collection Map",
        fill=(226, 232, 240),
        font=font_subtitle,
    )

    # Address count badge (top-right)
    count_text = f"{total_addresses:,} addresses mapped"
    count_bbox = draw.textbbox((0, 0), count_text, font=font_subtitle)
    count_w = count_bbox[2] - count_bbox[0]
    draw.text(
        (width - count_w - int(width * 0.02), by + 4),
        count_text,
        fill=(148, 163, 184),
        font=font_subtitle,
    )

    # --- Footer ---
    footer_y = height - int(height * 0.025)
    draw.text(
        (int(width * 0.02), footer_y),
        "trashalert.com  |  Every dot = one address with a verified pickup day",
        fill=(100, 116, 139),
        font=font_small,
    )

    return img


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate trash collection map image")
    parser.add_argument("--city", default="san-diego", help="City slug (default: san-diego)")
    parser.add_argument("--demo", action="store_true", help="Use CSV demo data (no Supabase needed)")
    args = parser.parse_args()

    city_slug = args.city
    city_display = city_slug.replace("-", " ").replace("_", " ").title()

    # Fetch data
    if args.demo:
        addresses = load_demo_data()
    else:
        log.info(f"Fetching all addresses for {city_display} from Supabase...")
        addresses = fetch_all_addresses(city_slug)

    if not addresses:
        log.error("No addresses found. Use --demo for test data or set SUPABASE_KEY.")
        sys.exit(1)

    log.info(f"Got {len(addresses)} addresses for {city_display}")

    # Day distribution
    from collections import Counter
    day_counts = Counter(a["day"] for a in addresses)
    for day in DAY_ORDER:
        if day in day_counts:
            log.info(f"  {day.capitalize():12s}: {day_counts[day]:>8,}")

    # Create output dir
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- 4K render ---
    W4K, H4K = 3840, 2160
    log.info(f"Rendering 4K image ({W4K}x{H4K})...")
    points_4k, bounds = project_points(addresses, W4K, H4K, padding=120)
    img_4k = render_map(points_4k, W4K, H4K, city_display, len(addresses))
    out_4k = OUTPUT_DIR / "sd-collection-map-4k.png"
    img_4k.save(str(out_4k), "PNG", optimize=True)
    log.info(f"Saved 4K: {out_4k} ({out_4k.stat().st_size / 1024 / 1024:.1f} MB)")

    # --- 1080p render ---
    W1080, H1080 = 1920, 1080
    log.info(f"Rendering 1080p image ({W1080}x{H1080})...")
    points_1080, _ = project_points(addresses, W1080, H1080, padding=60)
    img_1080 = render_map(points_1080, W1080, H1080, city_display, len(addresses))
    out_1080 = OUTPUT_DIR / "sd-collection-map-1080p.png"
    img_1080.save(str(out_1080), "PNG", optimize=True)
    log.info(f"Saved 1080p: {out_1080} ({out_1080.stat().st_size / 1024 / 1024:.1f} MB)")

    log.info("Done!")


if __name__ == "__main__":
    main()
