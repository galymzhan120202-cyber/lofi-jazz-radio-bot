"""Velvet Jazz Lounge — procedural branding generator (profile picture + banner).
Deep velvet purple/burgundy palette with warm gold accents — elegant, eye-catching,
soft on the eyes (no harsh neon, gentle gradients and glow only).
"""
import math
import random
import sys
import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

random.seed(42)

FONT_SERIF_BOLD = "C:/Windows/Fonts/georgiab.ttf"
FONT_SERIF = "C:/Windows/Fonts/georgia.ttf"
FONT_SERIF_ITALIC = "C:/Windows/Fonts/georgiai.ttf"

# --- Palette: velvet + warm gold ---
VELVET_TOP = (36, 14, 34)      # deep plum
VELVET_MID = (26, 10, 26)      # velvet burgundy-black
VELVET_BOTTOM = (14, 6, 16)    # near-black plum
GOLD = (216, 175, 122)         # warm champagne gold
GOLD_LIGHT = (238, 210, 165)
GOLD_DIM = (140, 105, 70)
CREAM = (240, 230, 214)


def vertical_gradient(size, top, bottom, mid=None):
    w, h = size
    img = Image.new("RGB", size, top)
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        if mid is not None and t < 0.5:
            tt = t / 0.5
            r = int(top[0] + (mid[0] - top[0]) * tt)
            g = int(top[1] + (mid[1] - top[1]) * tt)
            b = int(top[2] + (mid[2] - top[2]) * tt)
        elif mid is not None:
            tt = (t - 0.5) / 0.5
            r = int(mid[0] + (bottom[0] - mid[0]) * tt)
            g = int(mid[1] + (bottom[1] - mid[1]) * tt)
            b = int(mid[2] + (bottom[2] - mid[2]) * tt)
        else:
            r = int(top[0] + (bottom[0] - top[0]) * t)
            g = int(top[1] + (bottom[1] - top[1]) * t)
            b = int(top[2] + (bottom[2] - top[2]) * t)
        for x in range(0, w, 3):
            px[x, y] = (r, g, b)
            if x + 1 < w:
                px[x + 1, y] = (r, g, b)
            if x + 2 < w:
                px[x + 2, y] = (r, g, b)
    return img


def radial_glow(size, center, radius, color, max_alpha=140):
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    steps = 60
    for i in range(steps, 0, -1):
        t = i / steps
        r = int(radius * t)
        alpha = int(max_alpha * (1 - t) ** 2)
        gd.ellipse(
            [center[0] - r, center[1] - r, center[0] + r, center[1] + r],
            fill=(color[0], color[1], color[2], alpha),
        )
    return glow


def draw_treble_clef_monogram(draw, cx, cy, size, color):
    """Elegant stylized 'V' monogram with a jazz note flourish, drawn with strokes."""
    w = size * 0.62
    h = size * 0.62
    stroke = max(6, int(size * 0.045))
    # V shape
    left_top = (cx - w / 2, cy - h / 2)
    right_top = (cx + w / 2, cy - h / 2)
    bottom = (cx, cy + h / 2)
    draw.line([left_top, bottom], fill=color, width=stroke, joint="curve")
    draw.line([bottom, right_top], fill=color, width=stroke, joint="curve")
    # musical note accent to the right of the V
    note_cx = cx + w * 0.62
    note_cy = cy + h * 0.18
    note_r = size * 0.09
    draw.ellipse(
        [note_cx - note_r, note_cy - note_r, note_cx + note_r, note_cy + note_r],
        fill=color,
    )
    stem_x = note_cx + note_r * 0.85
    draw.line(
        [(stem_x, note_cy), (stem_x, note_cy - size * 0.34)],
        fill=color, width=max(4, int(stroke * 0.7))
    )
    # small flag
    draw.line(
        [(stem_x, note_cy - size * 0.34), (stem_x + size * 0.11, note_cy - size * 0.26)],
        fill=color, width=max(4, int(stroke * 0.7))
    )


