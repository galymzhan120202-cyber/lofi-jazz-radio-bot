"""Velvet Jazz Lounge — eye-catching thumbnail generator (1280x720).
Procedural scene variants (rain window, vinyl, piano, city night, candle cafe)
in the velvet+gold palette, with a bold hook line and duration badge —
built to compete visually with high-CTR channels in this niche.
"""
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_BLACK = "C:/Windows/Fonts/impact.ttf"
FONT_SERIF_BOLD = "C:/Windows/Fonts/georgiab.ttf"

VELVET_TOP = (36, 14, 34)
VELVET_MID = (26, 10, 26)
VELVET_BOTTOM = (12, 5, 14)
GOLD = (216, 175, 122)
GOLD_LIGHT = (245, 218, 170)
GOLD_DIM = (140, 105, 70)
CREAM = (240, 230, 214)
WARM_WHITE = (255, 244, 224)

W, H = 1280, 720


def vertical_gradient(size, top, bottom, mid=None):
    w, h = size
    img = Image.new("RGB", size, top)
    px = img.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        if mid is not None and t < 0.5:
            tt = t / 0.5
            c = tuple(int(top[i] + (mid[i] - top[i]) * tt) for i in range(3))
        elif mid is not None:
            tt = (t - 0.5) / 0.5
            c = tuple(int(mid[i] + (bottom[i] - mid[i]) * tt) for i in range(3))
        else:
            c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(0, w, 3):
            px[x, y] = c
            if x + 1 < w:
                px[x + 1, y] = c
            if x + 2 < w:
                px[x + 2, y] = c
    return img


def radial_glow(size, center, radius, color, max_alpha=140):
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    steps = 50
    for i in range(steps, 0, -1):
        t = i / steps
        r = int(radius * t)
        alpha = int(max_alpha * (1 - t) ** 2)
        gd.ellipse([center[0] - r, center[1] - r, center[0] + r, center[1] + r],
                   fill=(*color, alpha))
    return glow


def scene_rain_window(img):
    draw = ImageDraw.Draw(img, "RGBA")
    random.seed()
    for _ in range(90):
        x = random.uniform(0, W)
        y0 = random.uniform(-50, H)
        length = random.uniform(30, 90)
        alpha = random.randint(25, 70)
        draw.line([(x, y0), (x - 8, y0 + length)], fill=(*GOLD_LIGHT, alpha), width=1)
    glow = radial_glow((W, H), (int(W * 0.5), int(H * 0.35)), int(H * 0.7), GOLD, 90)
    return Image.alpha_composite(img.convert("RGBA"), glow)


def scene_vinyl(img):
    img = img.convert("RGBA")
    cx, cy, r = int(W * 0.78), int(H * 0.5), int(H * 0.62)
    disc = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(disc)
    dd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(15, 8, 14, 255))
    for i in range(6, r, 14):
        dd.ellipse([cx - i, cy - i, cx + i, cy + i], outline=(*GOLD_DIM, 90), width=1)
    label_r = int(r * 0.32)
    dd.ellipse([cx - label_r, cy - label_r, cx + label_r, cy + label_r], fill=(*GOLD, 255))
    hole_r = int(r * 0.04)
    dd.ellipse([cx - hole_r, cy - hole_r, cx + hole_r, cy + hole_r], fill=VELVET_BOTTOM)
    glow = radial_glow((W, H), (cx, cy), r + 80, GOLD, 70)
    img = Image.alpha_composite(img, glow)
    return Image.alpha_composite(img, disc)


def scene_piano(img):
    img = img.convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")
    key_h = int(H * 0.30)
    y0 = H - key_h
    n = 17
    key_w = W / n
    for i in range(n):
        x = i * key_w
        draw.rectangle([x, y0, x + key_w * 0.94, H], fill=(20, 10, 20, 235),
                        outline=(*GOLD_DIM, 120), width=1)
        if i % 7 not in (2, 6):
            bx = x + key_w * 0.62
            draw.rectangle([bx, y0, bx + key_w * 0.5, y0 + key_h * 0.62], fill=(8, 4, 8, 255))
    glow = radial_glow((W, H), (int(W * 0.5), int(H * 0.28)), int(H * 0.75), GOLD, 85)
    return Image.alpha_composite(img, glow)


