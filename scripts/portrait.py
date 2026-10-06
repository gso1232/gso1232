#!/usr/bin/env python3
"""
Turn a photo into the ASCII self-portrait that prints itself into a terminal
window, row by row behind a block cursor, then holds. 840 x 880, the same
canvas as stats.svg, so the two sit level in the README.

1. cut the person out (U^2-Net human segmentation, the model rembg caches)
2. smooth skin texture but keep edges, then stretch tones over the person only
3. push thin dark lines (eyes, brows, glasses, mouth) darker so they survive
   being averaged into 4 px character cells
4. map brightness to a density ramp: paper white is a space, the darkest is '@'

On the dark window the ink is light, so hair and outlines come out bright and
skin stays sparse: a pencil drawing in negative.

    python scripts/portrait.py photo/me.jpg [out.svg]

Tuning through env: COLS (detail, default 180), GAMMA (>1 lightens the face),
LINES (line darkening), SMOOTH and LOCAL (texture and local contrast), TONE="lo,hi" (percentiles that become black and white), CROP="x,y,side" in source pixels to override the
automatic head-and-shoulders square, and NAME for the status line.
"""
import os
import sys
from html import escape

import cv2
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "portrait.svg")
PREVIEW = os.path.join(ROOT, "photo", "prepped.png")

COLS = int(os.environ.get("COLS", 180))
GAMMA = float(os.environ.get("GAMMA", 1.5))
LINES = float(os.environ.get("LINES", 1.2))
TONE = [float(v) for v in os.environ.get("TONE", "2,75").split(",")]   # percentiles mapped to black, white
SMOOTH = int(os.environ.get("SMOOTH", 0))          # bilateral passes: fewer keeps more texture
LOCAL = float(os.environ.get("LOCAL", 3.5))        # CLAHE clip: local contrast in hair and shadows
WHITE = 0.82                       # brighter than this prints as a space
RAMP = " .,:-=+*xs#%@"             # sparse -> dense
PROMPT = os.environ.get("PROFILE_PROMPT", "mohamed@github")
NAME = os.environ.get("NAME", "Mohamed Samy")

BG_TOP, BG, EDGE = "#111722", "#0d1117", "#30363d"
MUTED, INK = "#7d8590", "#c9d1d9"

W, H = 840, 880
PAD, TITLE_H, STATUS_H = 20, 30, 43
CELL_W = (W - 2 * PAD) / COLS
CELL_H = CELL_W * 15 / 8            # monospace cells are ~1.875x taller than wide
ROWS = int((H - TITLE_H - STATUS_H - 6) / CELL_H)
PRINT_FOR = 5.8                     # seconds for the whole portrait


def cut_out(path):
    """U^2-Net human segmentation, run straight through onnxruntime on the CPU
    (the model rembg caches in ~/.u2net); returns the RGB and a 0-255 mask.
    A PNG that already has an alpha channel is taken as cut out."""
    src = Image.open(path)
    if src.mode == "RGBA":
        rgba = np.asarray(src)
        return rgba[..., :3], rgba[..., 3]

    import onnxruntime as ort
    model = os.path.join(os.path.expanduser("~"), ".u2net", "u2net_human_seg.onnx")
    opts = ort.SessionOptions()
    opts.enable_cpu_mem_arena = False          # keeps the footprint small
    sess = ort.InferenceSession(model, opts, providers=["CPUExecutionProvider"])

    photo = Image.open(path).convert("RGB")
    x = np.asarray(photo.resize((320, 320), Image.LANCZOS), np.float32)
    x = (x / x.max() - (0.485, 0.456, 0.406)) / (0.229, 0.224, 0.225)
    x = x.transpose(2, 0, 1)[None].astype(np.float32)
    pred = sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0]
    pred = (pred - pred.min()) / max(pred.max() - pred.min(), 1e-6)
    mask = Image.fromarray((pred * 255).astype(np.uint8)).resize(photo.size, Image.LANCZOS)
    return np.asarray(photo), np.asarray(mask)


def prep(rgb, alpha):
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    smooth = gray
    for _ in range(SMOOTH):
        smooth = cv2.bilateralFilter(smooth, 9, 40, 9)

    person = alpha > 128
    clahe = cv2.createCLAHE(clipLimit=LOCAL, tileGridSize=(8, 8)).apply(smooth)
    lo, hi = np.percentile(clahe[person], TONE)
    tone = np.clip((clahe.astype(np.float32) - lo) / max(hi - lo, 1), 0, 1)

    # thin dark strokes: fine blur darker than coarse blur
    fine = cv2.GaussianBlur(smooth, (0, 0), 1.5).astype(np.float32)
    coarse = cv2.GaussianBlur(smooth, (0, 0), 6).astype(np.float32)
    ridges = np.clip((coarse - fine) / 40.0, 0, 1)
    img = np.clip(tone - LINES * ridges, 0, 1)

    mask = cv2.GaussianBlur(alpha.astype(np.float32) / 255, (0, 0), 1.0)
    return img * mask + (1 - mask)       # onto white paper


