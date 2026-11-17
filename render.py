"""Render the profile card SVGs.

    python render.py            # live data (needs GITHUB_TOKEN in env)
    python render.py --demo     # fake stats, no token needed

Writes three layers, each in dark + light (README swaps them with GitHub's theme):
    cards/banner-{1,2,3}-*.svg  cozy ascii scene, split into side-by-side panels
    cards/hero-*.svg            name, details, the ascii orb
    cards/contrib-*.svg         github-style contribution grid

The layers are joined by one cable at banner.CABLE_X: code typed on the banner's
monitor is pushed down it, pours into the orb, drains out, and lights up today's
square in the contribution grid. Everything runs on the same 16 s loop.
"""

import base64
import datetime as dt
import json
import os
import random
import sys
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

import banner
import orb

ROOT = Path(__file__).parent
OUT = ROOT / "cards"

# ── openfolie tokens ─────────────────────────────────────────────────────
MODES = {
    "dark": dict(bg="#0a0a0a", text="#b8b8b8", strong="#f5f5f5", muted="#6f6f6f", line="#222222", art="#f5f5f5",
                 bright="#f5f5f5", faint="#2e2e2e", glow="#ffffff",
                 cells=["#161616", "#2e2e2e", "#575757", "#9c9c9c", "#f5f5f5"]),
    "light": dict(bg="#fafaf9", text="#3a3a3a", strong="#0a0a0a", muted="#8a8a8a", line="#e4e4e2", art="#0a0a0a",
                  bright="#0a0a0a", faint="#d4d4d1", glow="#9a9a96",
                  cells=["#ebebe9", "#cdcdca", "#999996", "#5a5a58", "#0a0a0a"]),
}

W, PAD = 960, 40
SANS = "G,'Geist',system-ui,-apple-system,'Segoe UI',sans-serif"
MONO = "GM,'Geist Mono',ui-monospace,Consolas,Menlo,monospace"

ORB_W, ORB_H = 340, 300            # the swarm's box (top right)
GLYPH = 11                         # glyph size in the swarm


