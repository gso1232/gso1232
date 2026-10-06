#!/usr/bin/env python3
"""
The numbers card that sits beside the ASCII portrait: a terminal window with
six tiles (streaks, totals, best day) whose figures count up to the real
value, and a contributions-per-month bar chart that grows in under them.

Same 840 x 880 canvas as portrait.svg, so the two match when the README shows
them side by side at equal widths. <img> SVGs get no script, so the count-up
is a stack of pre-drawn frames switched on and off with SMIL <set>.

    python scripts/stats.py [data.json] [out.svg]
"""
import datetime as dt
import json
import os
import sys
from html import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "contributions.json")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "stats.svg")
PROMPT = os.environ.get("PROFILE_PROMPT", "mohamed@github")

BG_TOP, BG = "#111722", "#0d1117"
TILE, EDGE = "#161b22", "#30363d"
MUTED, INK = "#7d8590", "#e6edf3"
GREEN, BAR = "#39d353", "#26a641"

W, H = 840, 880
PAD, TITLE_H, GAP = 20, 30, 16
TILE_W = (W - 2 * PAD - GAP) / 2
TILE_H = 150
TILES_Y = TITLE_H + PAD + 4
CHART_Y = TILES_Y + 3 * TILE_H + 3 * GAP

STAGGER, COUNT_FOR, STEPS = 0.15, 1.2, 16      # seconds, seconds, frames
BARS_AT, BAR_STAGGER = 6 * STAGGER + 0.4, 0.06


def day(s):
    d = dt.date.fromisoformat(s)
    return f"{d:%b} {d.day}"


def span(streak):
    return f"{day(streak['start'])} – {day(streak['end'])}" if streak["length"] else "no streak yet"


def number(v, decimal):
    return f"{v:,.1f}" if decimal else f"{int(round(v)):,}"


def counter(x, y, value, suffix, colour, start):
    """The figure, drawn STEPS times on an ease-out curve; each frame shows briefly."""
    decimal = isinstance(value, float)
    tail = f'<tspan font-size="24" font-weight="400" fill="{MUTED}">{escape(suffix)}</tspan>' if suffix else ""
    out = []
    for i in range(1, STEPS + 1):
        k = i / STEPS
        shown = value * (1 - (1 - k) ** 3)
        on = start + COUNT_FOR * (i - 1) / STEPS
        off = f'<set attributeName="opacity" to="0" begin="{start + COUNT_FOR * i / STEPS:.3f}s"/>' if i < STEPS else ""
        out.append(
            f'<text x="{x}" y="{y}" opacity="0" font-size="54" font-weight="700" fill="{colour}">'
            f'{number(shown, decimal)}{tail}'
            f'<set attributeName="opacity" to="1" begin="{on:.3f}s"/>{off}</text>'
        )
    return "".join(out)


def tile(i, label, value, suffix, caption, colour):
    col, row = i % 2, i // 2
    x = PAD + col * (TILE_W + GAP)
    y = TILES_Y + row * (TILE_H + GAP)
    t = i * STAGGER
    return (
        f'<g class="in" style="animation-delay:{t:.2f}s">'
        f'<rect x="{x}" y="{y}" width="{TILE_W}" height="{TILE_H}" rx="10" fill="{TILE}" stroke="{EDGE}"/>'
        f'<text x="{x + 24}" y="{y + 40}" fill="{MUTED}" font-size="22">$ {escape(label)}</text>'
        f'{counter(x + 24, y + 100, value, suffix, colour, t + 0.12)}'
        f'<text x="{x + 24}" y="{y + 130}" fill="{MUTED}" font-size="17">{escape(caption)}</text>'
        "</g>"
    )


