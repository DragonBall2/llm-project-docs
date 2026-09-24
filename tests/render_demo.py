"""Render demo.gif (not a test; needs Pillow and the Windows fonts under /mnt/c).

One Claude Code turn: the agent fixes lint.py, the pre-edit hook shows the traps,
the commit hook names the pages, and the agent updates them before it is done.
Hook text is verbatim from running the hooks on this repository at 70f1eb5; the
diff counts come from git; the terminal around it is drawn here. One long trap in
the pre-edit output is trimmed (marked ...).
"""
from pathlib import Path
import subprocess
import textwrap

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H, PAD, LH = 960, 640, 20, 24
FONT = ImageFont.truetype("/mnt/c/Windows/Fonts/consola.ttf", 17)
BOLD = ImageFont.truetype("/mnt/c/Windows/Fonts/consolab.ttf", 17)
SYM = ImageFont.truetype("/mnt/c/Windows/Fonts/seguisym.ttf", 17)
COLS = 96
BOTTOM = 4 * LH + 8  # input box

BG, FG, DIM, DIMMER = "#0d1117", "#e6edf3", "#8b949e", "#484f58"
GREEN, CYAN, YELLOW, ORANGE, RED = "#3fb950", "#79c0ff", "#e3b341", "#f0883e", "#ff7b72"

frames, durs = [], []


def stat(sha, path):
    out = subprocess.run(["git", "-C", str(ROOT), "show", "--numstat", "--format=", sha, "--", path],
                         capture_output=True, text=True).stdout.split()
    return f"Updated {path} with {out[0]} additions and {out[1]} removals"


def wrap(text, extra=0):
    lines = []
    for raw in text.split("\n"):
        lead = len(raw) - len(raw.lstrip(" "))
        body = raw.strip()
        if not body:
            lines.append("")
            continue
        for i, l in enumerate(textwrap.wrap(body, COLS - lead - extra) or [""]):
            lines.append(" " * (lead + (0 if i == 0 else 3)) + l)
    return lines


def draw_line(d, x, y, line):
    """One transcript line, coloured the way the TUI colours it."""
    s = line.lstrip()
    indent = len(line) - len(s)
    x += d.textlength(" " * indent, font=FONT)
    if s.startswith("> "):
        d.text((x, y), s, font=BOLD, fill=FG)
    elif s.startswith("⏺"):
        rest = s[1:].strip()
        d.text((x, y - 1), "⏺", font=SYM, fill=GREEN if "(" in rest.split(" ")[0] else FG)
        d.text((x + 22, y), rest, font=FONT, fill=FG)
    elif s.startswith("⎿"):
        rest = s[1:].strip()
        d.text((x, y - 1), "⎿", font=SYM, fill=DIM)
        col = DIM
        if rest.endswith("hook"):
            col = DIMMER
        d.text((x + 22, y), rest, font=FONT, fill=col)
    elif s.startswith("docs:"):
        d.text((x, y), s, font=FONT, fill=YELLOW)
    elif s.startswith("[["):
        d.text((x, y), s, font=FONT, fill=CYAN)
    elif s.startswith("⚠"):
        d.text((x, y - 1), "⚠", font=SYM, fill=ORANGE)
        d.text((x + 20, y), s[1:].lstrip("️ "), font=FONT, fill=ORANGE)
    elif s.startswith("- "):
        d.text((x, y), s, font=FONT, fill=DIM)
    else:
        d.text((x, y), s, font=FONT, fill=DIM if indent >= 5 else FG)


def render(lines, typing=None):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    top = PAD
    rows = (H - BOTTOM - PAD * 2) // LH
    y = top
    for line in lines[-rows:]:
        draw_line(d, PAD, y, line)
        y += LH
    # input box, as the TUI draws it
    by = H - BOTTOM
    d.rounded_rectangle([PAD, by + 6, W - PAD, by + 2 * LH + 6], radius=6, outline=DIMMER, width=1)
    prompt = typing if typing is not None else ""
    d.text((PAD + 14, by + LH - 6), "> " + prompt, font=FONT, fill=FG if prompt else DIMMER)
    if typing is not None:
        cx = PAD + 14 + d.textlength("> " + prompt, font=FONT)
        d.rectangle([cx, by + LH - 3, cx + 9, by + 2 * LH - 9], fill=FG)
    d.text((PAD + 14, by + 3 * LH), "? for shortcuts", font=FONT, fill=DIMMER)
    return im


