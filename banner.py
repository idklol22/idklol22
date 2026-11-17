"""Cozy ASCII night scene, split into side-by-side panels.

One 960x150 scene (rainy window, city, moon, string lights, lamp, sleeping
cat, plant, books, mug, monitor) rendered once and cropped into PANELS
images with viewBox, so anything that crosses a split (rain, the string-light
wave, the shooting star) stays continuous across the row of images.

The room continues below in the main card (render.py draws the under-desk
area on the same character grid): the desk legs, drawer and the monitor
cable at CABLE_X all carry on across the image boundary.
"""

import math
import random
from xml.sax.saxutils import escape

T = 16.0
W, H = 960, 150
PANELS = 3
FS, CW, LH, TOP = 10, 6.0, 10.5, 9          # Geist Mono advance = 0.6em
COLS, ROWS = 160, 14
CABLE_COL = 127
CABLE_X = CABLE_COL * CW                     # the monitor cable leaves the banner here
TAU = math.pi * 2


def X(c):
    return c * CW


def Y(r):
    return TOP + r * LH


def nb(s):
    return escape(s).replace(" ", chr(0xA0))


class Canvas:
    def __init__(self, rows=ROWS, cols=COLS, top=TOP):
        self.rows, self.cols, self.top = rows, cols, top
        self.g = [[(" ", None)] * cols for _ in range(rows)]

    def put(self, r, c, s, tone):
        for i, ch in enumerate(s):
            if ch != " " and 0 <= r < self.rows and 0 <= c + i < self.cols:
                self.g[r][c + i] = (ch, tone)

    def svg(self, fills):
        out = []
        for tone, fill in fills.items():
            parts = []
            for r, row in enumerate(self.g):
                c = 0
                while c < self.cols:
                    if row[c][1] != tone:
                        c += 1
                        continue
                    s = c
                    while c < self.cols and (row[c][1] == tone or (row[c][0] == " " and c + 1 < self.cols
                                                              and row[c + 1][1] == tone)):
                        c += 1
                    run = "".join(ch if t == tone else " " for ch, t in row[s:c])
                    parts.append(f'<tspan x="{X(s):.1f}" y="{self.top + r * LH:.1f}">{nb(run)}</tspan>')
            if parts:
                out.append(f'<text fill="{fill}">{"".join(parts)}</text>')
        return "".join(out)


def window(t0, t1):
    """values/keyTimes: visible only between t0 and t1 within the loop."""
    return f'values="0;1;0" keyTimes="0;{t0 / T:.4f};{t1 / T:.4f}" calcMode="discrete"'


