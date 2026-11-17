"""Cozy ASCII night scene, split into side-by-side panels.

One 960x300 scene (rainy window, city, moon, string lights, lamp, sleeping
cat, plant, books, mug, monitor) rendered once and cropped into PANELS
images with viewBox, so anything that crosses a split (rain, the string-light
wave, the shooting star) stays continuous across the row of images.

Everything runs on the shared 16 s loop: code gets typed on the monitor,
`git push` goes out, and pulses run down the cable that leaves the bottom
of the banner at CABLE_X, into the card below.
"""

import math
import random
from xml.sax.saxutils import escape

T = 16.0
W, H = 960, 300
PANELS = 3
FS, CW, LH, TOP = 12, 7.2, 13, 17            # Geist Mono advance = 0.6em
COLS, ROWS = 133, 22
CABLE_X = 750                                  # must match the orb's centre in the card below
TAU = math.pi * 2


def X(c):
    return c * CW


def Y(r):
    return TOP + r * LH


class Canvas:
    def __init__(self):
        self.g = [[(" ", None)] * COLS for _ in range(ROWS)]

    def put(self, r, c, s, tone):
        for i, ch in enumerate(s):
            if ch != " " and 0 <= r < ROWS and 0 <= c + i < COLS:
                self.g[r][c + i] = (ch, tone)

    def svg(self, fills):
        out = []
        for tone, fill in fills.items():
            parts = []
            for r, row in enumerate(self.g):
                c = 0
                while c < COLS:
                    if row[c][1] != tone:
                        c += 1
                        continue
                    s = c
                    while c < COLS and (row[c][1] == tone or (row[c][0] == " " and c + 1 < COLS
                                                              and row[c + 1][1] == tone)):
                        c += 1
                    run = "".join(ch if t == tone else " " for ch, t in row[s:c])
                    parts.append(f'<tspan x="{X(s):.1f}" y="{Y(r):.1f}">{escape(run).replace(" ", chr(0xA0))}</tspan>')
            if parts:
                out.append(f'<text fill="{fill}">{"".join(parts)}</text>')
        return "".join(out)


def window(t0, t1):
    """keyTimes/values helper: visible only between t0 and t1 within the loop."""
    a, b = t0 / T, t1 / T
    return f'values="0;1;0" keyTimes="0;{a:.4f};{b:.4f}" calcMode="discrete"'


