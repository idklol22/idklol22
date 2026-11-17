"""ASCII swarm that gathers into a rotating orb (after the OpenFolie site's orb).

Every glyph is its own particle. Each loop: the glyphs drift in flocks (each
particle trails a leader, like the site's drift mode), stream together into a
sphere that turns slowly with perspective and depth shading, hold, then break
apart into flocks again.

Positions are a pure function of time with periodic paths, so the loop is
seamless. They are sampled at KEY_FPS and the browser interpolates between
samples, so it plays at the display's frame rate.
"""

import math
import random

T = 16.0                                             # loop length (s)
GATHER_END, HOLD_END, RELEASE_END = 2.8, 10.0, 12.4  # drift runs RELEASE_END -> T, then wraps
KEY_FPS = 4
TAU = math.pi * 2
N = 460
GLYPHS = "+*:.#=-"
TILT = -0.38                                         # orb tilt, like the site's globe


def ease(p):
    p = min(1.0, max(0.0, p))
    return p * p * (3 - 2 * p)


class Orb:
    def __init__(self, width, height, seed=7):
        rnd = random.Random(seed)
        self.width, self.height = width, height
        self.r = min(width, height) * 0.4
        g = math.pi * (3 - math.sqrt(5))
        self.parts = []
        for i in range(N):
            y = 1 - 2 * (i + 0.5) / N
            rr = math.sqrt(1 - y * y)
            self.parts.append(dict(
                sx=math.cos(g * i) * rr, sy=y, sz=math.sin(g * i) * rr,   # home on the unit sphere
                g=rnd.choice(GLYPHS),
                lead=rnd.randrange(9), ox=rnd.gauss(0, 12), oy=rnd.gauss(0, 7),
                lag=rnd.uniform(0, 1.4), orb=rnd.uniform(3, 8), ph=rnd.random() * TAU,
                jit=rnd.random(),
            ))
        self.leaders = [dict(phx=rnd.random() * TAU, phy=rnd.random() * TAU,
                             mx=rnd.choice([1, 2]), my=rnd.choice([1, 2, 3])) for _ in range(9)]

    # ── motion ──
    def sphere(self, p, t):
        """Screen position + depth brightness of p's spot on the turning orb."""
        a = TAU * t / T                                   # one turn per loop -> periodic
        x, y, z = p["sx"], p["sy"], p["sz"]
        x, z = x * math.cos(a) + z * math.sin(a), -x * math.sin(a) + z * math.cos(a)
        y, z = y * math.cos(TILT) - z * math.sin(TILT), y * math.sin(TILT) + z * math.cos(TILT)
        s = 2.6 / (2.6 + z)
        b = 0.18 + 0.82 * (1 - z) / 2                     # near = 1, far = 0.18
        return self.width / 2 + x * self.r * s, self.height / 2 + y * self.r * s, b

    def drift(self, p, t):
        L = self.leaders[p["lead"]]
        u = TAU * (t - p["lag"]) / T
        x = self.width * (0.5 + 0.4 * math.sin(L["mx"] * u + L["phx"]))
        y = self.height * (0.5 + 0.38 * math.sin(L["my"] * u + L["phy"]))
        o = TAU * 4 * t / T + p["ph"]
        return x + p["ox"] + p["orb"] * math.cos(o), y + p["oy"] + p["orb"] * math.sin(o)

    def settle(self, p, t):
        """0 = flying with the flock, 1 = part of the orb."""
        if t < GATHER_END:                                # streams in, top of the orb first
            start = (1 - p["sy"]) / 2 * 1.4 + p["jit"] * 0.4
            return ease((t - start) / 1.0)
        if t < HOLD_END:
            return 1.0
        if t < RELEASE_END:                               # peels off, bottom first
            start = HOLD_END + (1 + p["sy"]) / 2 * 1.2 + p["jit"] * 0.3
            return 1 - ease((t - start) / 0.9)
        return 0.0

    def state(self, p, t):
        k = self.settle(p, t)
        ox, oy, b = self.sphere(p, t)
        if k >= 1:
            return ox, oy, b
        dx, dy = self.drift(p, t)
        return dx + (ox - dx) * k, dy + (oy - dy) * k, 0.7 + (b - 0.7) * k

    # ── svg ──
    def svg(self, x, y, fill, font, size):
        n = round(T * KEY_FPS)
        times = [i * T / n for i in range(n)] + [T]
        out = [f'<svg x="{x:.1f}" y="{y:.1f}" width="{self.width:.0f}" height="{self.height:.0f}" overflow="hidden">'
               f'<g font-family="{font}" font-size="{size}" text-anchor="middle" fill="{fill}">']
        for p in self.parts:
            st = [self.state(p, t) for t in times]
            pos = ";".join(f"{a:.0f} {b:.0f}" for a, b, _ in st)
            op = ";".join(f"{c:.2f}".lstrip("0") for _, _, c in st)
            a0, b0, c0 = self.state(p, 5.0)               # static fallback: the orb mid-hold
            out.append(f'<text transform="translate({a0:.0f} {b0:.0f})" opacity="{c0:.2f}">{p["g"]}'
                       f'<animateTransform attributeName="transform" type="translate" dur="{T}s" '
                       f'repeatCount="indefinite" values="{pos}"/>'
                       f'<animate attributeName="opacity" dur="{T}s" repeatCount="indefinite" values="{op}"/></text>')
        out.append("</g></svg>")
        return "".join(out)
