#!/usr/bin/env python3
"""
generate_assets.py
Builds the SVG assets used by the GitHub profile README.

Brand rules applied here:
  - Carbon #0A0A0A background, Graphite #141414 grid, Steel #262626 borders
  - Bone #EDEDED text, Ash #8A8A8A muted text, Neon #39FF14 as the one accent
  - JetBrains Mono for all text (embedded as a tiny subset, so it renders
    the same on every device, even inside an <img> tag)
  - 4 px corners, 8 px-friendly spacing, no extra colors

Usage:
    pip install fonttools
    python generate_assets.py           # build the new assets
    python generate_assets.py --clean   # also delete the old, unused files

Output:
    assets/intro.svg
    assets/cards/<repo>.svg
    assets/banner.jpg   (renamed from assets/LinkedinGitHub_banner.jpg)
"""

import argparse
import base64
import io
import sys
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
CARDS = ASSETS / "cards"
FONT_CACHE = ROOT / ".cache" / "fonts"
FONT_URL = (
    "https://github.com/JetBrains/JetBrainsMono/raw/master/fonts/ttf/{name}.ttf"
)

# Old files from the first version of the profile (all inside assets/).
OLD_BANNER = "LinkedinGitHub_banner.jpg"
NEW_BANNER = "banner.jpg"
LEGACY_FILES = [
    "about-me-svg.svg",
    "intro-.svg",
    "intro.svg.svg",
    "SentinelRAG.svg",
    "ft_transcendence.svg",
    "inception.svg",
    "webserv.svg",
    "linkedin_banner (1) (1).jpg",
]

# ---------------------------------------------------------- brand tokens
CARBON = "#0A0A0A"
GRAPHITE = "#141414"
STEEL = "#262626"
ASH = "#8A8A8A"
BONE = "#EDEDED"
NEON = "#39FF14"

RADIUS = 4
CHAR_W = 0.6  # JetBrains Mono: every character is 0.6 em wide
MONO_STACK = (
    "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
)

# ------------------------------------------------------------------ content
HANDLE = "anasqabbal"

INTRO_TITLE = "Terminal bio of Anas Qabbal"
INTRO_DESC = (
    "Software engineer. Systems, backend, full-stack. "
    "Focus: Software Engineer, Full Stack, Systems, Applied AI, DevOps. "
    "Stack: C, C++, JavaScript, TypeScript, Next.js, NestJS, Python, MySQL, "
    "PostgreSQL, Bash. Status: building resilient low-level and distributed systems."
)

REPOS = [
    {
        "file": "sentinelrag.svg",
        "title": "SentinelRAG",
        "line1": "Local-first security intelligence + codebase",
        "line2": "vulnerability engine (FastAPI, Qdrant, Ollama)",
        "tags": "Python · RAG · Cybersecurity",
    },
    {
        "file": "ft-transcendence.svg",
        "title": "ft_transcendence",
        "line1": "Real-time multiplayer platform with TypeScript,",
        "line2": "WebSockets, ModSecurity WAF + HashiCorp Vault",
        "tags": "TypeScript · React · Security",
    },
    {
        "file": "webserv.svg",
        "title": "webserv",
        "line1": "Non-blocking HTTP/1.1 web server built from",
        "line2": "scratch in C++98 with select() I/O multiplexing",
        "tags": "C++98 · HTTP/1.1 · Systems",
    },
    {
        "file": "inception.svg",
        "title": "inception",
        "line1": "Multi-container Docker infrastructure on custom",
        "line2": "Alpine Linux images (Nginx, WordPress, MariaDB)",
        "tags": "Docker · Alpine · DevOps",
    },
]


# ------------------------------------------------------------ font helpers
def get_font_path(weight):
    """Return the local path of a JetBrains Mono file (download once)."""
    name = f"JetBrainsMono-{weight}"
    path = FONT_CACHE / f"{name}.ttf"
    if not path.exists():
        FONT_CACHE.mkdir(parents=True, exist_ok=True)
        try:
            urllib.request.urlretrieve(FONT_URL.format(name=name), path)
        except Exception as exc:  # network problem, offline, etc.
            print(f"warning: could not download {name}: {exc}", file=sys.stderr)
            return None
    return path


