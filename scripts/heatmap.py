#!/usr/bin/env python3
"""
Draw data/contributions.json as GitHub's own year grid, dark theme, and make
it play: the squares pop in as a diagonal wave from the oldest week to today,
and every active day flashes bright as it lands.

GitHub shows README SVGs through <img>, where CSS animation runs and scripts
do not, so the whole thing is CSS keyframes with a per-cell delay.

    python scripts/heatmap.py [data.json] [out.svg]
"""
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "contributions.json")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "contributions.svg")

# GitHub dark: empty, then the four quartiles
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
LABEL = "#7d8590"
INK = "#e6edf3"

CELL, PITCH = 13, 16
LEFT, TOP = 34, 24             # room for Mon/Wed/Fri and the month row
COL_DELAY, ROW_DELAY = 0.064, 0.036   # the wave: ~3.4 s across a year


def weeks_of(days):
    """Columns of 7 slots, Sunday first, like GitHub; None pads the ends."""
    cols, col = [], [None] * 7
    for d in days:
        wd = (dt.date.fromisoformat(d["date"]).weekday() + 1) % 7   # Sun = 0
        if wd == 0 and any(col):
            cols.append(col)
            col = [None] * 7
        col[wd] = d
    cols.append(col)
    return cols


def month_labels(cols):
    """GitHub's rule: a month is named over the first week whose top day is in it."""
    out, prev = [], None
    for c, col in enumerate(cols):
        month = dt.date.fromisoformat(next(d for d in col if d)["date"]).strftime("%b")
        if month != prev:
            if out and c - out[-1][0] < 3:
                out.pop()       # too close to fit: the later month wins
            out.append((c, month))
            prev = month
    return [(LEFT + c * PITCH, m) for c, m in out]


def render(data):
    cols = weeks_of(data["days"])
    w = LEFT + len(cols) * PITCH + 6
    h = TOP + 7 * PITCH + 34

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif">',
        "<style>"
        f".l{{fill:{LABEL};font-size:13px;font-weight:600}}"
        f".t{{fill:{INK};font-size:15px;font-weight:700}}"
        ".s{transform-box:fill-box;transform-origin:center;opacity:0;animation:pop .55s ease-out both}"
        ".a{animation:pop .55s ease-out both,glow .7s ease-out both}"
        "@keyframes pop{0%{opacity:0;transform:scale(.2)}60%{opacity:1;transform:scale(1.12)}"
        "100%{opacity:1;transform:scale(1)}}"
        "@keyframes glow{0%,45%{filter:brightness(2.4)}100%{filter:brightness(1)}}"
        "@media (prefers-reduced-motion:reduce){.s{opacity:1!important;animation:none!important}}"
        "</style>",
    ]
    for x, name in month_labels(cols):
        parts.append(f'<text class="l" x="{x}" y="16">{name}</text>')
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        parts.append(f'<text class="l" x="2" y="{TOP + row * PITCH + 11}">{name}</text>')

    for c, col in enumerate(cols):
        for r, d in enumerate(col):
            if not d:
                continue
            cls = "s a" if d["count"] else "s"
            delay = c * COL_DELAY + r * ROW_DELAY
            parts.append(
                f'<rect class="{cls}" x="{LEFT + c * PITCH}" y="{TOP + r * PITCH}" width="{CELL}" '
                f'height="{CELL}" rx="2.5" fill="{LEVELS[d["level"]]}" style="animation-delay:{delay:.3f}s">'
                f'<title>{d["date"]}: {d["count"]}</title></rect>'
            )

    parts.append(f'<text class="t" x="{LEFT}" y="{TOP + 7 * PITCH + 18}">'
                 f'{data["total"]:,} contributions in the last year</text>')
    parts.append("</svg>")
    return "".join(parts)


if __name__ == "__main__":
    data = json.load(open(SRC, encoding="utf-8"))
    svg = render(data)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {OUT} ({len(svg) // 1024} KB)")