def chart(months):
    x, y = PAD, CHART_Y
    w, h = W - 2 * PAD, H - PAD - CHART_Y
    left, right = x + 28, x + w - 28
    base, top = y + h - 44, y + 76
    slot = (right - left) / len(months)
    peak = max((m["count"] for m in months), default=0) or 1
    t0 = 6 * STAGGER

    out = [
        f'<g class="in" style="animation-delay:{t0:.2f}s">'
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{TILE}" stroke="{EDGE}"/>'
        f'<text x="{x + 24}" y="{y + 40}" fill="{MUTED}" font-size="22">$ contributions / month</text>'
        f'<line x1="{left}" y1="{base + 0.5}" x2="{right}" y2="{base + 0.5}" stroke="{EDGE}"/>'
    ]
    best = max(range(len(months)), key=lambda i: months[i]["count"])
    for i, m in enumerate(months):
        bh = max(2, (base - top) * m["count"] / peak) if m["count"] else 2
        bx = left + i * slot + slot * 0.16
        bw = slot * 0.68
        fill = (GREEN if i == best else BAR) if m["count"] else EDGE
        out.append(
            f'<rect class="bar" x="{bx:.1f}" y="{base - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="2" '
            f'fill="{fill}" style="animation-delay:{BARS_AT + i * BAR_STAGGER:.2f}s"/>'
        )
        letter = dt.date.fromisoformat(m["month"] + "-01").strftime("%b")[0]
        out.append(f'<text x="{bx + bw / 2:.1f}" y="{base + 26}" fill="{MUTED}" font-size="15" '
                   f'text-anchor="middle">{letter}</text>')
        if i == best and m["count"]:
            out.append(
                f'<text class="in" x="{bx + bw / 2:.1f}" y="{base - bh - 10:.1f}" fill="{INK}" font-size="15" '
                f'text-anchor="middle" style="animation-delay:{BARS_AT + len(months) * BAR_STAGGER:.2f}s">'
                f'{m["count"]:,}</text>'
            )
    out.append("</g>")
    return "".join(out)


def render(d):
    cur, lng, best = d["current_streak"], d["longest_streak"], d["best_day"]
    n = len(d["days"])
    tiles = [
        ("current streak", cur["length"], " days", span(cur), GREEN),
        ("longest streak", lng["length"], " days", span(lng), INK),
        ("contributions", d["total"], "", "in the last year", INK),
        ("active days", d["active_days"], f" / {n}", f"{d['active_days'] / n:.0%} of the year", INK),
        ("best day", best["count"], "", day(best["date"]) if best["count"] else "still to come", INK),
        ("avg / active day", float(d["per_active_day"]), "", "contributions", INK),
    ]
    return "".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        'font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace">',
        "<style>"
        ".in{opacity:0;animation:rise .45s ease-out both}"
        "@keyframes rise{0%{opacity:0;transform:translateY(14px)}100%{opacity:1;transform:none}}"
        ".bar{transform-box:fill-box;transform-origin:bottom;transform:scaleY(0);animation:grow .6s ease-out both}"
        "@keyframes grow{to{transform:scaleY(1)}}"
        "@media (prefers-reduced-motion:reduce){.in,.bar{opacity:1!important;transform:none!important;animation:none!important}}"
        "</style>",
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG_TOP}"/>'
        f'<stop offset="1" stop-color="{BG}"/></linearGradient></defs>',
        f'<rect width="{W}" height="{H}" rx="12" fill="url(#bg)"/>',
        f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="12" fill="none" stroke="{EDGE}"/>',
        f'<line x1="0" y1="{TITLE_H}" x2="{W}" y2="{TITLE_H}" stroke="{EDGE}"/>',
        '<circle cx="20" cy="15" r="5" fill="#ff5f56"/><circle cx="36" cy="15" r="5" fill="#ffbd2e"/>'
        '<circle cx="52" cy="15" r="5" fill="#27c93f"/>',
        f'<text x="{W / 2}" y="19" fill="{MUTED}" font-size="12" text-anchor="middle">{PROMPT}: ~$ ./stats.sh</text>',
        *(tile(i, *t) for i, t in enumerate(tiles)),
        chart(d["months"]),
        "</svg>",
    ])


if __name__ == "__main__":
    svg = render(json.load(open(SRC, encoding="utf-8")))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {OUT} ({len(svg) // 1024} KB)")
