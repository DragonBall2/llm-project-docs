"""Render demo.gif (not a test; needs Pillow and the Windows fonts under /mnt/c): three scenes, each a real hook output inside a scripted terminal.

Frames are emitted only when something changes, with per-frame durations, so the
GIF stays small. Hook text is verbatim from running the hooks on this repository
(pre-edit output has one long paragraph trimmed, marked with ...).
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import textwrap

W, H, PAD, LH = 960, 600, 22, 24
FONT = ImageFont.truetype("/mnt/c/Windows/Fonts/consola.ttf", 17)
BOLD = ImageFont.truetype("/mnt/c/Windows/Fonts/consolab.ttf", 17)
SYM = ImageFont.truetype("/mnt/c/Windows/Fonts/seguisym.ttf", 17)
COLS = 94

BG, FG, DIM = "#0d1117", "#e6edf3", "#8b949e"
GREEN, CYAN, YELLOW, ORANGE, PURPLE = "#3fb950", "#79c0ff", "#e3b341", "#f0883e", "#d2a8ff"

frames, durs = [], []


def wrap(text, indent=0):
    lines = []
    for raw in text.split("\n"):
        lead = len(raw) - len(raw.lstrip(" "))
        body = raw.strip()
        if not body:
            lines.append("")
            continue
        for i, l in enumerate(textwrap.wrap(body, COLS - lead - indent) or [""]):
            lines.append(" " * (lead + (0 if i == 0 else 4)) + l)
    return lines


def color_for(line):
    s = line.lstrip()
    if s.startswith("docs:"):
        return YELLOW
    if s.startswith("[["):
        return CYAN
    if s.startswith("⚠"):
        return ORANGE
    if s.startswith("$"):
        return GREEN
    if s.startswith("●"):
        return PURPLE
    if s.startswith(">"):
        return FG
    return DIM


def render(lines, cursor=False):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    # title bar
    d.rectangle([0, 0, W, 34], fill="#161b22")
    for i, c in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        d.ellipse([16 + i * 22, 11, 28 + i * 22, 23], fill=c)
    d.text((W // 2 - 60, 8), "claude — llm-project-docs", font=FONT, fill=DIM)
    y = 34 + PAD
    for line in lines[-((H - 34 - PAD * 2) // LH):]:
        x = PAD
        col = color_for(line)
        if "⚠" in line:
            pre, post = line.split("⚠", 1)
            d.text((x, y), pre, font=FONT, fill=col)
            x += d.textlength(pre, font=FONT)
            d.text((x, y - 1), "⚠", font=SYM, fill=col)
            x += 20
            d.text((x, y), post.lstrip("️ "), font=FONT, fill=col)
        elif line.lstrip().startswith("$") or line.lstrip().startswith("●"):
            head, rest = line.split(" ", 1) if " " in line else (line, "")
            d.text((x, y), head, font=BOLD, fill=col)
            d.text((x + 22, y), rest, font=FONT, fill=FG)
        else:
            d.text((x, y), line, font=FONT, fill=col)
        y += LH
    if cursor:
        d.rectangle([PAD + d.textlength(lines[-1], font=FONT) + 2, y - LH + 3,
                     PAD + d.textlength(lines[-1], font=FONT) + 11, y - 3], fill=FG)
    return im


def emit(lines, dur, cursor=False):
    frames.append(render(lines, cursor))
    durs.append(dur)


def type_line(screen, text, per=45, hold=500):
    for i in range(1, len(text) + 1):
        emit(screen + [text[:i]], per, cursor=True)
    emit(screen + [text], hold)
    screen.append(text)


def block(screen, text, per=120, hold=3500):
    for l in wrap(text):
        screen.append(l)
        emit(screen, per)
    emit(screen, hold)


PRE_EDIT = """docs: before you edit plugin/scripts/lint.py, docs/ has traps recorded for it:
  [[page-states]]
    ⚠️ `verified_at` is written *before* you commit, so a fresh docs commit shows every page it touched as "stale by 1". That is your own commit, not drift.
  [[lint]]
    ⚠️ `--topo-order` is what makes this exact, not an optimisation. Topological order places every ancestor of a commit after it, so anything listed before the sha is provably not an ancestor, and since everything is reachable from HEAD that is exactly `sha..HEAD`. Plain reverse-chronological order **undercounts** commits merged in from a side branch, which is the dangerous direction for a staleness check.
    ⚠️ Every git call that returns paths needs `-c core.quotepath=false`. By default git escapes non-ASCII paths, so a Korean page name never matches the path looked up. The first time this regressed, unverified went from 6 to 0 and **looked like an improvement**. ...