# ── data ─────────────────────────────────────────────────────────────────
QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC) { totalCount }
    contributionsCollection {
      totalCommitContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date } }
      }
    }
  }
}"""


def fetch_stats(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-card"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(f"GraphQL error: {body['errors']}")
    u = body["data"]["user"]
    cc = u["contributionsCollection"]
    weeks = cc["contributionCalendar"]["weeks"]
    return {
        "created": dt.date.fromisoformat(u["createdAt"][:10]),
        "repos": u["repositories"]["totalCount"],
        "commits": cc["totalCommitContributions"],
        "total": cc["contributionCalendar"]["totalContributions"],
        "weeks": [[d["contributionCount"] for d in w["contributionDays"]] for w in weeks],
        "starts": [dt.date.fromisoformat(w["contributionDays"][0]["date"]) for w in weeks],
        "first_weekday": dt.date.fromisoformat(weeks[0]["contributionDays"][0]["date"]).isoweekday() % 7,
    }


def demo_stats():
    rnd = random.Random(22)
    weeks = []
    for _ in range(53):
        burst = rnd.random() < 0.35
        weeks.append([rnd.choice([0, 0, 0, 1, 2, 3, 5, 8]) if burst or rnd.random() < 0.25 else 0
                      for _ in range(7)])
    today = dt.date.today()
    sunday = today - dt.timedelta(days=today.isoweekday() % 7)
    starts = [sunday - dt.timedelta(weeks=52 - i) for i in range(53)]
    return {"created": dt.date(2022, 3, 14), "repos": 18, "commits": 412,
            "total": sum(map(sum, weeks)), "weeks": weeks, "starts": starts, "first_weekday": 0}


# ── svg helpers ──────────────────────────────────────────────────────────
def font_css(families=("G", "GM")):
    css = []
    for fam, file in (("G", "geist-latin.woff2"), ("GM", "geist-mono-latin.woff2")):
        if fam not in families:
            continue
        p = ROOT / "fonts" / file
        if p.exists():
            b64 = base64.b64encode(p.read_bytes()).decode()
            css.append(f"@font-face{{font-family:{fam};src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    return "".join(css)


def txt(x, y, s, fill, size, family=SANS, weight=None, anchor=None, upper=False):
    a = f'x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" font-family="{family}"'
    if weight:
        a += f' font-weight="{weight}"'
    if anchor:
        a += f' text-anchor="{anchor}"'
    if upper:
        a += ' letter-spacing="0.5"'
        s = s.upper()
    return f"<text {a}>{escape(s)}</text>"


def label(x, y, s, c, anchor=None, size=11):
    return txt(x, y, s, c["muted"], size, MONO, anchor=anchor, upper=True)


def hline(x1, x2, y, c):
    return f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" stroke="{c["line"]}"/>'


def span(d1, d2):
    y, m = d2.year - d1.year, d2.month - d1.month
    if d2.day < d1.day:
        m -= 1
    if m < 0:
        y, m = y - 1, m + 12
    return f"{y}y {m}m"


# ── render ───────────────────────────────────────────────────────────────
def contrib_grid(s, x, y, c):
    """GitHub's layout: weeks as columns, Sun..Sat as rows, months on top."""
    o = []
    weeks, starts = s["weeks"][-53:], s["starts"][-53:]
    lx, gap = 30, 3
    pitch = (W - PAD - x - lx + gap) / len(weeks)
    cell = pitch - gap
    gx, gy = x + lx, y + 16
    prev = None
    for w, d in enumerate(starts):
        if d.month != prev and w < len(weeks) - 2:
            o.append(txt(gx + w * pitch, y + 6, d.strftime("%b"), c["muted"], 10, MONO))
        prev = d.month
    for r, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        o.append(txt(x, gy + r * pitch + cell - 2, name, c["muted"], 10, MONO))
    nz = sorted(n for wk in weeks for n in wk if n)
    q = [nz[int(len(nz) * f)] for f in (0.25, 0.5, 0.75)] if nz else [1, 2, 3]
    for w, wk in enumerate(weeks):
        off = s.get("first_weekday", 0) if w == 0 else 0
        for d, n in enumerate(wk):
            lvl = 0 if n == 0 else 1 + sum(n > b for b in q)
            o.append(f'<rect x="{gx + w * pitch:.1f}" y="{gy + (d + off) * pitch:.1f}" width="{cell:.1f}" '
                     f'height="{cell:.1f}" rx="2" fill="{c["cells"][lvl]}"/>')
    lw = len(weeks) - 1
    today = (gx + lw * pitch, gy + (len(weeks[-1]) - 1 + (s.get("first_weekday", 0) if lw == 0 else 0)) * pitch, cell)
    by = gy + 7 * pitch + 14
    o.append(txt(gx, by + 9, f"{s['total']:,} contributions in the last year  ·  updated {dt.date.today().isoformat()}",
                 c["muted"], 11, MONO))
    lx2 = W - PAD - 5 * 13 - 34
    o.append(txt(lx2 - 8, by + 9, "Less", c["muted"], 10, MONO, anchor="end"))
    for i, col in enumerate(c["cells"]):
        o.append(f'<rect x="{lx2 + i * 13}" y="{by}" width="10" height="10" rx="2" fill="{col}"/>')
    o.append(txt(lx2 + 5 * 13 + 4, by + 9, "More", c["muted"], 10, MONO))
    return "".join(o), by + 10, today


def page(o, H, c, fonts):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f'<style>{fonts}</style><rect width="{W}" height="{H}" fill="{c["bg"]}"/>'
            + "".join(o) + "</svg>")


def section_head(o, title, note, c, y=40):
    o.append(f'<rect x="{PAD}" y="{y - 8}" width="7" height="7" fill="{c["strong"]}"/>')
    o.append(txt(PAD + 16, y, title, c["strong"], 11, MONO, upper=True))
    if note:
        o.append(label(W - PAD, y, note, c, anchor="end"))
    o.append(hline(PAD, W - PAD, y + 21, c))