def scene(c, rnd):
    """Returns (static canvas, svg drawn behind it, animated svg on top)."""
    cv = Canvas()
    pre, anim = [], []
    loop = f'dur="{T}s" repeatCount="indefinite"'

    # ── window ──
    cv.put(1, 4, "+" + "-" * 87 + "+", "text")
    for r in range(2, 7):
        cv.put(r, 4, "|", "text"); cv.put(r, 92, "|", "text"); cv.put(r, 48, "|", "muted")
    cv.put(7, 4, "+" + "-" * 87 + "+", "text")
    cv.put(8, 2, "[" + "=" * 91 + "]", "text")

    for i, line in enumerate([" .-.", "(   )", " '-'"]):          # moon
        cv.put(2 + i, 78, line, "bright")

    x, lit = 5, []                                             # city skyline, rows 4..6
    while x < 90:
        w = rnd.randint(4, 8)
        h = 1 if 72 <= x <= 86 else rnd.randint(1, 3)
        top = 7 - h
        w = min(w, 91 - x)
        if w < 3:
            break
        cv.put(top - 1, x + 1, "_" * (w - 2), "muted")
        for r in range(top, 7):
            cv.put(r, x, "|", "muted"); cv.put(r, x + w - 1, "|", "muted")
            for k in range(x + 1, x + w - 1, 2):
                (lit.append((r, k)) if rnd.random() < 0.35 else cv.put(r, k, ".", "faint"))
        x += w + rnd.randint(0, 2)
    for r, k in lit:
        d = rnd.uniform(3, 7)
        anim.append(f'<text x="{X(k):.1f}" y="{Y(r):.1f}" fill="{c["text"]}">:'
                    f'<animate attributeName="opacity" values="1;.25;1" dur="{d:.1f}s" '
                    f'begin="{rnd.uniform(0, d):.1f}s" repeatCount="indefinite"/></text>')

    for _ in range(12):                                        # stars
        r, k = rnd.randint(2, 3), rnd.randint(6, 90)
        if 76 <= k <= 84 or k == 48:
            continue
        d = rnd.uniform(2, 5)
        anim.append(f'<text x="{X(k):.1f}" y="{Y(r):.1f}" fill="{c["bright"]}">{rnd.choice(".+.*")}'
                    f'<animate attributeName="opacity" values=".2;1;.2" dur="{d:.1f}s" '
                    f'begin="{rnd.uniform(0, d):.1f}s" repeatCount="indefinite"/></text>')

    # rain, clipped to the glass
    anim.append(f'<clipPath id="glass"><rect x="{X(5):.0f}" y="{Y(1) + 2:.0f}" width="{X(87):.0f}" '
                f'height="{Y(7) - Y(1) - 10:.0f}"/></clipPath><g clip-path="url(#glass)" fill="{c["muted"]}">')
    for _ in range(60):
        x0 = rnd.uniform(X(5), X(95))
        d = rnd.uniform(0.55, 0.9)
        anim.append(f'<text>{rnd.choice(chr(39) + "|,")}'
                    f'<animateTransform attributeName="transform" type="translate" '
                    f'values="{x0:.0f} {Y(1):.0f};{x0 - 10:.0f} {Y(7):.0f}" dur="{d:.2f}s" '
                    f'begin="{rnd.uniform(0, d):.2f}s" repeatCount="indefinite"/></text>')
    anim.append("</g>")

    # shooting star once per loop, across the window
    anim.append(f'<g fill="{c["bright"]}" opacity="0"><text>*<tspan dx="-18" fill="{c["muted"]}">--</tspan></text>'
                f'<animateTransform attributeName="transform" type="translate" {loop} '
                f'values="{X(8):.0f} {Y(2):.0f};{X(8):.0f} {Y(2):.0f};{X(64):.0f} {Y(3):.0f};{X(64):.0f} {Y(3):.0f}" '
                f'keyTimes="0;{7 / T:.4f};{7.9 / T:.4f};1"/>'
                f'<animate attributeName="opacity" {loop} {window(7.0, 7.9)}/></g>')

    # ── string lights: a twinkle wave travelling across every panel ──
    cv.put(0, 0, "." * COLS, "faint")
    for k in range(3, COLS, 7):
        anim.append(f'<text x="{X(k):.1f}" y="{Y(0) + 2:.1f}" fill="{c["bright"]}">o'
                    f'<animate attributeName="opacity" values="1;.25;1" dur="4s" begin="{k * 0.025:.2f}s" '
                    f'repeatCount="indefinite"/></text>')

    # ── desk ──
    cv.put(11, 0, "=" * COLS, "text")
    for r in range(12, ROWS):
        cv.put(r, 3, "|", "muted"); cv.put(r, 156, "|", "muted")
    cv.put(12, 8, ".--------------------.", "muted")
    cv.put(13, 8, "|       [ __ ]       |", "muted")

    cv.put(9, 8, "[_________]", "text")                       # books
    cv.put(10, 8, "[_______]_]", "text")
    cv.put(9, 25, "\\\\|//", "text")                           # plant
    cv.put(10, 25, "[___]", "muted")

    cat = ["  /\\_/\\", " ( -.- )___)~"]                       # sleeping cat, breathing
    rows = "".join(f'<tspan x="{X(44):.1f}" y="{Y(9 + i):.1f}">{nb(l)}</tspan>' for i, l in enumerate(cat))
    base = Y(10)
    anim.append(f'<g><text fill="{c["bright"]}">{rows}</text>'
                f'<animateTransform attributeName="transform" type="matrix" dur="4s" repeatCount="indefinite" '
                f'values="1 0 0 1 0 0;1 0 0 1.06 0 {-0.06 * base:.2f};1 0 0 1 0 0"/></g>')
    for i, z in enumerate("zZz"):
        anim.append(f'<text fill="{c["muted"]}" opacity="0">{z}'
                    f'<animateTransform attributeName="transform" type="translate" dur="6s" begin="{i * 2}s" '
                    f'repeatCount="indefinite" values="{X(52):.0f} {Y(9):.0f};{X(55):.0f} {Y(7):.0f};{X(53):.0f} {Y(5):.0f}"/>'
                    f'<animate attributeName="opacity" values="0;.9;0" dur="6s" begin="{i * 2}s" repeatCount="indefinite"/></text>')

    # lamp + glow
    for i, line in enumerate(["  ____", " /    \\", "/______\\", "   ||", "   ||", "   ||", "   ||", "   ||", "  [__]"]):
        cv.put(2 + i, 98, line, "text" if i < 3 else "muted")
    pre.append(f'<radialGradient id="glow"><stop offset="0" stop-color="{c["glow"]}" stop-opacity=".2"/>'
               f'<stop offset="1" stop-color="{c["glow"]}" stop-opacity="0"/></radialGradient>'
               f'<ellipse cx="{X(102):.0f}" cy="{Y(6):.0f}" rx="75" ry="48" fill="url(#glow)">'
               f'<animate attributeName="opacity" values="1;.85;1;.95;1" dur="5s" repeatCount="indefinite"/></ellipse>')

    # monitor
    cv.put(1, 112, "." + "-" * 25 + ".", "text")
    for r in range(2, 7):
        cv.put(r, 112, "|", "text"); cv.put(r, 138, "|", "text")
    cv.put(7, 112, "'" + "-" * 25 + "'", "text")
    cv.put(8, 123, "|___|", "muted")
    cv.put(9, 121, "_|_____|_", "muted")
    cv.put(10, 120, "[_________]", "muted")

    code = [("~ $ vim rain.py", 0.4), ("for drop in sky:", 2.0), ("  drop.fall()", 3.6),
            ("~ $ git commit -am wip", 9.0), ("~ $ git push  ->", 12.2)]
    for i, (line, at) in enumerate(code):
        anim.append(f'<text x="{X(114):.1f}" y="{Y(2 + i):.1f}" fill="{c["bright"] if line.startswith("~") else c["text"]}" '
                    f'opacity="{1 if i < 3 else 0}">{nb(line)}'
                    f'<animate attributeName="opacity" {loop} {window(at, 15.6)}/></text>')
    anim.append(f'<rect x="{X(131):.0f}" y="{Y(6) - 7:.0f}" width="5" height="8" fill="{c["bright"]}">'
                f'<animate attributeName="opacity" values="1;0" dur="1s" calcMode="discrete" repeatCount="indefinite"/></rect>')

    # mug + steam
    cv.put(9, 145, " __", "muted")
    cv.put(10, 144, "c[__]", "text")
    for i in range(5):
        d, sx = 3.6, X(146.5)
        pts = ";".join(f"{sx + 3 * math.sin(k / 4 * TAU + i):.0f} {Y(9) - k * 8:.0f}" for k in range(5))
        anim.append(f'<text fill="{c["muted"]}" opacity="0">{"~()~."[i]}'
                    f'<animateTransform attributeName="transform" type="translate" dur="{d}s" begin="{i * d / 5:.2f}s" '
                    f'repeatCount="indefinite" values="{pts}"/>'
                    f'<animate attributeName="opacity" values="0;.8;0" dur="{d}s" begin="{i * d / 5:.2f}s" repeatCount="indefinite"/></text>')

    # cable: monitor stand -> behind the desk -> out the bottom at CABLE_X
    sx, sy = X(125), Y(10) + 3
    path = f"M{sx:.0f},{sy:.0f} C{sx:.0f},{Y(12):.0f} {CABLE_X},{Y(11.5):.0f} {CABLE_X},{H}"
    pre.append(f'<path d="{path}" fill="none" stroke="{c["muted"]}" stroke-width="1.5" '
               f'stroke-dasharray="1 4" stroke-linecap="round"/>')
    return cv, pre, anim


def panels(c, font_css, mono):
    rnd = random.Random(5)
    cv, pre, anim = scene(c, rnd)
    body = (f'<g font-family="{mono}" font-size="{FS}">' + "".join(pre)
            + cv.svg({"faint": c["faint"], "muted": c["muted"], "text": c["text"], "bright": c["bright"]})
            + "".join(anim) + "</g>")
    pw = W / PANELS
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{pw:.0f}" height="{H}" '
            f'viewBox="{i * pw:.0f} 0 {pw:.0f} {H}"><style>{font_css}</style>'
            f'<rect x="{i * pw:.0f}" width="{pw:.0f}" height="{H}" fill="{c["bg"]}"/>{body}</svg>'
            for i in range(PANELS)]
