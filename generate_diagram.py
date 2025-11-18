#!/usr/bin/env python3
"""
Generate TrashAlert Architecture Diagram
Requires: pip install pillow
Alternative: Use this script as reference to create diagram in draw.io or similar tool
"""

try:
    from PIL import Image, ImageDraw, ImageFont
    import os

    # Create a large canvas
    width = 2400
    height = 3200
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)

    # Define colors
    COLOR_CLIENT = '#E3F2FD'  # Light blue
    COLOR_INFRA = '#FFF3E0'   # Light orange
    COLOR_APP = '#E8F5E9'     # Light green
    COLOR_DATA = '#F3E5F5'    # Light purple
    COLOR_EXTERNAL = '#FFF9C4' # Light yellow
    COLOR_BORDER = '#37474F'  # Dark gray
    COLOR_TEXT = '#212121'    # Almost black
    COLOR_ARROW = '#1976D2'   # Blue

    # Try to use a nice font, fall back to default if not available
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        heading_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        title_font = ImageFont.load_default()
        heading_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    def draw_box(x, y, w, h, fill_color, label, sublabels=None):
        """Draw a rounded rectangle box with label"""
        # Draw rounded rectangle
        draw.rounded_rectangle([x, y, x+w, y+h], radius=10, fill=fill_color, outline=COLOR_BORDER, width=3)

        # Draw label
        bbox = draw.textbbox((0, 0), label, font=heading_font)
        text_width = bbox[2] - bbox[0]
        draw.text((x + (w - text_width) // 2, y + 15), label, fill=COLOR_TEXT, font=heading_font)

        # Draw sublabels if provided
        if sublabels:
            y_offset = y + 60
            for sublabel in sublabels:
                draw.text((x + 20, y_offset), "• " + sublabel, fill=COLOR_TEXT, font=small_font)
                y_offset += 25

    def draw_arrow(x1, y1, x2, y2):
        """Draw an arrow from (x1,y1) to (x2,y2)"""
        # Draw line
        draw.line([(x1, y1), (x2, y2)], fill=COLOR_ARROW, width=3)

        # Draw arrowhead
        arrow_size = 15
        draw.polygon([
            (x2, y2),
            (x2 - arrow_size, y2 - arrow_size),
            (x2 + arrow_size, y2 - arrow_size)
        ], fill=COLOR_ARROW)

    # Title
    title = "TrashAlert System Architecture"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    title_width = bbox[2] - bbox[0]
    draw.text((width // 2 - title_width // 2, 30), title, fill=COLOR_TEXT, font=title_font)

    y_pos = 120

    # CLIENT LAYER
    draw.rounded_rectangle([50, y_pos, width-50, y_pos+200], radius=15, fill=COLOR_CLIENT, outline=COLOR_BORDER, width=4)
    draw.text((100, y_pos+15), "CLIENT LAYER", fill=COLOR_TEXT, font=heading_font)

    # Client boxes
    box_width = 250
    box_spacing = 50
    x_start = 150
    clients = ["Web App\n(React)", "iOS App\n(Swift)", "Android App\n(Kotlin)", "Third-Party\nIntegrations"]
    for i, client in enumerate(clients):
        x = x_start + i * (box_width + box_spacing)
        draw.rounded_rectangle([x, y_pos+70, x+box_width, y_pos+160], radius=8, fill='white', outline=COLOR_BORDER, width=2)

        # Center text
        lines = client.split('\n')
        text_y = y_pos + 90
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=text_font)
            text_width = bbox[2] - bbox[0]
            draw.text((x + (box_width - text_width) // 2, text_y), line, fill=COLOR_TEXT, font=text_font)
            text_y += 25

    # Arrow from client to infra
    draw_arrow(width // 2, y_pos + 200, width // 2, y_pos + 250)
    draw.text((width // 2 + 20, y_pos + 210), "HTTPS/REST", fill=COLOR_TEXT, font=small_font)

    y_pos += 280

    # INFRASTRUCTURE LAYER
    draw.rounded_rectangle([50, y_pos, width-50, y_pos+250], radius=15, fill=COLOR_INFRA, outline=COLOR_BORDER, width=4)
    draw.text((100, y_pos+15), "INFRASTRUCTURE LAYER", fill=COLOR_TEXT, font=heading_font)

    # Nginx box
    nginx_items = [
        "SSL Termination (Let's Encrypt)",
        "Rate Limiting (30/min lookup, 10/min report)",
        "HTTP Caching (5 min TTL)",
        "Load Balancing",
        "DDoS Protection"
    ]
    draw_box(150, y_pos+60, width-300, 170, 'white', "NGINX Reverse Proxy", nginx_items)

    # Arrow from infra to app
    draw_arrow(width // 2, y_pos + 250, width // 2, y_pos + 300)

    y_pos += 330

    # APPLICATION LAYER
    draw.rounded_rectangle([50, y_pos, width-50, y_pos+500], radius=15, fill=COLOR_APP, outline=COLOR_BORDER, width=4)
    draw.text((100, y_pos+15), "APPLICATION LAYER (FastAPI)", fill=COLOR_TEXT, font=heading_font)

    # API Endpoints box
    api_endpoints = [
        "GET /lookup - Schedule lookup",
        "POST /report - Submit observation",
        "GET /stats - System statistics",
        "GET /health - Health check"
    ]
    draw_box(150, y_pos+60, width-300, 140, 'white', "API Endpoints", api_endpoints)

    # Business Logic boxes (3 columns)
    logic_y = y_pos + 220
    logic_width = 450
    logic_spacing = 50

    logic_boxes = [
        ("Address\nNormalization", ["Parse input", "Standardize", "Geocode", "Validate"]),
        ("Lookup Engine", ["Multi-source priority", "Data ranking", "Cache lookup", "Exceptions"]),
        ("Crowdsourcing\nEngine", ["Consensus algorithm", "Verification", "Spam filter", "Aggregation"])
    ]

    x_start = 150
    for i, (title, items) in enumerate(logic_boxes):
        x = x_start + i * (logic_width + logic_spacing)
        draw_box(x, logic_y, logic_width, 180, 'white', title, items)

    # Security boxes (3 columns)
    security_y = logic_y + 220
    security_boxes = [
        ("Rate Limiter", ["Sliding window", "IP tracking", "Abuse detection"]),
        ("Validation", ["Input sanitize", "Schema validate", "Business rules"]),
        ("Authentication", ["API keys", "JWT tokens", "OAuth 2.0"])
    ]

    for i, (title, items) in enumerate(security_boxes):
        x = x_start + i * (logic_width + logic_spacing)
        draw_box(x, security_y, logic_width, 140, 'white', title, items)

    # Arrow from app to data
    draw_arrow(width // 2, y_pos + 500, width // 2, y_pos + 550)

    y_pos += 580

    # DATA LAYER
    draw.rounded_rectangle([50, y_pos, width-50, y_pos+450], radius=15, fill=COLOR_DATA, outline=COLOR_BORDER, width=4)
    draw.text((100, y_pos+15), "DATA LAYER", fill=COLOR_TEXT, font=heading_font)

    # PostgreSQL box
    draw.rounded_rectangle([150, y_pos+60, width-300, y_pos+400], radius=10, fill='white', outline=COLOR_BORDER, width=2)
    draw.text((180, y_pos+75), "PostgreSQL Database (SQLite for dev)", fill=COLOR_TEXT, font=heading_font)

    # Database tables (3 columns, 3 rows)
    table_width = 350
    table_height = 90
    table_spacing = 40
    tables_x = 200
    tables_y = y_pos + 130

    tables = [
        ["addresses", "Normalized addresses,\nGPS coordinates,\nCity/state, OSM data"],
        ["crowd_reports", "Individual user reports,\nTimestamps,\nIP tracking"],
        ["schedules", "Official schedules,\nZone-based,\nProvider info"],
        ["crowd_consensus", "Aggregated reports,\nAgreement ratios,\nVerified status"],
        ["schedule_exceptions", "Holidays,\nRoute changes,\nWeather delays"],
        ["source_metadata", "Data sources,\nParser versions,\nUpdate logs"],
        ["request_metrics", "API usage,\nPerformance,\nError tracking"],
        ["pickup_zones", "Geographic boundaries,\nZone-level schedules"]
    ]

    for i, (table_name, description) in enumerate(tables):
        row = i // 3
        col = i % 3
        x = tables_x + col * (table_width + table_spacing)
        y = tables_y + row * (table_height + table_spacing)

        # Only draw if within bounds
        if y + table_height < y_pos + 400:
            draw.rounded_rectangle([x, y, x+table_width, y+table_height], radius=5, fill='#ECEFF1', outline=COLOR_BORDER, width=1)
            draw.text((x+10, y+8), table_name, fill=COLOR_TEXT, font=text_font)

            # Draw description
            desc_y = y + 35
            for line in description.split('\n'):
                draw.text((x+10, desc_y), line, fill=COLOR_TEXT, font=small_font)
                desc_y += 18

    y_pos += 480

    # EXTERNAL SOURCES
    draw.rounded_rectangle([50, y_pos, width-50, y_pos+200], radius=15, fill=COLOR_EXTERNAL, outline=COLOR_BORDER, width=4)
    draw.text((100, y_pos+15), "EXTERNAL DATA SOURCES", fill=COLOR_TEXT, font=heading_font)

    external_width = 450
    external_spacing = 100
    external_boxes = [
        ("OpenStreetMap", ["Overpass API", "Address data", "Coordinates", "Boundaries"]),
        ("Municipal Websites", ["Web scraping", "PDF parsing", "Schedule extraction"]),
        ("Waste Hauler APIs", ["CR&R", "Waste Management", "Republic Services"])
    ]

    x_start = 200
    for i, (title, items) in enumerate(external_boxes):
        x = x_start + i * (external_width + external_spacing)
        draw_box(x, y_pos+60, external_width, 120, 'white', title, items)

    # Add footer
    footer_y = y_pos + 220
    draw.text((100, footer_y), "Performance: <5ms cached | <100ms uncached | 99.9% uptime target", fill=COLOR_TEXT, font=text_font)
    draw.text((100, footer_y + 30), "Tech Stack: FastAPI + PostgreSQL + Docker + Nginx + Let's Encrypt", fill=COLOR_TEXT, font=text_font)
    draw.text((100, footer_y + 60), "Data Priority: VERIFIED CROWD > OFFICIAL > UNVERIFIED > UNKNOWN", fill=COLOR_TEXT, font=text_font)

    # Save the image
    output_path = '/home/user/TrashAlert/ARCHITECTURE_DIAGRAM.png'
    img.save(output_path, 'PNG', quality=95)
    print(f"✓ Diagram saved to {output_path}")
    print(f"  Dimensions: {width}x{height} pixels")

except ImportError as e:
    print("PIL/Pillow not installed. To generate the diagram:")
    print("1. Install: pip install pillow")
    print("2. Run: python3 generate_diagram.py")
    print("")
    print("Alternative: Use the text diagram in ARCHITECTURE_DIAGRAM.txt")
    print("and convert it using:")
    print("- https://asciiflow.com")
    print("- https://app.diagrams.net (draw.io)")
    print("- Screenshot in terminal with monospace font")
    exit(1)