def square(img, alpha):
    if os.environ.get("CROP"):
        x, y, side = (int(v) for v in os.environ["CROP"].split(","))
    else:
        # the whole person with a margin; a tall photo wants CROP instead
        ys, xs = np.nonzero(alpha > 20)
        side = max(xs.max() - xs.min(), ys.max() - ys.min()) + 60
        x = (xs.min() + xs.max()) // 2 - side // 2
        y = (ys.min() + ys.max()) // 2 - side // 2
    canvas = np.ones((side, side), np.float32)
    sx0, sy0 = max(x, 0), max(y, 0)
    sx1, sy1 = min(x + side, img.shape[1]), min(y + side, img.shape[0])
    canvas[sy0 - y: sy1 - y, sx0 - x: sx1 - x] = img[sy0:sy1, sx0:sx1]
    return canvas


def to_ascii(img):
    small = cv2.resize(img, (COLS, ROWS), interpolation=cv2.INTER_AREA)
    small = small ** (1 / GAMMA)
    rows = []
    for line in small:
        chars = []
        for v in line:
            if v >= WHITE:
                chars.append(" ")
            else:
                k = (WHITE - v) / WHITE          # 0 at paper, 1 at black
                chars.append(RAMP[1 + min(len(RAMP) - 2, int(k * (len(RAMP) - 1)))])
        rows.append("".join(chars))
    return rows


def svg(rows):
    art_w = COLS * CELL_W
    top = TITLE_H + 6
    step = PRINT_FOR / len(rows)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace">',
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG_TOP}"/>'
        f'<stop offset="1" stop-color="{BG}"/></linearGradient></defs>',
        f'<rect width="{W}" height="{H}" rx="12" fill="url(#bg)"/>',
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="none" stroke="{EDGE}"/>',
        f'<line x1="0" y1="{TITLE_H}" x2="{W}" y2="{TITLE_H}" stroke="{EDGE}"/>',
        '<circle cx="20" cy="15" r="5" fill="#ff5f56"/><circle cx="36" cy="15" r="5" fill="#ffbd2e"/>'
        '<circle cx="52" cy="15" r="5" fill="#27c93f"/>',
        f'<text x="{W / 2}" y="19" fill="{MUTED}" font-size="12" text-anchor="middle">{PROMPT}: ~$ ./portrait.sh</text>',
    ]
    for i, row in enumerate(rows):
        y = top + i * CELL_H
        t = i * step
        if row.strip():
            # the row is all there; a clip opening left to right is what "types" it
            out.append(
                f'<clipPath id="r{i}"><rect x="{PAD}" y="{y:.2f}" height="{CELL_H:.2f}" width="0">'
                f'<animate attributeName="width" from="0" to="{art_w:.1f}" begin="{t:.3f}s" dur="{step:.3f}s" '
                f'fill="freeze"/></rect></clipPath>'
                f'<text clip-path="url(#r{i})" xml:space="preserve" x="{PAD}" y="{y + CELL_H * 0.74:.2f}" '
                f'fill="{INK}" font-size="{CELL_H * 0.86:.2f}" textLength="{art_w:.1f}" '
                f'lengthAdjust="spacing">{escape(row)}</text>'
            )
        # the block cursor rides the edge of the opening, one row at a time
        out.append(
            f'<rect y="{y + 1:.2f}" width="{CELL_W:.2f}" height="{CELL_H - 2:.2f}" fill="{INK}" opacity="0">'
            f'<animate attributeName="x" from="{PAD}" to="{PAD + art_w:.1f}" begin="{t:.3f}s" dur="{step:.3f}s" '
            f'fill="freeze"/><set attributeName="opacity" to=".85" begin="{t:.3f}s"/>'
            f'<set attributeName="opacity" to="0" begin="{t + step:.3f}s"/></rect>'
        )
    sy = H - STATUS_H
    out += [
        f'<line x1="0" y1="{sy}" x2="{W}" y2="{sy}" stroke="{EDGE}"/>',
        f'<text x="{PAD}" y="{sy + 27}" fill="{MUTED}" font-size="14" xml:space="preserve">'
        f'{PROMPT}:~$ whoami <tspan fill="{INK}">{escape(NAME)}</tspan> '
        f'<tspan fill="{INK}">█<animate attributeName="fill-opacity" values="1;1;0;0" keyTimes="0;.5;.51;1" '
        f'dur="1s" repeatCount="indefinite"/></tspan></text>',
        "</svg>",
    ]
    return "".join(out)


if __name__ == "__main__":
    rgb, alpha = cut_out(SRC)
    img = square(prep(rgb, alpha), alpha)
    os.makedirs(os.path.dirname(PREVIEW), exist_ok=True)
    Image.fromarray((img * 255).astype(np.uint8)).save(PREVIEW)
    rows = to_ascii(img)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg(rows))
    print(f"wrote {OUT}: {COLS} x {ROWS} characters; prepped image at {PREVIEW}")