def make_profile_picture(path, size=800):
    img = vertical_gradient((size, size), VELVET_TOP, VELVET_BOTTOM, VELVET_MID).convert("RGBA")

    glow = radial_glow((size, size), (size // 2, int(size * 0.46)), int(size * 0.55), GOLD, max_alpha=95)
    glow = glow.filter(ImageFilter.GaussianBlur(size * 0.05))
    img = Image.alpha_composite(img, glow)

    # soft vignette for depth
    vignette = Image.new("L", (size, size), 0)
    vd = ImageDraw.Draw(vignette)
    vd.ellipse([-size * 0.15, -size * 0.15, size * 1.15, size * 1.15], fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(size * 0.12))
    dark_layer = Image.new("RGBA", (size, size), (0, 0, 0, 90))
    inv = Image.eval(vignette, lambda p: 255 - p)
    dark_layer.putalpha(inv)
    img = Image.alpha_composite(img, dark_layer)

    draw = ImageDraw.Draw(img)
    draw_treble_clef_monogram(draw, size / 2, size * 0.47, size * 0.62, GOLD_LIGHT)

    # thin ring accent
    ring_r = size * 0.44
    draw.ellipse(
        [size / 2 - ring_r, size / 2 - ring_r, size / 2 + ring_r, size / 2 + ring_r],
        outline=(*GOLD_DIM, 160), width=max(2, int(size * 0.006))
    )

    img.convert("RGB").save(path, quality=95)
    print(f"✓ Profile picture: {path}")


def draw_piano_keys(draw, x0, y0, width, height, color, alpha_img_size, key_count=28):
    key_w = width / key_count
    for i in range(key_count):
        x = x0 + i * key_w
        draw.rectangle([x, y0, x + key_w * 0.86, y0 + height], outline=(*color, 60), width=1)


def make_banner(path, size=(2560, 1440)):
    w, h = size
    img = vertical_gradient(size, VELVET_TOP, VELVET_BOTTOM, VELVET_MID).convert("RGBA")

    glow1 = radial_glow(size, (int(w * 0.5), int(h * 0.42)), int(h * 0.85), GOLD, max_alpha=70)
    glow1 = glow1.filter(ImageFilter.GaussianBlur(h * 0.06))
    img = Image.alpha_composite(img, glow1)

    glow2 = radial_glow(size, (int(w * 0.12), int(h * 0.15)), int(h * 0.5), GOLD, max_alpha=35)
    img = Image.alpha_composite(img, glow2)
    glow3 = radial_glow(size, (int(w * 0.88), int(h * 0.85)), int(h * 0.5), GOLD, max_alpha=35)
    img = Image.alpha_composite(img, glow3)

    draw = ImageDraw.Draw(img)

    # subtle piano key strip along the very bottom (fades into background)
    key_strip_h = int(h * 0.05)
    draw_piano_keys(draw, 0, h - key_strip_h, w, key_strip_h, GOLD_DIM, size)

    cy = int(h * 0.46)

    # Wordmark
    title_font = ImageFont.truetype(FONT_SERIF_BOLD, int(h * 0.135))
    subtitle_font = ImageFont.truetype(FONT_SERIF_ITALIC, int(h * 0.045))

    title = "VELVET JAZZ LOUNGE"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx, ty = w / 2 - tw / 2, cy - th / 2 - bbox[1]

    # soft gold text glow (draw blurred copy behind)
    glow_layer = Image.new("RGBA", size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow_layer)
    gdraw.text((tx, ty), title, font=title_font, fill=(*GOLD, 255))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(14))
    img = Image.alpha_composite(img, glow_layer)
    draw = ImageDraw.Draw(img)
    draw.text((tx, ty), title, font=title_font, fill=(*GOLD_LIGHT, 255))

    # thin rule well above and below the wordmark only (clear of text, no subtitle clutter)
    rule_w = int(w * 0.22)
    rule_top_y = ty - int(h * 0.07)
    rule_bottom_y = ty + th + int(h * 0.07)
    draw.line([(w / 2 - rule_w / 2, rule_top_y), (w / 2 + rule_w / 2, rule_top_y)],
              fill=(*GOLD_DIM, 180), width=2)
    draw.line([(w / 2 - rule_w / 2, rule_bottom_y), (w / 2 + rule_w / 2, rule_bottom_y)],
              fill=(*GOLD_DIM, 180), width=2)

    img.convert("RGB").save(path, quality=95)
    print(f"✓ Banner: {path}")


if __name__ == "__main__":
    make_profile_picture("branding_profile.png")
    make_banner("branding_banner.png")
