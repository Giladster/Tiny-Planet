# paint over the NASA logo and Apollo 11 mission patch with our own Tiny Planet patches
import sys, math, random
from PIL import Image, ImageDraw
src, out = sys.argv[1], sys.argv[2]
im = Image.open(src).convert("RGBA")
def patch(kind, r):
    S = 8; R = r * S; c = Image.new("RGBA", (2 * R + 8, 2 * R + 8), (0, 0, 0, 0)); d = ImageDraw.Draw(c); o = R + 4
    d.ellipse((o - R, o - R, o + R, o + R), fill=(232, 232, 236, 255)); d.ellipse((o - R + S * 2, o - R + S * 2, o + R - S * 2, o + R - S * 2), fill=(22, 34, 82, 255))
    random.seed(kind)
    for _ in range(16):
        x = random.uniform(-.75, .75) * R; y = random.uniform(-.75, .75) * R
        if x * x + y * y < (R * .8) ** 2: d.ellipse((o + x - S * .6, o + y - S * .6, o + x + S * .6, o + y + S * .6), fill=(255, 255, 255, 255))
    if kind == "planet":
        pr = R * .42; ring = (o - R * .78, o - R * .2, o + R * .78, o + R * .2)
        d.ellipse(ring, outline=(255, 214, 120, 255), width=int(S * 1.6))
        d.ellipse((o - pr, o - pr, o + pr, o + pr), fill=(255, 128, 48, 255))
        d.ellipse((o - pr * .6, o + pr * .1, o + pr * .2, o + pr * .75), fill=(255, 180, 100, 255))
        d.arc(ring, 180, 360, fill=(255, 214, 120, 255), width=int(S * 1.6))  # front half of the ring (the texture is upside down on the suit)
    else:
        pts = [(o + math.cos(math.radians(90 + i * 36)) * (R * .55 if i % 2 == 0 else R * .23), o + math.sin(math.radians(90 + i * 36)) * (R * .55 if i % 2 == 0 else R * .23)) for i in range(10)]
        d.polygon(pts, fill=(255, 200, 60, 255)); d.ellipse((o - R * .12, o - R * .12, o + R * .12, o + R * .12), fill=(90, 220, 255, 255))
    return c.resize((c.width // S, c.height // S), Image.LANCZOS)
for kind, (cx, cy), r in (("planet", (377, 656), 29), ("star", (531, 653), 26)):
    p = patch(kind, r); im.alpha_composite(p, (cx - p.width // 2, cy - p.height // 2))
im.convert("RGB").save(out)
