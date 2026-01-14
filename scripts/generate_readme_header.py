#!/usr/bin/env python3
"""Generate README header image for toyoura-nagisa project."""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import os

# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
ASSETS_DIR = PROJECT_ROOT / "docs" / "assets"
AVATAR_PATH = ASSETS_DIR / "Nagisa_avatar.png"
OUTPUT_PATH = ASSETS_DIR / "readme_header.png"

# Image dimensions
WIDTH = 720
HEIGHT = 200

# Colors (RGB)
GRADIENT_START = (255, 230, 240)  # Light pink
GRADIENT_END = (252, 215, 228)    # Slightly darker pink
TITLE_COLOR = (200, 50, 120)      # Magenta/pink for title
TAGLINE_COLOR = (200, 50, 120)    # Same pink for tagline
SUBTITLE_COLOR = (80, 80, 80)     # Dark gray
FEATURES_COLOR = (150, 130, 140)  # Muted pink-gray
URL_COLOR = (180, 150, 165)       # Light muted pink


def create_gradient_background(width: int, height: int) -> Image.Image:
    """Create a horizontal gradient background."""
    img = Image.new("RGB", (width, height))

    for x in range(width):
        ratio = x / width
        r = int(GRADIENT_START[0] + (GRADIENT_END[0] - GRADIENT_START[0]) * ratio)
        g = int(GRADIENT_START[1] + (GRADIENT_END[1] - GRADIENT_START[1]) * ratio)
        b = int(GRADIENT_START[2] + (GRADIENT_END[2] - GRADIENT_START[2]) * ratio)

        for y in range(height):
            img.putpixel((x, y), (r, g, b))

    return img


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Get a font, falling back to default if needed."""
    # Try common font paths
    font_paths = [
        # macOS
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSDisplay.ttf",
        "/Library/Fonts/Arial.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # Windows
        "C:/Windows/Fonts/arial.ttf",
    ]

    if bold:
        bold_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
        font_paths = bold_paths + font_paths

    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    # Fallback to default
    return ImageFont.load_default()


def generate_header():
    """Generate the README header image."""
    # Create gradient background
    img = create_gradient_background(WIDTH, HEIGHT)
    draw = ImageDraw.Draw(img)

    # Load and resize avatar (maintain aspect ratio)
    avatar_width = 0
    if AVATAR_PATH.exists():
        avatar = Image.open(AVATAR_PATH)
        orig_w, orig_h = avatar.size

        # Scale to fit height with padding, maintain aspect ratio
        target_height = HEIGHT - 20  # 10px padding top and bottom
        scale = target_height / orig_h
        avatar_width = int(orig_w * scale)
        avatar_height = target_height

        avatar = avatar.resize((avatar_width, avatar_height), Image.Resampling.NEAREST)

        # Paste avatar (handle transparency)
        if avatar.mode == "RGBA":
            img.paste(avatar, (10, 10), avatar)
        else:
            img.paste(avatar, (10, 10))

    # Text positioning (right of avatar)
    text_x = avatar_width + 30 if avatar_width else 20

    # Fonts
    title_font = get_font(42, bold=True)
    tagline_font = get_font(20, bold=True)
    subtitle_font = get_font(22)
    features_font = get_font(14)
    url_font = get_font(13)

    # Draw text elements
    y_offset = 20

    # Title: toyoura-nagisa
    draw.text((text_x, y_offset), "toyoura-nagisa", font=title_font, fill=TITLE_COLOR)
    y_offset += 50

    # Tagline: >> Script is Context
    draw.text((text_x, y_offset), ">> Script is Context", font=tagline_font, fill=TAGLINE_COLOR)
    y_offset += 28

    # Subtitle: LLM-Driven PFC Simulation Assistant
    draw.text((text_x, y_offset), "LLM-Driven PFC Simulation Assistant", font=subtitle_font, fill=SUBTITLE_COLOR)
    y_offset += 32

    # Features
    features = "Doc Query  |  Lifecycle Control  |  SubAgent  |  Multimodal Diagnostics  |  Skills"
    draw.text((text_x, y_offset), features, font=features_font, fill=FEATURES_COLOR)
    y_offset += 28

    # URL: github.com/yusong652/toyoura-nagisa
    draw.text((text_x, y_offset), "github.com/yusong652/toyoura-nagisa", font=url_font, fill=URL_COLOR)

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUTPUT_PATH, "PNG")
    print(f"Header saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    generate_header()
