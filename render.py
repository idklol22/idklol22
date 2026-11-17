"""Render the profile card SVGs.

    python render.py            # live data (needs GITHUB_TOKEN in env)
    python render.py --demo     # fake stats, no token needed

Writes three layers, each in dark + light (README swaps them with GitHub's theme):
    cards/banner-{1,2,3}-*.svg  cozy ascii scene, split into side-by-side panels
    cards/hero-*.svg            name + details; the room continues under the desk
    cards/contrib-*.svg         github-style contribution grid

The ascii room carries on downward: the banner's desk legs, drawer and monitor
cable continue into the main card (backpack, power strip, plant, shoes, floor),
and the floor runs on as faint boards at the top of the contribution grid.
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

ROOT = Path(__file__).parent
OUT = ROOT / "cards"

# ── slate palette (openfolie layout, dark slate blue / light slate) ──────
MODES = {
    "dark": dict(bg="#0a0e14", text="#aab5c4", strong="#eef2f7", muted="#5f6d82", line="#1a2230", art="#eef2f7",
                 bright="#eef2f7", faint="#1f2835", glow="#cfe0ff",
                 cells=["#121821", "#22304a", "#3c5070", "#7189b0", "#d6e1f2"]),
    "light": dict(bg="#eef1f5", text="#334155", strong="#0f172a", muted="#7b8799", line="#d5dbe3", art="#0f172a",
                  bright="#0f172a", faint="#cfd6df", glow="#7b8aa3",
                  cells=["#dde3ea", "#b7c3d3", "#8395ae", "#4b5d78", "#1e293b"]),
}

W, PAD = 960, 40
SERIF = "S,'Instrument Serif',Georgia,'Times New Roman',serif"
MONO = "GM,'JetBrains Mono',ui-monospace,Consolas,Menlo,monospace"   # 0.6em advance, same grid as before
FONTS = {
    "S": [("instrument-serif-latin-400-normal.woff2", 400, "normal"),
          ("instrument-serif-latin-400-italic.woff2", 400, "italic")],
    "GM": [("jetbrains-mono-latin-400-normal.woff2", 400, "normal"),
           ("jetbrains-mono-latin-500-normal.woff2", 500, "normal")],
}

LOOP = banner.T


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
def font_css(families=("S", "GM")):
    css = []
    for fam in families:
        for file, weight, style in FONTS[fam]:
            path = ROOT / "fonts" / file
            if path.exists():
                b64 = base64.b64encode(path.read_bytes()).decode()
                css.append(f"@font-face{{font-family:{fam};font-weight:{weight};font-style:{style};"
                           f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
    # JetBrains Mono ships code ligatures (==, ||, ->); ascii art needs every glyph separate
    css.append("text{font-variant-ligatures:none;font-feature-settings:'liga' 0,'calt' 0}")
    return "".join(css)


def txt(x, y, s, fill, size, family=SERIF, weight=None, anchor=None, upper=False, italic=False):
    a = f'x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" font-family="{family}"'
    if weight:
        a += f' font-weight="{weight}"'
    if anchor:
        a += f' text-anchor="{anchor}"'
    if italic:
        a += ' font-style="italic"'
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


def under_desk(c, H):
    """The room below the banner, on the banner's character grid.
    Row 0 sits right under the banner's last row."""
    LH = banner.LH
    top = banner.TOP + banner.ROWS * LH - banner.H              # continue the banner's row rhythm
    rows = int((H - top) / LH) + 1
    floor = rows - 1
    cv = banner.Canvas(rows=rows, cols=banner.COLS, top=top)
    for r in range(floor):                                   # desk legs keep going
        cv.put(r, 3, "|", "muted"); cv.put(r, 156, "|", "muted")
    cv.put(0, 8, "|                    |", "muted")            # drawer, bottom half
    cv.put(1, 8, "'--------------------'", "muted")
    cv.put(2, 3, "|____", "faint"); cv.put(2, 152, "____|", "faint")   # desk frame rail
    cv.put(floor, 0, "_" * banner.COLS, "muted")             # the floor

    def block(r0, c0, lines, tone):
        for i, l in enumerate(lines):
            cv.put(r0 + i, c0, l, tone(i) if callable(tone) else tone)

    # ── hanging under the desk top ──
    block(0, 104, ["  _|_", " /   \\", "|     |", "[]   []"], "text")        # headphones on a hook
    block(0, 116, [")", "(", " )", " o"], "faint")                          # mouse cable dangling off the edge
    block(0, 137, [".----------------.", "|     [ __ ]     |", "|----------------|",
                   "|     [ __ ]     |", "|----------------|", "|     [ __ ]     |",
                   "'----------------'"], "muted")                         # drawer pedestal

    # ── pinned to the back wall, in the shade under the desk ──
    block(8, 104, [".--------.", "| todo:  |", "| - ship |", "| - sleep|", "'--------'"],
          lambda i: "muted" if i in (0, 4) else "text")                    # sticky note
    block(10, 116, [".--o---.", "|  /\\  |", "| /  \\ |", "|/____\\|", "'------'"], "muted")   # pinned photo
    block(8, 139, ["   _||_", "  /    \\", " /|    |\\", "/_|    |_\\", "  |    |", "  |____|"],
          lambda i: "muted" if i < 2 else "faint")                          # hoodie on the pedestal knob

    # ── monitor cable drops to the power strip ──
    cc = banner.CABLE_COL
    for r in range(0, floor - 3):
        cv.put(r, cc, ":", "faint")
    cv.put(floor - 3, cc, "|", "muted")
    cv.put(floor - 2, cc - 6, ".-----'-----.", "muted")
    cv.put(floor - 1, cc - 6, "[o o  o o  o]", "text")

    # ── on the floor ──
    block(floor - 9, 102, [".---------.", "| [=====] |", "| [=====] |", "| ::::::: |", "|  .---.  |",
                           "|  |(@)|  |", "|  '---'  |", "| o   ::: |", "'---------'"],
          lambda i: "text" if i in (0, 5, 7, 8) else "muted")               # pc tower
    cv.put(floor - 3, 113, "._", "faint")                                   # its power cable
    cv.put(floor - 2, 115, "\\_____", "faint")
    cv.put(floor - 1, 115, "@~~", "muted")                                  # the cat's yarn ball
    block(floor - 5, 134, ["   .--.", "  /    \\", " | [==] |", " |  __  |", " |_|__|_|"], "text")   # backpack
    block(floor - 12, 145, ["    _", "   |=|", "   |=|", "   | |", "   | |", "  _| |_", " /  .  \\",
                            "(  (o)  )", " \\  '  /", " / ___ \\", "(  \\_/  )", " '-----'"],
          lambda i: "muted" if i < 6 else "text")                           # guitar leaning on the leg

    # dust + shadow under the desk (only in empty cells)
    rnd = random.Random(9)
    for r in range(3, floor):
        for k in range(101, 155):
            if cv.g[r][k][1] is None and rnd.random() < 0.035:
                cv.put(r, k, rnd.choice(".'`,"), "faint")
    return cv.svg({"faint": c["faint"], "muted": c["muted"], "text": c["text"]})