def emit(lines, dur, typing=None):
    frames.append(render(lines, typing))
    durs.append(dur)


def say(screen, line, dur=500):
    screen.append(line)
    emit(screen, dur)


def block(screen, text, per=90, hold=3000):
    for l in wrap(text, extra=6):
        screen.append("     " + l)
        emit(screen, per)
    emit(screen, hold)


PRE_EDIT = """docs: before you edit plugin/scripts/lint.py, docs/ has traps recorded for it:
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

ask = "the stale count misses commits merged from a branch. fix lint.py"
s = []
emit(s, 800, typing="")
for i in range(1, len(ask) + 1):
    emit(s, 40, typing=ask[:i])
emit(s, 600, typing=ask)
say(s, "> " + ask, 900)
say(s, "")
say(s, "⏺ Read(plugin/scripts/lint.py)", 400)
say(s, "  ⎿  Read 355 lines", 700)
say(s, "⏺ Update(plugin/scripts/lint.py)", 500)
say(s, "  ⎿  PreToolUse hook", 300)
block(s, PRE_EDIT, hold=5500)
say(s, "  ⎿  " + stat("70f1eb5", "plugin/scripts/lint.py"), 900)
say(s, "⏺ Bash(python3 tests/test_roundtrip.py)", 600)
say(s, "  ⎿  ok - scaffold, clean, json, hooks, edit hook, unverified, stale, broken link", 900)
say(s, '⏺ Bash(git commit -am "perf: lint.py makes 12 git calls instead of 70")', 600)
say(s, "  ⎿  [main 70f1eb5] perf: lint.py makes 12 git calls instead of 70", 500)
say(s, "  ⎿  PostToolUse hook", 300)
block(s, COMMIT, hold=5000)
say(s, "⏺ Five pages describe what I just changed. Checking each while the change is still", 100)
say(s, "  in context.", 1500)
say(s, "⏺ Update(docs/subsystems/lint.md)", 500)
say(s, "  ⎿  " + stat("f5ce7ea", "docs/subsystems/lint.md"), 700)
say(s, "⏺ Update(docs/concepts/page-states.md)", 500)
say(s, "  ⎿  " + stat("f5ce7ea", "docs/concepts/page-states.md"), 700)
say(s, "⏺ Update(docs/operations/testing.md)", 500)
say(s, "  ⎿  " + stat("f5ce7ea", "docs/operations/testing.md"), 700)
say(s, "⏺ layout and release only describe the version bump. The prose still holds, so only", 100)
say(s, "  verified_at moves.", 1200)
say(s, '⏺ Bash(git commit -am "docs: pages named by the commit hook, checked against 70f1eb5")', 600)
say(s, "  ⎿  [main f5ce7ea] docs: pages named by the commit hook, checked against 70f1eb5", 800)
say(s, "⏺ Done. lint.py makes 12 git calls instead of 70, and the five pages that describe it", 100)
say(s, "  are checked against 70f1eb5.", 6000)

# end card
im = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(im)
big = ImageFont.truetype("/mnt/c/Windows/Fonts/consolab.ttf", 26)
d.text((PAD, 200), "llm-project-docs", font=big, fill=FG)
d.text((PAD, 250), "The agent that changed the code updates the docs, in the same turn.", font=FONT, fill=DIM)
d.text((PAD, 274), "You never think about them. Nothing is bumped by a script.", font=FONT, fill=DIM)
d.text((PAD, 330), "/plugin marketplace add DragonBall2/llm-project-docs", font=FONT, fill=GREEN)
d.text((PAD, 354), "/plugin install llm-project-docs@llm-project-docs", font=FONT, fill=GREEN)
d.text((PAD, 378), "/project-docs-setup", font=FONT, fill=GREEN)
frames.append(im)
durs.append(4500)

pal = [f.quantize(colors=16, method=Image.Quantize.MEDIANCUT) for f in frames]
pal[0].save(ROOT / "demo.gif", save_all=True, append_images=pal[1:],
            duration=durs, loop=0, optimize=True)
print(len(frames), "frames,", round(sum(durs) / 1000, 1), "s")
