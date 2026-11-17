"""Render the profile card SVGs.

    python render.py            # live data (needs GITHUB_TOKEN in env)
    python render.py --demo     # fake stats, no token needed

Writes two layers, each in dark + light (README swaps them with GitHub's theme):
    cards/banner-{1,2,3}-*.svg  cozy ascii scene, split into side-by-side panels
    cards/hero-*.svg            name + details; the room continues under the desk

The ascii room carries on downward: the banner's desk legs, drawer and monitor
cable continue into the main card (pedestal, pc, power strip, guitar, floor).
Fonts come from FONT_SETS, picked by "fonts" in profile.json.
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
                 bright="#eef2f7", faint="#1f2835", glow="#cfe0ff"),
    "light": dict(bg="#eef1f5", text="#334155", strong="#0f172a", muted="#7b8799", line="#d5dbe3", art="#0f172a",
                  bright="#0f172a", faint="#cfd6df", glow="#7b8aa3"),
}

W, PAD = 960, 40

# ── fonts ────────────────────────────────────────────────────────────────
# text: name, tagline, values. label: small caps labels. art: the ascii scene
# (must have a 0.6em advance so it lands on the banner's character grid).
FONT_SETS = {
    "grotesk": dict(
        text=("Space Grotesk", [("space-grotesk-latin-400-normal.woff2", 400, "normal"),
                                ("space-grotesk-latin-500-normal.woff2", 500, "normal")]),
        label=("Space Mono", [("space-mono-latin-400-normal.woff2", 400, "normal")]),
        art=("Fira Mono", [("fira-mono-latin-400-normal.woff2", 400, "normal")]),
        name_weight=500, italic=False, label_size=11),
}


class Fonts:
    def __init__(self, key):
        fs = FONT_SETS[key]
        self.cfg = fs
        self.text = f"FT,'{fs['text'][0]}',system-ui,'Segoe UI',sans-serif"
        self.label = f"FL,'{fs['label'][0]}',ui-monospace,Consolas,monospace"
        self.art = f"FA,'{fs['art'][0]}',ui-monospace,Consolas,monospace"
        self._sets = {"FT": fs["text"][1], "FL": fs["label"][1], "FA": fs["art"][1]}

    def css(self, which=("FT", "FL", "FA")):
        out = []
        for fam in which:
            for file, weight, style in self._sets[fam]:
                path = ROOT / "fonts" / file
                if path.exists():
                    b64 = base64.b64encode(path.read_bytes()).decode()
                    out.append(f"@font-face{{font-family:{fam};font-weight:{weight};font-style:{style};"
                               f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")
        # ascii art needs every glyph separate, never a ligature
        out.append("text{font-variant-ligatures:none;font-feature-settings:'liga' 0,'calt' 0}")
        return "".join(out)


# ── data ─────────────────────────────────────────────────────────────────
QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC) { totalCount }
    contributionsCollection { totalCommitContributions }
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
    return {
        "created": dt.date.fromisoformat(u["createdAt"][:10]),
        "repos": u["repositories"]["totalCount"],
        "commits": u["contributionsCollection"]["totalCommitContributions"],
    }


def demo_stats():
    return {"created": dt.date(2022, 3, 14), "repos": 18, "commits": 412}


# ── svg helpers ──────────────────────────────────────────────────────────
def txt(x, y, s, fill, size, family, weight=None, anchor=None, upper=False, italic=False):
    a = f'x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" font-family="{family}"'
    if weight:
        a += f' font-weight="{weight}"'
    if anchor:
        a += f' text-anchor="{anchor}"'
    if italic:
        a += ' font-style="italic"'
    if upper:
        a += ' letter-spacing="0.6"'
        s = s.upper()
    return f"<text {a}>{escape(s)}</text>"


def hline(x1, x2, y, c):
    return f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" stroke="{c["line"]}"/>'


def span(d1, d2):
    y, m = d2.year - d1.year, d2.month - d1.month
    if d2.day < d1.day:
        m -= 1
    if m < 0:
        y, m = y - 1, m + 12
    return f"{y}y {m}m"


def page(o, H, c, css):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f'<style>{css}</style><rect width="{W}" height="{H}" fill="{c["bg"]}"/>'
            + "".join(o) + "</svg>")


# ── the room under the desk ──────────────────────────────────────────────
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

    # hanging under the desk top
    block(0, 104, ["  _|_", " /   \\", "|     |", "[]   []"], "text")        # headphones on a hook
    block(0, 116, [")", "(", " )", " o"], "faint")                          # mouse cable dangling off the edge
    block(0, 137, [".----------------.", "|     [ __ ]     |", "|----------------|",
                   "|     [ __ ]     |", "|----------------|", "|     [ __ ]     |",
                   "'----------------'"], "muted")                         # drawer pedestal

    # pinned to the back wall, in the shade under the desk
    block(8, 104, [".--------.", "| todo:  |", "| - ship |", "| - sleep|", "'--------'"],
          lambda i: "muted" if i in (0, 4) else "text")                    # sticky note
    block(10, 116, [".--o---.", "|  /\\  |", "| /  \\ |", "|/____\\|", "'------'"], "muted")   # pinned photo
    block(8, 139, ["   _||_", "  /    \\", " /|    |\\", "/_|    |_\\", "  |    |", "  |____|"],
          lambda i: "muted" if i < 2 else "faint")                          # hoodie on the pedestal knob

    # monitor cable drops to the power strip
    cc = banner.CABLE_COL
    for r in range(0, floor - 3):
        cv.put(r, cc, ":", "faint")
    cv.put(floor - 3, cc, "|", "muted")
    cv.put(floor - 2, cc - 6, ".-----'-----.", "muted")
    cv.put(floor - 1, cc - 6, "[o o  o o  o]", "text")

    # on the floor
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

    rnd = random.Random(9)                                                  # dust + shadow, empty cells only
    for r in range(3, floor):
        for k in range(101, 155):
            if cv.g[r][k][1] is None and rnd.random() < 0.035:
                cv.put(r, k, rnd.choice(".'`,"), "faint")
    return cv.svg({"faint": c["faint"], "muted": c["muted"], "text": c["text"]})


def render_hero(cfg, s, c, f):
    today = dt.date.today()
    fs = f.cfg
    ls = fs["label_size"]

    def label(x, y, t):
        return txt(x, y, t, c["muted"], ls, f.label, upper=True)

    o = []
    o.append(f'<rect x="{PAD}" y="35" width="7" height="7" fill="{c["strong"]}"/>')
    o.append(txt(PAD + 16, 43, "about", c["strong"], ls, f.label, upper=True))
    o.append(hline(PAD, W - PAD, 64, c))

    colr = 600
    o.append(txt(PAD, 122, cfg.get("name") or cfg["user"], c["strong"], 40, f.text, weight=fs["name_weight"]))
    if cfg.get("tagline"):
        o.append(txt(PAD, 154, cfg["tagline"], c["text"], 17, f.text, italic=fs["italic"]))
    y = 182
    rows = list(cfg.get("rows", [])) + [["on github", span(s["created"], today)]]
    for k, v in rows:
        o.append(hline(PAD, colr, y, c))
        y += 24
        o.append(label(PAD, y, k))
        o.append(txt(PAD + 110, y + 0.5, str(v), c["text"], 16, f.text))
        y += 13
    o.append(hline(PAD, colr, y, c))
    y += 34
    stats = [("repos", s["repos"]), ("commits this year", s["commits"])]
    colw = (colr - PAD) / len(stats)
    for i, (k, v) in enumerate(stats):
        o.append(label(PAD + i * colw, y, k))
        o.append(txt(PAD + i * colw, y + 36, f"{v:,}", c["strong"], 34, f.text, weight=fs["name_weight"]))
    H = round(y + 34 + 30)

    o.insert(0, f'<g font-family="{f.art}" font-size="{banner.FS}">{under_desk(c, H)}</g>')
    return page(o, H, c, f.css())


def render_all(cfg, stats, out_dir, font_key):
    f = Fonts(font_key)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.svg"):
        old.unlink()
    for mode, colors in MODES.items():
        for i, panel in enumerate(banner.panels(colors, f.css(("FA",)), f.art), 1):
            (out_dir / f"banner-{i}-{mode}.svg").write_text(panel, encoding="utf-8")
        (out_dir / f"hero-{mode}.svg").write_text(render_hero(cfg, stats, colors, f), encoding="utf-8")


def main():
    cfg = json.loads((ROOT / "profile.json").read_text(encoding="utf-8"))
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("ACCESS_TOKEN")
    if "--demo" in sys.argv or not token:
        print("demo data (set GITHUB_TOKEN for live stats)", file=sys.stderr)
        stats = demo_stats()
    else:
        stats = fetch_stats(cfg["user"], token)
    key = cfg.get("fonts", "grotesk")
    render_all(cfg, stats, OUT, key)
    print(f"wrote cards/: banner-1..3, hero ({key} fonts)")


if __name__ == "__main__":
    main()