If the trap no longer applies after your change, fix the page too."""

COMMIT = """docs: commit 70f1eb5 changed code that 5 docs page(s) describe.
  [[layout]] — .claude-plugin/marketplace.json, plugin/.claude-plugin/plugin.json
  [[page-states]] — plugin/scripts/lint.py
  [[release]] — .claude-plugin/marketplace.json, plugin/.claude-plugin/plugin.json
  [[testing]] — tests/test_roundtrip.py
  [[lint]] — plugin/scripts/lint.py

While the change is still fresh, check each page against what you just did:
  - prose still correct -> move `verified_at` to 70f1eb5
  - prose now wrong     -> fix the body, then move `updated` and `verified_at`
  - a trap you hit while making this change and the page does not mention it -> that is the most valuable thing you can add"""

SESSION = """docs: 5 page(s) describe code that moved since they were checked.
  [[layout]] -- 1 commits behind
  [[lint]] -- 1 commits behind
  [[page-states]] -- 1 commits behind
  [[release]] -- 1 commits behind
  [[testing]] -- 1 commits behind
Reading one before you touch that area is usually cheaper than finding out it was wrong. /docs-sync updates them."""

# scene 1: before the edit
s = []
type_line(s, "$ claude")
s.append("")
type_line(s, "> the stale count misses commits merged from a branch. fix lint.py")
s.append("")
emit(s, 700)
s.append("● Edit(plugin/scripts/lint.py)")
emit(s, 900)
s.append("  PreToolUse hook:")
block(s, PRE_EDIT, hold=6000)

# scene 2: after the commit
s = ["$ claude", "", "> the stale count misses commits merged from a branch. fix lint.py", "",
     "● Edit(plugin/scripts/lint.py) … done", "● Bash(python3 tests/test_roundtrip.py) … ok", ""]
emit(s, 600)
s.append('● Bash(git commit -am "perf: lint.py makes 12 git calls instead of 70")')
emit(s, 900)
s.append("  PostToolUse hook:")
block(s, COMMIT, hold=6000)

# scene 3: next session
s = []
type_line(s, "$ claude")
emit(s, 600)
s.append("  SessionStart hook:")
block(s, SESSION, hold=5000)

# end card
im = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(im)
big = ImageFont.truetype("/mnt/c/Windows/Fonts/consolab.ttf", 26)
d.text((PAD, 200), "llm-project-docs", font=big, fill=FG)
d.text((PAD, 250), "docs/ that knows which pages went stale,", font=FONT, fill=DIM)
d.text((PAD, 274), "and shows you the traps before you edit.", font=FONT, fill=DIM)
d.text((PAD, 330), "/plugin marketplace add DragonBall2/llm-project-docs", font=FONT, fill=GREEN)
d.text((PAD, 354), "/plugin install llm-project-docs@llm-project-docs", font=FONT, fill=GREEN)
d.text((PAD, 378), "/project-docs-setup", font=FONT, fill=GREEN)
frames.append(im); durs.append(4000)

pal = [f.quantize(colors=32, method=Image.Quantize.MEDIANCUT) for f in frames]
pal[0].save(str(Path(__file__).resolve().parent.parent / "demo.gif"), save_all=True, append_images=pal[1:],
            duration=durs, loop=0, optimize=True)
print(len(frames), "frames,", sum(durs) / 1000, "s")