def subset_to_base64(path, chars):
    """Keep only the glyphs we use, return the font as a base64 string."""
    options = subset.Options()
    options.layout_features = []
    options.hinting = False
    options.notdef_outline = True
    options.name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14]  # keep license info
    font = TTFont(path)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(text="".join(sorted(chars)))
    subsetter.subset(font)
    buffer = io.BytesIO()
    font.save(buffer)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def font_face_css(chars):
    """Build @font-face rules with embedded subsets (400 and 700)."""
    css = []
    for weight_name, weight in (("Regular", 400), ("Bold", 700)):
        path = get_font_path(weight_name)
        if path is None:
            return ""  # fall back to the system monospace stack
        data = subset_to_base64(path, chars)
        css.append(
            "@font-face {"
            " font-family: 'JetBrains Mono';"
            f" font-weight: {weight};"
            f" src: url(data:font/ttf;base64,{data}) format('truetype');"
            " }"
        )
    return "\n".join(css)


# ------------------------------------------------------------ svg helpers
def text_el(x, y, segments, size, max_x=None, label="", anchor=None):
    """
    One <text> line made of (text, css_class) segments.
    Returns (markup, plain_text). Warns if the line is too wide.
    """
    plain = "".join(s for s, _ in segments)
    if max_x is not None and anchor is None:
        needed = x + len(plain) * size * CHAR_W
        if needed > max_x:
            print(
                f"warning: '{label or plain[:30]}' is too wide "
                f"({needed:.0f}px > {max_x:.0f}px)",
                file=sys.stderr,
            )
    spans = "".join(
        f'<tspan class="{cls}">{escape(s)}</tspan>' if cls else escape(s)
        for s, cls in segments
    )
    extra = f' text-anchor="{anchor}"' if anchor else ""
    markup = f'<text x="{x}" y="{y}" font-size="{size}"{extra}>{spans}</text>'
    return markup, plain


def build_svg(width, height, grid, title, desc, body, chars):
    """Wrap the body in the shared brand frame: carbon, grid, steel border."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" role="img" aria-labelledby="title desc">
  <title id="title">{escape(title)}</title>
  <desc id="desc">{escape(desc)}</desc>
  <defs>
    <style>
{font_face_css(chars)}
      text {{ font-family: {MONO_STACK}; fill: {BONE}; }}
      .b {{ font-weight: 700; }}
      .n {{ fill: {NEON}; }}
      .a {{ fill: {ASH}; }}
      .e {{ fill: {BONE}; }}
      @keyframes blink {{ 0%, 49% {{ opacity: 1; }} 50%, 100% {{ opacity: 0; }} }}
      .cursor {{ animation: blink 1.1s steps(1) infinite; }}
      @media (prefers-reduced-motion: reduce) {{ .cursor {{ animation: none; }} }}
    </style>
    <pattern id="grid" width="{grid}" height="{grid}" patternUnits="userSpaceOnUse">
      <path d="M {grid} 0 L 0 0 0 {grid}" fill="none" stroke="{GRAPHITE}" stroke-width="1"/>
    </pattern>
    <filter id="glow" x="-100%" y="-100%" width="300%" height="300%">
      <feGaussianBlur stdDeviation="2.5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="{RADIUS}" fill="{CARBON}"/>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="{RADIUS}" fill="url(#grid)" stroke="{STEEL}" stroke-width="1"/>
{body}
</svg>
"""