def render_hero(cfg, s, c, fonts):
    today = dt.date.today()
    o = []
    section_head(o, "about", None, c, 43)

    colr = 600
    o.append(txt(PAD, 124, cfg.get("name") or cfg["user"], c["strong"], 48))
    if cfg.get("tagline"):
        o.append(txt(PAD, 156, cfg["tagline"], c["text"], 19, italic=True))
    y = 182
    rows = list(cfg.get("rows", [])) + [["on github", span(s["created"], today)]]
    for k, v in rows:
        o.append(hline(PAD, colr, y, c))
        y += 24
        o.append(label(PAD, y, k, c))
        o.append(txt(PAD + 110, y + 1, str(v), c["text"], 18))
        y += 13
    o.append(hline(PAD, colr, y, c))
    y += 34
    stats = [("repos", s["repos"]), ("commits this year", s["commits"])]
    colw = (colr - PAD) / len(stats)
    for i, (k, v) in enumerate(stats):
        o.append(label(PAD + i * colw, y, k, c))
        o.append(txt(PAD + i * colw, y + 38, f"{v:,}", c["strong"], 42))
    H = round(y + 34 + 30)

    o.insert(0, f'<g font-family="{MONO}" font-size="{banner.FS}">{under_desk(c, H)}</g>')
    return page(o, H, c, fonts)


def render_contrib(s, c, fonts):
    o = []
    boards = banner.Canvas(rows=2, cols=banner.COLS, top=banner.TOP)
    for r, (off, tone) in enumerate(((0, "faint"), (9, "faint"))):
        boards.put(r, 0, "".join("|" if (k + off) % 18 == 0 else "_" for k in range(banner.COLS)), tone)
    o.append(f'<g font-family="{MONO}" font-size="{banner.FS}" opacity=".7">'
             f'{boards.svg({"faint": c["faint"]})}</g>')
    section_head(o, "contributions", None, c, 52)
    grid, y, _ = contrib_grid(s, PAD, 104, c)
    o.append(grid)

    return page(o, round(y + 30), c, fonts)


def main():
    cfg = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("ACCESS_TOKEN")
    if "--demo" in sys.argv or not token:
        print("demo data (set GITHUB_TOKEN for live stats)", file=sys.stderr)
        stats = demo_stats()
    else:
        stats = fetch_stats(cfg["user"], token)
    fonts, mono_only = font_css(), font_css(("GM",))
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.svg"):
        old.unlink()
    for mode, colors in MODES.items():
        for i, panel in enumerate(banner.panels(colors, mono_only, MONO), 1):
            (OUT / f"banner-{i}-{mode}.svg").write_text(panel, encoding="utf-8")
        (OUT / f"hero-{mode}.svg").write_text(render_hero(cfg, stats, colors, fonts), encoding="utf-8")
        (OUT / f"contrib-{mode}.svg").write_text(render_contrib(stats, colors, fonts), encoding="utf-8")
    print("wrote cards/: banner-1..3, hero, contrib")

if __name__ == "__main__":
    main()