def render_hero(cfg, s, swarm, c, fonts):
    today = dt.date.today()
    o = []
    section_head(o, cfg["user"], None, c, 43)

    colr = W - PAD - ORB_W - 24
    o.append(txt(PAD, 124, cfg.get("name") or cfg["user"], c["strong"], 34, weight=600))
    if cfg.get("tagline"):
        o.append(txt(PAD, 158, cfg["tagline"], c["text"], 16))
    y = 192
    rows = list(cfg.get("rows", [])) + [["on github", span(s["created"], today)]]
    for k, v in rows:
        o.append(hline(PAD, colr, y, c))
        y += 24
        o.append(label(PAD, y, k, c))
        o.append(txt(PAD + 104, y + 0.5, str(v), c["text"], 15))
        y += 13
    o.append(hline(PAD, colr, y, c))
    y += 36
    stats = [("repos", s["repos"]), ("commits this year", s["commits"])]
    colw = (colr - PAD) / len(stats)
    for i, (k, v) in enumerate(stats):
        o.append(label(PAD + i * colw, y, k, c))
        o.append(txt(PAD + i * colw, y + 36, f"{v:,}", c["strong"], 30, weight=500))

    H = round(max(y + 36, 76 + ORB_H) + 28)
    cx = banner.CABLE_X
    for y1, y2 in ((0, 84), (76 + ORB_H - 14, H)):          # cable in from the banner, out to the grid
        o.append(f'<line x1="{cx}" y1="{y1}" x2="{cx}" y2="{y2}" stroke="{c["muted"]}" stroke-width="1.5" '
                 f'stroke-dasharray="1 4" stroke-linecap="round"/>')
    o.append(swarm.svg(W - PAD - ORB_W, 76, c["art"], MONO, GLYPH))
    return page(o, H, c, fonts)


def render_contrib(s, c, fonts):
    o = []
    section_head(o, "contributions", None, c)
    grid, y, (tx, ty, cell) = contrib_grid(s, PAD, 92, c)
    o.append(grid)

    # the cable arrives from the orb and lands on today's square
    cx, hy = banner.CABLE_X, 76
    xr, my = tx + cell + 9, ty + cell / 2                   # run down the grid's right edge, enter from the side
    path = f"M{cx},0 L{cx},{hy} L{xr:.1f},{hy} L{xr:.1f},{my:.1f} L{tx + cell + 2:.1f},{my:.1f}"
    o.append(f'<path d="{path}" fill="none" stroke="{c["muted"]}" stroke-width="1.5" stroke-dasharray="1 4" '
             f'stroke-linecap="round"/>')
    T = orb.T
    loop = f'dur="{T}s" repeatCount="indefinite"'
    for i in range(5):                       # the orb drains at the end of the loop -> arrives here at its start
        a, b = 0.1 + i * 0.2, 1.1 + i * 0.2
        o.append(f'<text dy="4" text-anchor="middle" font-family="{MONO}" font-size="11" fill="{c["art"]}" opacity="0">'
                 f'{"+*:=+"[i]}<animateMotion {loop} path="{path}" keyPoints="0;0;1;1" '
                 f'keyTimes="0;{a / T:.4f};{b / T:.4f};1" calcMode="linear"/>'
                 f'<animate attributeName="opacity" {loop} values="0;1;0" keyTimes="0;{a / T:.4f};{b / T:.4f}" '
                 f'calcMode="discrete"/></text>')
    o.append(f'<rect x="{tx - 2:.1f}" y="{ty - 2:.1f}" width="{cell + 4:.1f}" height="{cell + 4:.1f}" rx="3" '
             f'fill="none" stroke="{c["strong"]}" opacity="0"><animate attributeName="opacity" {loop} '
             f'values="0;1;.35;0" keyTimes="0;{1.9 / T:.4f};{4 / T:.4f};{7 / T:.4f}"/></rect>')
    return page(o, round(y + 30), c, fonts)


def main():
    cfg = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("ACCESS_TOKEN")
    if "--demo" in sys.argv or not token:
        print("demo data (set GITHUB_TOKEN for live stats)", file=sys.stderr)
        stats = demo_stats()
    else:
        stats = fetch_stats(cfg["user"], token)
    hero_h = 404                                            # approx; only used for the orb's exit point
    ox = banner.CABLE_X - (W - PAD - ORB_W)
    swarm = orb.Orb(ORB_W, ORB_H, entry=(ox, -76), exit=(ox, hero_h - 76))
    fonts, mono_only = font_css(), font_css(("GM",))
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.svg"):
        old.unlink()
    for mode, colors in MODES.items():
        for i, panel in enumerate(banner.panels(colors, mono_only, MONO), 1):
            (OUT / f"banner-{i}-{mode}.svg").write_text(panel, encoding="utf-8")
        (OUT / f"hero-{mode}.svg").write_text(render_hero(cfg, stats, swarm, colors, fonts), encoding="utf-8")
        (OUT / f"contrib-{mode}.svg").write_text(render_contrib(stats, colors, fonts), encoding="utf-8")
    print("wrote cards/: banner-1..3, hero, contrib")

if __name__ == "__main__":
    main()