# ------------------------------------------------------------ intro.svg
def build_intro():
    width, step, pad = 840, 24, 32
    limit = width - pad  # right margin
    prompt = f"~/{HANDLE} $ "
    chars, lines = set(" "), []

    def add(x, y, segments, size=15, anchor=None, label=""):
        markup, plain = text_el(x, y, segments, size, limit, label, anchor)
        chars.update(plain)
        lines.append("  " + markup)

    # window bar: one neon status dot, two quiet Steel dots
    bar = [
        f'  <circle cx="28" cy="24" r="5" fill="{NEON}"/>',
        f'  <circle cx="48" cy="24" r="5" fill="{STEEL}"/>',
        f'  <circle cx="68" cy="24" r="5" fill="{STEEL}"/>',
        f'  <line x1="1" y1="44" x2="{width - 1}" y2="44" stroke="{STEEL}" stroke-width="1"/>',
    ]
    add(width - 20, 28, [("bash", "a")], size=12, anchor="end")

    y = 76
    add(pad, y, [(prompt + "whoami", "n b")], label="prompt 1")
    y += step
    add(pad, y, [("> software engineer. systems, backend, full-stack.", "")], label="bio")

    y += step + 12
    add(pad, y, [(prompt + "cat profile.json", "n b")], label="prompt 2")
    y += step
    add(pad, y, [("{", "")])
    y += step
    add(
        pad + 24, y,
        [('"focus": ', "a"),
         ('["Software Engineer", "Full Stack", "Systems", "Applied AI", "DevOps"],', "e")],
        label="focus",
    )
    y += step
    add(
        pad + 24, y,
        [('"stack": ', "a"),
         ('["C", "C++", "JavaScript", "TypeScript", "Next.js",', "e")],
        label="stack 1",
    )
    y += step
    add(
        pad + 24 + 10 * 15 * CHAR_W, y,
        [('"NestJS", "Python", "MySQL", "PostgreSQL", "Bash"],', "e")],
        label="stack 2",
    )
    y += step
    add(
        pad + 24, y,
        [('"status": ', "a"),
         ('"Building resilient low-level + distributed systems"', "n")],
        label="status",
    )
    y += step
    add(pad, y, [("}", "")])

    y += step + 12
    add(pad, y, [(prompt, "n b")], label="prompt 3")
    cursor_x = pad + len(prompt) * 15 * CHAR_W
    cursor = (
        f'  <rect class="cursor" x="{cursor_x:.1f}" y="{y - 12}" width="9" height="16" '
        f'fill="{NEON}" filter="url(#glow)"/>'
    )

    height = y + 28
    body = "\n".join(bar + lines + [cursor])
    return build_svg(width, height, 30, INTRO_TITLE, INTRO_DESC, body, chars)


# ------------------------------------------------------------ repo cards
def build_card(repo, index, total):
    width, height, pad = 420, 132, 20
    limit = width - 24
    chars, lines = set(" "), []

    def add(x, y, segments, size, anchor=None, label=""):
        markup, plain = text_el(x, y, segments, size, limit, label, anchor)
        chars.update(plain)
        lines.append("  " + markup)

    add(pad, 34, [("> " + repo["title"], "n b")], 16, label=repo["title"])
    add(width - pad, 34, [(f"{index:02d} / {total:02d}", "a")], 12, anchor="end")
    add(pad, 62, [(repo["line1"], "")], 13, label=repo["title"] + " line 1")
    add(pad, 82, [(repo["line2"], "")], 13, label=repo["title"] + " line 2")
    lines.append(f'  <circle cx="{pad + 5}" cy="108" r="4" fill="{NEON}"/>')
    add(pad + 16, 112, [(repo["tags"], "a")], 12, label=repo["title"] + " tags")

    title = f"{repo['title']} project card"
    desc = f"{repo['line1']} {repo['line2']}. {repo['tags']}."
    return build_svg(width, height, 24, title, desc, "\n".join(lines), chars)


# ------------------------------------------------------------------- tidy
def tidy_assets(clean):
    """Rename the banner. Delete old files only when --clean is given."""
    old, new = ASSETS / OLD_BANNER, ASSETS / NEW_BANNER
    if old.exists() and not new.exists():
        old.rename(new)
        print(f"Renamed assets/{OLD_BANNER} -> assets/{NEW_BANNER}")

    found = [name for name in LEGACY_FILES if (ASSETS / name).exists()]
    if not found:
        return
    if clean:
        for name in found:
            (ASSETS / name).unlink()
            print(f"Deleted assets/{name}")
    else:
        print("\nOld files still in assets/ (no longer used by the README):")
        for name in found:
            print(f"  - {name}")
        print("Run 'python generate_assets.py --clean' to delete them.")


# ------------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(description="Build the profile SVG assets.")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="delete the old files listed in LEGACY_FILES",
    )
    args = parser.parse_args()

    ASSETS.mkdir(exist_ok=True)
    CARDS.mkdir(parents=True, exist_ok=True)

    (ASSETS / "intro.svg").write_text(build_intro(), encoding="utf-8")

    total = len(REPOS)
    for i, repo in enumerate(REPOS, start=1):
        svg = build_card(repo, i, total)
        (CARDS / repo["file"]).write_text(svg, encoding="utf-8")

    print(f"Generated assets/intro.svg and {total} cards in assets/cards/")
    tidy_assets(args.clean)


if __name__ == "__main__":
    main()