def scene_city_night(img):
    img = img.convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")
    random.seed()
    x = 0
    while x < W:
        bw = random.uniform(60, 140)
        bh = random.uniform(H * 0.25, H * 0.6)
        draw.rectangle([x, H - bh, x + bw, H], fill=(18, 9, 18, 255))
        wx = x + 8
        while wx < x + bw - 10:
            wy = H - bh + 10
            while wy < H - 14:
                if random.random() < 0.35:
                    draw.rectangle([wx, wy, wx + 8, wy + 10], fill=(*GOLD_LIGHT, 220))
                wy += 20
            wx += 16
        x += bw + 6
    glow = radial_glow((W, H), (int(W * 0.5), int(H * 0.3)), int(H * 0.8), GOLD, 75)
    return Image.alpha_composite(img, glow)


SCENES = [scene_rain_window, scene_vinyl, scene_piano, scene_city_night]


def draw_text_with_glow(img, text, font, xy, fill, glow_color=GOLD, blur=10):
    glow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    gd.text(xy, text, font=font, fill=(*glow_color, 255))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(blur))
    img = Image.alpha_composite(img.convert("RGBA"), glow_layer)
    draw = ImageDraw.Draw(img)
    draw.text(xy, text, font=font, fill=fill,
               stroke_width=3, stroke_fill=(10, 5, 10, 255))
    return img


def make_thumbnail(hook_text, duration_minutes, out_path, scene_fn=None):
    """hook_text: short punchy line (<=4 words ideally). duration_minutes: int."""
    img = vertical_gradient((W, H), VELVET_TOP, VELVET_BOTTOM, VELVET_MID)
    scene_fn = scene_fn or random.choice(SCENES)
    img = scene_fn(img)

    # left-side dark scrim so text stays readable regardless of scene
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    for x in range(0, int(W * 0.62), 2):
        t = x / (W * 0.62)
        alpha = int(190 * (1 - t))
        sd.line([(x, 0), (x, H)], fill=(8, 4, 10, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), scrim)

    # hook text, big bold, upper-left safe zone
    font_size = 108 if len(hook_text) <= 14 else 84
    font = ImageFont.truetype(FONT_BLACK, font_size)
    words = hook_text.upper().split()
    lines = []
    cur = ""
    draw_probe = ImageDraw.Draw(img)
    max_w = int(W * 0.56)
    for w in words:
        trial = (cur + " " + w).strip()
        bbox = draw_probe.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    lines = lines[:3]

    ty = int(H * 0.16)
    for line in lines:
        img = draw_text_with_glow(img, line, font, (60, ty), WARM_WHITE, GOLD, blur=8)
        bbox = ImageDraw.Draw(img).textbbox((0, 0), line, font=font)
        ty += (bbox[3] - bbox[1]) + 14

    # duration badge, top-right, rounded pill
    draw = ImageDraw.Draw(img)
    if duration_minutes < 90:
        badge_text = f"{duration_minutes} MIN"
    else:
        h_val = round(duration_minutes / 60, 1)
        if h_val == int(h_val):
            h_val = int(h_val)
        badge_text = f"{h_val}H JAZZ"
    badge_font = ImageFont.truetype(FONT_SERIF_BOLD, 40)
    bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 26, 16
    bx1 = W - bw - pad_x * 2 - 36
    by1 = 36
    bx2, by2 = bx1 + bw + pad_x * 2, by1 + bh + pad_y * 2
    draw.rounded_rectangle([bx1, by1, bx2, by2], radius=(by2 - by1) // 2,
                            fill=(*GOLD, 235))
    draw.text((bx1 + pad_x, by1 + pad_y - bbox[1]), badge_text, font=badge_font,
               fill=VELVET_BOTTOM)

    # small brand wordmark bottom-left
    brand_font = ImageFont.truetype(FONT_SERIF_BOLD, 30)
    img = draw_text_with_glow(img, "VELVET JAZZ LOUNGE", brand_font,
                                (60, H - 64), GOLD_LIGHT, GOLD, blur=4)

    img.convert("RGB").save(out_path, quality=92)
    return out_path


HOOK_LINES = [
    "Cozy Jazz Night", "Rainy Jazz Cafe", "Midnight Jazz Bar", "Warm Jazz Piano",
    "Smooth Jazz Vibes", "Late Night Lounge", "Jazz for Sleep", "Deep Focus Jazz",
    "Sunday Jazz Cafe", "Velvet Jazz Night",
]

if __name__ == "__main__":
    make_thumbnail(random.choice(HOOK_LINES), 95, "thumbnail_preview.png")
    print("done")
