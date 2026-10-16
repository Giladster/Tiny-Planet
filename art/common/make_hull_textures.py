# Tiny Planet: tiling hull detail textures for every Blender ship.
# Run: python3 make_hull_textures.py <out_dir>   (needs numpy + Pillow)
# Makes three 1024px seamless maps:
#   hull_color.png  near-white grime/dirt multiplier (ship colors stay bright when tinted)
#   hull_rough.png  glTF metal/rough map: G = roughness variation, B = 1 (metal comes from the material)
#   hull_normal.png panel lines, rivets, vents and small dents
import sys, os
import numpy as np
from PIL import Image

OUT = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
os.makedirs(OUT, exist_ok=True)
N = 1024
rng = np.random.default_rng(7)


def blur(a, s):  # seamless gaussian blur (wraps around the edges)
    f = np.fft.fftfreq(N)
    g = np.exp(-(f[:, None] ** 2 + f[None, :] ** 2) * (2 * np.pi * s) ** 2 / 2)
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g))


def noise(scale, octaves=4):  # seamless fractal noise in 0..1
    out = np.zeros((N, N)); amp = 1; tot = 0
    for o in range(octaves):
        s = scale / 2 ** o
        out += amp * blur(rng.standard_normal((N, N)), s); tot += amp; amp *= .5
    out -= out.min(); return out / out.max()


# ---- panels: split the square into rectangles, like hull plates
height = np.ones((N, N)) * .5
groove = np.zeros((N, N))
panels = []
def split(x0, y0, x1, y1, d):
    w, h = x1 - x0, y1 - y0
    if d > 7 or (d > 3 and rng.random() < .25) or min(w, h) < 60:
        panels.append((x0, y0, x1, y1)); return
    if w > h * rng.uniform(.7, 1.4):
        c = int(x0 + w * rng.uniform(.3, .7)); split(x0, y0, c, y1, d + 1); split(c, y0, x1, y1, d + 1)
    else:
        c = int(y0 + h * rng.uniform(.3, .7)); split(x0, y0, x1, c, d + 1); split(x0, c, x1, y1, d + 1)
split(0, 0, N, N, 0)
yy, xx = np.mgrid[0:N, 0:N]
for (x0, y0, x1, y1) in panels:
    height[y0:y1, x0:x1] = .5 + rng.uniform(-.06, .06)  # each plate sits a hair higher or lower
    groove[y0:y1, x0 % N] = 1; groove[y0:y1, (x1 - 1) % N] = 1; groove[y0 % N, x0:x1] = 1; groove[(y1 - 1) % N, x0:x1] = 1
    w, h = x1 - x0, y1 - y0
    r = rng.random()
    if r < .18 and w > 120 and h > 90:  # a vent: a row of slots
        n = int(rng.integers(4, 9)); vy0 = y0 + h * .3; vy1 = y0 + h * .7
        for i in range(n):
            vx = int(x0 + w * (.2 + .6 * i / max(1, n - 1)))
            height[int(vy0):int(vy1), vx - 3:vx + 3] -= .35
    elif r < .45:  # rivets along the plate edges
        step = int(rng.integers(26, 40))
        for x in range(x0 + 12, x1 - 8, step):
            for y in (y0 + 9, y1 - 10):
                height[max(0, y - 3):y + 3, max(0, x - 3):x + 3] += .25
    elif r < .55 and w > 80 and h > 80:  # an inset hatch
        m = 14; height[y0 + m:y1 - m, x0 + m:x1 - m] -= .08
        for x in (x0 + m, x1 - m - 1): groove[y0 + m:y1 - m, x] = .7
        for y in (y0 + m, y1 - m - 1): groove[y, x0 + m:x1 - m] = .7
groove = np.clip(blur(groove, 1.1) * 2.4, 0, 1)
dents = noise(40, 3)
height = blur(height, .8) - groove * .55 + (dents - .5) * .05

# ---- normal map from the height (wrap-around gradients so it tiles)
k = 3.2
dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * k
dy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * k
nz = np.ones_like(dx); ln = np.sqrt(dx * dx + dy * dy + 1)
nrm = np.stack([-dx / ln, dy / ln, nz / ln], -1) * .5 + .5
Image.fromarray((nrm * 255).astype(np.uint8)).save(os.path.join(OUT, "hull_normal.png"))

# ---- dirt and wear: darker in the grooves, streaks of grime, lighter scuffed spots
grime = noise(90, 5)
ao = blur(groove, 3)
plate_tone = np.ones((N, N))
for (x0, y0, x1, y1) in panels:
    plate_tone[y0:y1, x0:x1] = rng.uniform(.93, 1.0)
col = np.clip(plate_tone * (1 - .12 * (grime > .6) * (grime - .6) * 4) * (1 - .45 * ao), 0, 1)
col = np.clip(col * .97 + .03, 0, 1)
rgb = np.stack([col, col * .995, col * .985], -1)
Image.fromarray((rgb * 255).astype(np.uint8)).save(os.path.join(OUT, "hull_color.png"))

# ---- roughness: shiny plates, rougher grime and grooves, fine scratches
scr = np.zeros((N, N))
for _ in range(220):  # thin straight scratches
    x, y = rng.integers(0, N, 2); a = rng.uniform(0, np.pi); L = rng.integers(20, 90)
    t = np.arange(L); px = (x + np.cos(a) * t).astype(int) % N; py = (y + np.sin(a) * t).astype(int) % N
    scr[py, px] = 1
scr = np.clip(blur(scr, .6) * 3, 0, 1)
rough = np.clip(.78 + .3 * grime + .35 * ao - .25 * scr, 0, 1.25) / 1.25
orm = np.stack([np.ones_like(rough), rough, np.ones_like(rough)], -1)
Image.fromarray((orm * 255).astype(np.uint8)).save(os.path.join(OUT, "hull_rough.png"))
print("textures in", OUT)
