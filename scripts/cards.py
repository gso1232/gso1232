#!/usr/bin/env python3
"""
Project cards for the README's `ls ~/projects` section: each screenshot sits in
a dark browser window (traffic lights, the site's address in the title bar),
the same chrome as the terminal cards above it, so the page reads as one desk.

The screenshots come from the printed photos on the 3D desk in my portfolio
(lut-portfolio/blender/textures/photo-*.png): a white border and a caption
strip around each capture, which crop() trims back to the capture itself.
The JPEG is embedded, because GitHub serves README SVGs as images and an
image cannot load anything else.

    python scripts/cards.py [photos dir]
"""
import base64
import io
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHOTOS = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "..", "lut-portfolio", "blender", "textures")
OUT = os.path.join(ROOT, "assets", "projects")

# slug: (photo, address shown in the title bar)
CARDS = {
    "synergy": ("photo-synergy.png", "fflsynergy.com"),
    "duriza": ("photo-duriza.png", "durizaeg.com"),
    "monopoly-eg": ("photo-ganeeh.png", "monopoly-eg.vercel.app"),
    "adham-assem": ("photo-adham-assem.png", "adham-assem.vercel.app"),
    "sondos": ("photo-sondos.png", "sondos-ten.vercel.app"),
    "ast-generator": ("photo-ast-generator.png", "project-u6myu.vercel.app"),
}

W, BAR, R = 840, 34, 12
EDGE, BAR_BG, MUTED = "#30363d", "#161b22", "#7d8590"


def capture_box(path):
    """Where the capture sits inside the printed photo: everything that isn't
    paper, above the caption strip. Measured on a dark capture, because a
    capture with white areas reads as paper at its edges."""
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.int16)
    h = a.shape[0]
    paper = np.median(np.concatenate([a[:8, :8].reshape(-1, 3), a[:8, -8:].reshape(-1, 3)]), axis=0)
    ink = np.abs(a - paper).sum(axis=2) > 40
    ink[int(h * 0.86):] = False                          # the caption strip
    rows = np.nonzero(ink.mean(axis=1) > 0.5)[0]
    cols = np.nonzero(ink[rows.min():rows.max()].mean(axis=0) > 0.5)[0]
    return cols.min(), rows.min(), cols.max() + 1, rows.max() + 1


def card(shot, address):
    shot = shot.resize((W, round(W * shot.height / shot.width)), Image.LANCZOS)
    buf = io.BytesIO()
    shot.save(buf, "JPEG", quality=84, optimize=True, progressive=True)
    data = base64.b64encode(buf.getvalue()).decode()
    h = BAR + shot.height
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" '
        'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace">'
        f'<defs><clipPath id="w"><rect width="{W}" height="{h}" rx="{R}"/></clipPath></defs>'
        f'<g clip-path="url(#w)">'
        f'<rect width="{W}" height="{BAR}" fill="{BAR_BG}"/>'
        f'<image href="data:image/jpeg;base64,{data}" x="0" y="{BAR}" width="{W}" height="{shot.height}"/>'
        f'</g>'
        f'<line x1="0" y1="{BAR}" x2="{W}" y2="{BAR}" stroke="{EDGE}"/>'
        '<circle cx="20" cy="17" r="5.5" fill="#ff5f56"/><circle cx="38" cy="17" r="5.5" fill="#ffbd2e"/>'
        '<circle cx="56" cy="17" r="5.5" fill="#27c93f"/>'
        f'<rect x="{W / 2 - 150}" y="7" width="300" height="20" rx="6" fill="#0d1117" stroke="{EDGE}"/>'
        f'<text x="{W / 2}" y="21.5" fill="{MUTED}" font-size="12.5" text-anchor="middle">{address}</text>'
        f'<rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="{R}" fill="none" stroke="{EDGE}"/>'
        "</svg>"
    )


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    # every photo is printed with the same border, so one box fits them all
    box = capture_box(os.path.join(PHOTOS, CARDS["duriza"][0]))
    for slug, (photo, address) in CARDS.items():
        shot = Image.open(os.path.join(PHOTOS, photo)).convert("RGB").crop(box)
        svg = card(shot, address)
        path = os.path.join(OUT, f"{slug}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote {path} ({len(svg) // 1024} KB)")