def scene(c, rnd):
    """Returns (static canvas, svg drawn behind it, animated svg on top)."""
    cv = Canvas()
    pre, anim = [], []
    loop = f'dur="{T}s" repeatCount="indefinite"'

    # ── window ──
    cv.put(2, 6, "+" + "-" * 79 + "+", "text")
    for r in range(3, 11):
        cv.put(r, 6, "|", "text"); cv.put(r, 86, "|", "text"); cv.put(r, 46, "|", "muted")
    cv.put(11, 6, "+" + "-" * 79 + "+", "text")
    cv.put(12, 4, "[" + "=" * 83 + "]", "text")

    # moon
    for i, line in enumerate([" .--.", "/    \\", "|  .  |", "\\  ' /", " '--'"]):
        cv.put(3 + i, 69, line, "bright")

    # city skyline (rows 7..10), kept low near the moon
    x = 7
    lit = []
    while x < 84:
        w = rnd.randint(4, 8)
        h = rnd.randint(1, 2) if 62 <= x <= 78 else rnd.randint(1, 4)
        top = 11 - h
        if x + w > 85:
            w = 85 - x
        if w < 3:
            break
        cv.put(top - 1, x + 1, "_" * (w - 2), "muted")
        for r in range(top, 11):
            cv.put(r, x, "|", "muted"); cv.put(r, x + w - 1, "|", "muted")
            for k in range(x + 1, x + w - 1, 2):
                if rnd.random() < 0.35:
                    lit.append((r, k))
                else:
                    cv.put(r, k, ".", "faint")
        x += w + rnd.randint(0, 2)
    for r, k in lit:                                   # lit windows breathe
        d = rnd.uniform(3, 7)
        anim.append(f'<text x="{X(k):.1f}" y="{Y(r):.1f}" fill="{c["text"]}">:'
                    f'<animate attributeName="opacity" values="1;.25;1" dur="{d:.1f}s" '
                    f'begin="{rnd.uniform(0, d):.1f}s" repeatCount="indefinite"/></text>')

    # stars
    for _ in range(16):
        r, k = rnd.randint(3, 6), rnd.randint(8, 84)
        if 67 <= k <= 77 or k == 46:
            continue
        d = rnd.uniform(2, 5)
        anim.append(f'<text x="{X(k):.1f}" y="{Y(r):.1f}" fill="{c["bright"]}">{rnd.choice(".+.*")}'
                    f'<animate attributeName="opacity" values=".2;1;.2" dur="{d:.1f}s" '
                    f'begin="{rnd.uniform(0, d):.1f}s" repeatCount="indefinite"/></text>')

    # rain, clipped to the glass
    anim.append(f'<clipPath id="glass"><rect x="{X(7):.0f}" y="{Y(2) + 3:.0f}" width="{X(79):.0f}" '
                f'height="{Y(11) - Y(2) - 12:.0f}"/></clipPath><g clip-path="url(#glass)" fill="{c["muted"]}">')
    for _ in range(70):
        x0 = rnd.uniform(X(7), X(88))
        d = rnd.uniform(0.7, 1.2)
        anim.append(f'<text>{rnd.choice(chr(39) + "|,")}'
                    f'<animateTransform attributeName="transform" type="translate" '
                    f'values="{x0:.0f} {Y(2):.0f};{x0 - 18:.0f} {Y(11):.0f}" dur="{d:.2f}s" '
                    f'begin="{rnd.uniform(0, d):.2f}s" repeatCount="indefinite"/></text>')
    anim.append("</g>")

    # shooting star once per loop, across the two window panels
    anim.append(f'<g fill="{c["bright"]}" opacity="0"><text>*<tspan dx="-22" fill="{c["muted"]}">--</tspan></text>'
                f'<animateTransform attributeName="transform" type="translate" {loop} '
                f'values="{X(12):.0f} {Y(3):.0f};{X(12):.0f} {Y(3):.0f};{X(60):.0f} {Y(5):.0f};{X(60):.0f} {Y(5):.0f}" '
                f'keyTimes="0;{7 / T:.4f};{7.9 / T:.4f};1"/>'
                f'<animate attributeName="opacity" {loop} {window(7.0, 7.9)}/></g>')

    # ── string lights: a sagging wire with a twinkle wave travelling across every panel ──
    for k in range(COLS):
        r = 0 if (k % 22) in (0, 1, 21) else 1
        cv.put(r, k, "." if r else "'", "faint")
    for k in range(4, COLS, 7):
        r = 0 if (k % 22) in (0, 1, 21) else 1
        anim.append(f'<text x="{X(k):.1f}" y="{Y(r) + 4:.1f}" fill="{c["bright"]}">o'
                    f'<animate attributeName="opacity" values="1;.25;1" dur="4s" begin="{k * 0.03:.2f}s" '
                    f'repeatCount="indefinite"/></text>')

    # ── desk ──
    cv.put(16, 0, "=" * COLS, "text")
    for r in range(17, ROWS):
        cv.put(r, 3, "|", "muted"); cv.put(r, 129, "|", "muted")
    cv.put(17, 8, ".---------------------.", "muted")
    cv.put(18, 8, "|        [ __ ]        |", "muted")
    cv.put(19, 8, "'---------------------'", "muted")

    # books
    cv.put(13, 10, " _________", "muted")
    cv.put(14, 10, "[_________]", "text")
    cv.put(15, 10, "[_______]_]", "text")

    # plant
    cv.put(13, 26, "\\\\|//", "text")
    cv.put(14, 25, "[_____]", "muted")
    cv.put(15, 26, "\\___/", "muted")

    # sleeping cat (breathes) + rising z's
    cat = ["  /\\_/\\", " ( -.- )___", " (__ __)___)~"]
    rows = "".join(f'<tspan x="{X(48):.1f}" y="{Y(13 + i):.1f}">{escape(l).replace(" ", chr(0xA0))}</tspan>'
                   for i, l in enumerate(cat))
    base = Y(15)
    anim.append(f'<g><text fill="{c["bright"]}">{rows}</text>'
                f'<animateTransform attributeName="transform" type="matrix" dur="4s" repeatCount="indefinite" '
                f'values="1 0 0 1 0 0;1 0 0 1.05 0 {-0.05 * base:.2f};1 0 0 1 0 0"/></g>')
    for i, z in enumerate("zZz"):
        anim.append(f'<text fill="{c["muted"]}" opacity="0">{z}'
                    f'<animateTransform attributeName="transform" type="translate" dur="6s" begin="{i * 2}s" '
                    f'repeatCount="indefinite" values="{X(57):.0f} {Y(13):.0f};{X(61):.0f} {Y(10):.0f};{X(59):.0f} {Y(7):.0f}"/>'
                    f'<animate attributeName="opacity" values="0;.9;0" dur="6s" begin="{i * 2}s" repeatCount="indefinite"/></text>')

    # lamp + glow
    for i, line in enumerate(["  ____", " /    \\", "/______\\", "   ||", "   ||", "   ||", "   ||", "   ||", "  _||_", " [____]"]):
        cv.put(6 + i, 89, line, "text" if i < 3 else "muted")
    pre.append(f'<radialGradient id="glow"><stop offset="0" stop-color="{c["glow"]}" stop-opacity=".22"/>'
                   f'<stop offset="1" stop-color="{c["glow"]}" stop-opacity="0"/></radialGradient>'
                   f'<ellipse cx="{X(93):.0f}" cy="{Y(12):.0f}" rx="95" ry="70" fill="url(#glow)">'
                   f'<animate attributeName="opacity" values="1;.85;1;.95;1" dur="5s" repeatCount="indefinite"/></ellipse>')

    # monitor
    cv.put(4, 100, ".-----------------------.", "text")
    for r in range(5, 12):
        cv.put(r, 100, "|", "text"); cv.put(r, 124, "|", "text")
    cv.put(12, 100, "'-----------------------'", "text")
    cv.put(13, 110, "|___|", "muted")
    cv.put(14, 108, "_|_____|_", "muted")
    cv.put(15, 107, "[_________]", "muted")

    # code typed over the loop, then pushed
    code = [("~/idklol22 $", 0.4), ("vim orb.py", 1.6), ("for p in swarm:", 3.2), ("  p.drift(t)", 4.6),
            ("  p.glow()", 6.0), ("git commit -am wip", 9.0), ("git push  ->", 12.2)]
    for i, (line, at) in enumerate(code):
        anim.append(f'<text x="{X(102):.1f}" y="{Y(5 + i):.1f}" fill="{c["bright"] if i in (0, 6) else c["text"]}" '
                    f'opacity="{1 if i < 5 else 0}">{escape(line).replace(" ", chr(0xA0))}'
                    f'<animate attributeName="opacity" {loop} {window(at, 15.6)}/></text>')
    anim.append(f'<rect x="{X(102):.0f}" y="{Y(11) - 9:.0f}" width="6" height="10" fill="{c["bright"]}">'
                f'<animate attributeName="opacity" values="1;0" dur="1s" calcMode="discrete" repeatCount="indefinite"/></rect>')

    # mug + steam
    cv.put(14, 126, " __", "muted")
    cv.put(15, 125, "c[__]", "text")
    for i in range(6):
        d, sx = 3.6, X(127.5)
        pts = ";".join(f"{sx + 4 * math.sin(k / 4 * TAU + i):.0f} {Y(14) - k * 9:.0f}" for k in range(6))
        anim.append(f'<text fill="{c["muted"]}" opacity="0">{"~()~.,"[i]}'
                    f'<animateTransform attributeName="transform" type="translate" dur="{d}s" begin="{i * d / 6:.2f}s" '
                    f'repeatCount="indefinite" values="{pts}"/>'
                    f'<animate attributeName="opacity" values="0;.8;0" dur="{d}s" begin="{i * d / 6:.2f}s" repeatCount="indefinite"/></text>')

    # cable: monitor stand -> behind the desk -> out the bottom at CABLE_X
    sx, sy = X(112), Y(15) + 3
    path = f"M{sx:.0f},{sy:.0f} C{sx:.0f},{Y(18):.0f} {CABLE_X},{Y(17):.0f} {CABLE_X},{H}"
    pre.append(f'<path d="{path}" fill="none" stroke="{c["muted"]}" stroke-width="1.5" '
                   f'stroke-dasharray="1 4" stroke-linecap="round"/>')
    for i in range(5):                                 # the push travels down the cable
        a, b = 13.6 + i * 0.22, 14.9 + i * 0.22
        anim.append(f'<text dy="4" text-anchor="middle" fill="{c["bright"]}" opacity="0">{"+*:=+"[i]}'
                    f'<animateMotion {loop} path="{path}" keyPoints="0;0;1;1" keyTimes="0;{a / T:.4f};{b / T:.4f};1" calcMode="linear"/>'
                    f'<animate attributeName="opacity" {loop} {window(a, b)}/></text>')
    return cv, pre, anim


def panels(c, font_css, mono):
    rnd = random.Random(5)
    cv, pre, anim = scene(c, rnd)
    body = (f'<g font-family="{mono}" font-size="{FS}">' + "".join(pre)
            + cv.svg({"faint": c["faint"], "muted": c["muted"], "text": c["text"], "bright": c["bright"]})
            + "".join(anim) + "</g>")
    pw = W / PANELS
    out = []
    for i in range(PANELS):
        out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{pw:.0f}" height="{H}" '
                   f'viewBox="{i * pw:.0f} 0 {pw:.0f} {H}"><style>{font_css}</style>'
                   f'<rect x="{i * pw:.0f}" width="{pw:.0f}" height="{H}" fill="{c["bg"]}"/>{body}</svg>')
    return out
