#!/usr/bin/env python3
"""
Generate raster brand icons for the Data Trust Platform from the shared
"neural hex" mark. Run from carbon-frontend/:

    python3 scripts/generate-icons.py

Outputs into public/: favicon.ico, favicon-16/32.png, apple-touch-icon.png,
android-chrome-192/512.png, and og-image.png.

The vector sources are public/logo.svg (transparent) and public/favicon.svg
(filled). This script draws the same geometry with PIL so the raster assets
match the SVG without needing a system SVG renderer.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(__file__), "..", "public")

# Brand palette (matches carbonTheme.js + the SVG gradients)
BG_A = (11, 18, 32)      # #0b1220
BG_B = (18, 43, 79)      # #122b4f
STROKE = (47, 111, 224)  # #2f6fe0 (blue-cyan blend)
NODE = (14, 165, 233)    # #0ea5e9
CORE_A = (59, 130, 246)  # #3b82f6
CORE_B = (56, 189, 248)  # #38bdf8
WHITE = (255, 255, 255)


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient_bg(size, radius=0):
    """Diagonal gradient background, optional rounded corners."""
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = (x / w + y / h) / 2.0
            px[x, y] = _lerp(BG_A, BG_B, t) + (255,)
    if radius > 0:
        mask = Image.new("L", (w, h), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
        img.putalpha(mask)
    return img


def draw_mark(size, radius=0):
    """Draw the neural-hex mark on a gradient rounded-square background."""
    img = gradient_bg((size, size), radius=radius)
    d = ImageDraw.Draw(img)
    S = size
    c = S / 2.0
    R = S * 0.34          # vertex radius from center
    ring_w = max(2, int(S * 0.045))
    spoke_w = max(2, int(S * 0.03))
    node_r = S * 0.047
    center_r = S * 0.10

    def vertex(a_deg):
        a = math.radians(a_deg)
        return (c + R * math.cos(a), c + R * math.sin(a))

    angles = [0, 60, 120, 180, 240, 300]
    pts = [vertex(a) for a in angles]

    # Hexagonal ring
    d.line(pts + [pts[0]], fill=STROKE, width=ring_w, joint="curve")

    # Spokes: center -> vertex
    for p in pts:
        d.line([(c, c), p], fill=STROKE, width=spoke_w)

    # Vertex nodes
    for p in pts:
        x, y = p
        d.ellipse([x - node_r, y - node_r, x + node_r, y + node_r], fill=NODE)

    # Central node (gradient-ish: outer ring + white core)
    d.ellipse([c - center_r, c - center_r, c + center_r, c + center_r], fill=CORE_A)
    d.ellipse([c - center_r * 0.5, c - center_r * 0.5, c + center_r * 0.5, c + center_r * 0.5], fill=CORE_B)
    d.ellipse([c - center_r * 0.22, c - center_r * 0.22, c + center_r * 0.22, c + center_r * 0.22], fill=WHITE)

    return img


def _font(size):
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def draw_og_image():
    W, H = 1200, 630
    img = gradient_bg((W, H))
    d = ImageDraw.Draw(img)

    # Mark (large) on the left third
    mark_size = 360
    mark = draw_mark(mark_size, radius=int(mark_size * 0.22))
    img.paste(mark, (90, (H - mark_size) // 2), mark)

    # Wordmark on the right
    title_font = _font(72)
    sub_font = _font(34)
    d.text((90 + mark_size + 60, 210), "Data Trust Platform", fill=WHITE, font=title_font)
    d.text((90 + mark_size + 60, 310), "AASTMT", fill=(165, 210, 255), font=sub_font)
    d.text((90 + mark_size + 60, 360), "Catalog · MDM · Data Quality · Emissions", fill=(148, 163, 184), font=_font(26))

    return img


def main():
    os.makedirs(OUT, exist_ok=True)

    # Favicon PNGs (rounded-square app-icon look)
    for s in (16, 32):
        draw_mark(s, radius=int(s * 0.22)).save(os.path.join(OUT, f"favicon-{s}x{s}.png"))

    # Apple touch (180, full square per Apple convention)
    draw_mark(180, radius=int(180 * 0.22)).save(os.path.join(OUT, "apple-touch-icon.png"))

    # Android chrome
    for s in (192, 512):
        draw_mark(s, radius=int(s * 0.22)).save(os.path.join(OUT, f"android-chrome-{s}x{s}.png"))

    # favicon.ico (multi-size)
    ico = draw_mark(48, radius=int(48 * 0.22))
    ico.save(os.path.join(OUT, "favicon.ico"), format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])

    # OG / social share card
    draw_og_image().save(os.path.join(OUT, "og-image.png"))

    print("Generated:")
    for f in sorted(os.listdir(OUT)):
        if f.endswith((".png", ".ico")):
            print("  public/" + f)


if __name__ == "__main__":
    main()
