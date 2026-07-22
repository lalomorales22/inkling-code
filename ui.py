"""Terminal presentation for the Inkling agent.

Visual language: glass. The terminal background shows through everywhere — no
filled blocks, no painted backgrounds. Thin blue hairlines are the only strong
colour, so structure reads as an outline floating over whatever is behind it,
and the actual content stays in the default foreground.

Everything degrades: animation is disabled when stdout is not a tty (so piped
output stays clean), colour is disabled when NO_COLOR is set or TERM is dumb,
and the palette upgrades itself to 24-bit when the terminal advertises it.
"""

import os
import re
import shutil
import sys
import threading
import time

# ── capability detection ────────────────────────────────────────────────────

IS_TTY = sys.stdout.isatty() or bool(os.environ.get("INKLING_FORCE_TTY"))
NO_COLOR = bool(os.environ.get("NO_COLOR")) or os.environ.get("TERM") == "dumb"
TRUECOLOR = os.environ.get("COLORTERM", "") in ("truecolor", "24bit")
ANIMATE = IS_TTY and not NO_COLOR


def _c(code256: int, rgb: tuple[int, int, int]) -> str:
    """A colour, expressed however this terminal can manage it.

    Terminal.app tops out at 256 colours; iTerm/Ghostty/WezTerm do 24-bit.
    """
    if NO_COLOR:
        return ""
    if TRUECOLOR:
        return f"\033[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"
    return f"\033[38;5;{code256}m"


# The palette is deliberately narrow: three blues, two greys, and two signal
# colours reserved for approval and refusal.
LINE = _c(39, (56, 189, 248))    # hairline blue — borders, rails, markers
GLOW = _c(45, (125, 211, 252))   # brighter blue — titles, active elements
DEEP = _c(24, (7, 89, 133))      # receded blue — inactive rail, leaders
DIM = "" if NO_COLOR else "\033[2m"
MUTE = _c(242, (115, 115, 115))  # secondary text
WARN = _c(214, (251, 191, 36))   # awaiting a decision
STOP = _c(203, (248, 113, 113))  # blocked or declined
OK = _c(78, (74, 222, 128))      # completed
OFF = "" if NO_COLOR else "\033[0m"
BOLD = "" if NO_COLOR else "\033[1m"
ITAL = "" if NO_COLOR else "\033[3m"

CLEAR_LINE = "\r\033[K" if IS_TTY else ""
HIDE_CURSOR = "\033[?25l" if ANIMATE else ""
SHOW_CURSOR = "\033[?25h" if ANIMATE else ""

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def width(cap: int = 76) -> int:
    return min(shutil.get_terminal_size((80, 24)).columns - 2, cap)


def _plain_len(text: str) -> int:
    """Visible length, ignoring ANSI escape sequences."""
    out, i = 0, 0
    while i < len(text):
        if text[i] == "\033":
            while i < len(text) and text[i] != "m":
                i += 1
        else:
            out += 1
        i += 1
    return out


# ── boot ────────────────────────────────────────────────────────────────────

def boot(model: str, mode: str, cwd: str, animate: bool = True,
         facts: list[str] | None = None) -> None:
    """Draw the opening frame, tracing its outline in rather than printing it.

    `facts` are extra pre-styled rows — tool/skill/MCP counts, session id —
    rendered under a hairline divider inside the same frame.
    """
    w = width()
    inner = w - 2
    mode_tint = {"safe": OK, "auto": WARN, "yolo": STOP}.get(mode, GLOW)

    rows: list[str | None] = [
        f"{GLOW}{BOLD}inkling{OFF}{MUTE}  ·  glass interface{OFF}",
        f"{MUTE}{model}{OFF}",
        f"{MUTE}mode {OFF}{mode_tint}{mode}{OFF}{MUTE}  ·  {cwd}{OFF}",
    ]
    if facts:
        rows.append(None)  # divider
        rows.extend(facts)

    def render(row: str | None) -> str:
        if row is None:
            return f"{LINE}├{DEEP}{'╌' * inner}{OFF}{LINE}┤{OFF}"
        pad = " " * max(0, inner - 1 - _plain_len(row))
        return f"{LINE}│{OFF} {row}{pad}{LINE}│{OFF}"

    if not ANIMATE or not animate:
        print(f"{LINE}╭{'─' * inner}╮{OFF}")
        for row in rows:
            print(render(row))
        print(f"{LINE}╰{'─' * inner}╯{OFF}")
        print()
        return

    sys.stdout.write(HIDE_CURSOR)
    try:
        # Trace the top edge outward from the centre — the frame assembles
        # itself rather than appearing all at once.
        for step in range(0, inner // 2 + 1, 3):
            left = inner // 2 - step
            bar = "─" * (step * 2)
            sys.stdout.write(f"\r{LINE}{' ' * left}╭{bar}╮{OFF}")
            sys.stdout.flush()
            time.sleep(0.008)
        sys.stdout.write(f"\r{LINE}╭{'─' * inner}╮{OFF}\n")

        for row in rows:
            sys.stdout.write(render(row) + "\n")
            sys.stdout.flush()
            time.sleep(0.045)

        sys.stdout.write(f"{LINE}╰{'─' * inner}╯{OFF}\n\n")
        sys.stdout.flush()
    finally:
        sys.stdout.write(SHOW_CURSOR)


# ── latency spinner ─────────────────────────────────────────────────────────

class Spinner:
    """Braille spinner with a live elapsed counter.

    Runs on its own thread so it keeps turning while the main thread blocks on
    the first byte from the API — which is where the dead air used to be.
    """

    def __init__(self, label: str = "thinking"):
        self.label = label
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.started = time.monotonic()

    def __enter__(self) -> "Spinner":
        if ANIMATE:
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        return self

    def _spin(self) -> None:
        sys.stdout.write(HIDE_CURSOR)
        i = 0
        while not self._stop.is_set():
            glyph = SPINNER[i % len(SPINNER)]
            elapsed = time.monotonic() - self.started
            sys.stdout.write(
                f"\r  {LINE}{glyph}{OFF} {MUTE}{self.label}{OFF} {DEEP}{'·' * (i % 12)}{OFF} "
                f"{MUTE}{elapsed:.1f}s{OFF}\033[K"
            )
            sys.stdout.flush()
            i += 1
            self._stop.wait(0.08)

    def stop(self) -> float:
        elapsed = time.monotonic() - self.started
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.3)
            sys.stdout.write(CLEAR_LINE + SHOW_CURSOR)
            sys.stdout.flush()
        return elapsed

    def __exit__(self, *exc) -> None:
        self.stop()


# ── streaming reveal ────────────────────────────────────────────────────────

class Reveal:
    """Types the model's prose out at a readable pace, without ever lagging.

    A fixed per-character delay would fall further behind the faster the model
    streams. Instead this tracks a target rate and only sleeps while it is
    ahead of schedule, so the effect degrades to raw streaming under load
    rather than queueing up a backlog.
    """

    def __init__(self, enabled: bool = True, rate: int = 1200):
        self.enabled = enabled and ANIMATE
        self.rate = rate
        self.started: float | None = None
        self.written = 0

    def write(self, text: str) -> None:
        if not self.enabled:
            sys.stdout.write(text)
            sys.stdout.flush()
            return
        if self.started is None:
            self.started = time.monotonic()
        for ch in text:
            sys.stdout.write(ch)
            self.written += 1
            due = self.started + self.written / self.rate
            slack = due - time.monotonic()
            if slack > 0:
                sys.stdout.flush()
                time.sleep(min(slack, 0.02))
        sys.stdout.flush()

    def reset(self) -> None:
        self.started = None
        self.written = 0


# ── the activity rail ───────────────────────────────────────────────────────
#
# Tool calls hang off a continuous vertical hairline for the duration of a
# turn. The rail is what makes a long chain of calls read as one unit.

def rail_open() -> None:
    print(f"  {DEEP}│{OFF}")


NAME_COL = 12  # tool names pad to this so details line up in a column


def rail_call(name: str, detail: str, tint: str = LINE) -> None:
    w = width()
    padded = name.ljust(NAME_COL)
    label = f"{tint}├▸{OFF} {GLOW}{padded}{OFF}"
    room = w - NAME_COL - 8
    if detail and room > 8:
        detail = detail.replace("\n", " ⏎ ")
        if len(detail) > room:
            detail = detail[: room - 1] + "…"
        print(f"  {label} {MUTE}{detail}{OFF}")
    else:
        print(f"  {label}")


def rail_result(text: str, elapsed: float | None = None, tint: str = DEEP) -> None:
    w = width()
    body = text.replace("\n", " ")[: w - 18]
    stamp = ""
    if elapsed is not None:
        stamp = f"{MUTE}{elapsed * 1000:.0f}ms{OFF}" if elapsed < 1 else f"{MUTE}{elapsed:.1f}s{OFF}"
    pad = " " * max(1, w - _plain_len(body) - _plain_len(stamp) - 6)
    print(f"  {tint}│{OFF}  {MUTE}{body}{OFF}{pad}{stamp}")


def rail_blocked(reason: str) -> None:
    print(f"  {STOP}├╳{OFF} {STOP}blocked{OFF} {MUTE}· {reason}{OFF}")


def rail_declined() -> None:
    print(f"  {DEEP}│{OFF}  {MUTE}declined{OFF}")


def rail_close(elapsed: float, steps: int) -> None:
    w = width()
    tail = f"{MUTE}{steps} step{'s' if steps != 1 else ''} · {elapsed:.1f}s{OFF}"
    pad = " " * max(1, w - _plain_len(tail) - 4)
    print(f"  {DEEP}╰{'─' * 2}{OFF}{pad}{tail}\n")


# ── framed panels ───────────────────────────────────────────────────────────

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def _wrap_ansi(line: str, limit: int) -> list[str]:
    """Hard-wrap a coloured line without ever splitting an escape sequence.

    Panels must never truncate: the whole point is that the user sees exactly
    what they are approving, so a long command wraps rather than being quietly
    cut off. The colours active at the break are re-applied to the next
    fragment, so styling survives the wrap even mid-span.
    """
    if _plain_len(line) <= limit:
        return [line]
    out: list[str] = []
    current, active, visible = "", "", 0
    i = 0
    while i < len(line):
        seq = _ANSI_RE.match(line, i)
        if seq:
            current += seq.group(0)
            active = "" if seq.group(0) == "\033[0m" else active + seq.group(0)
            i = seq.end()
            continue
        if visible == limit:
            out.append(current + (OFF if active else ""))
            current, visible = active, 0
        current += line[i]
        visible += 1
        i += 1
    if current:
        out.append(current)
    return out


def panel(title: str, lines: list[str], tint: str = WARN) -> None:
    """A thin outlined panel, used where the user has to actually look."""
    w = width()
    inner = w - 2
    head = f"{tint}╭─ {OFF}{tint}{title}{OFF} "
    print(f"{head}{tint}{'─' * max(0, inner - _plain_len(title) - 3)}╮{OFF}")
    for raw in lines:
        for line in _wrap_ansi(raw, inner - 2):
            pad = " " * max(0, inner - 1 - _plain_len(line))
            print(f"{tint}│{OFF} {line}{pad}{tint}│{OFF}")
    print(f"{tint}╰{'─' * inner}╯{OFF}")


def plan(todos: list[dict]) -> None:
    if not todos:
        return
    done = sum(1 for t in todos if t["status"] == "done")
    total = len(todos)
    filled = int((done / total) * 18) if total else 0
    bar = f"{LINE}{'━' * filled}{OFF}{DEEP}{'─' * (18 - filled)}{OFF}"
    print(f"  {DEEP}│{OFF}  {bar}  {MUTE}{done}/{total}{OFF}")
    for item in todos:
        if item["status"] == "done":
            print(f"  {DEEP}│{OFF}  {OK}✓{OFF} {DIM}{item['task']}{OFF}")
        elif item["status"] == "in_progress":
            print(f"  {DEEP}│{OFF}  {LINE}▸{OFF} {item['task']}")
        else:
            print(f"  {DEEP}│{OFF}  {DEEP}·{OFF} {MUTE}{item['task']}{OFF}")


def prompt_line(mode: str) -> str:
    tint = {"safe": OK, "auto": WARN, "yolo": STOP}.get(mode, GLOW)
    return f"{tint}›{OFF} "


def rule() -> None:
    print(f"{DEEP}{'─' * width()}{OFF}")


# ── markdown-lite ───────────────────────────────────────────────────────────
#
# The model writes markdown; a terminal shows asterisks. This is the smallest
# renderer that fixes that without pretending to be a browser: headings get
# weight, bullets get a real glyph, inline code gets the glow tint, and fenced
# code hangs off a gutter hairline. It is stateful and line-buffered so it can
# sit inside the streaming path.

_MD_CODE = re.compile(r"`([^`\n]+)`")
_MD_BOLD = re.compile(r"\*\*([^*\n]+?)\*\*")
_MD_HEAD = re.compile(r"^(#{1,4})\s+(.*)")
_MD_BULLET = re.compile(r"^(\s*)[-*]\s+")


class MarkdownLite:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled and not NO_COLOR
        self._buf = ""
        self._fence = False

    def _inline(self, text: str) -> str:
        text = _MD_CODE.sub(f"{GLOW}\\1{OFF}", text)
        text = _MD_BOLD.sub(f"{BOLD}\\1{OFF}", text)
        return text

    def _line(self, line: str) -> str:
        if line.lstrip().startswith("```"):
            self._fence = not self._fence
            return f"{DEEP}{line}{OFF}"
        if self._fence:
            return f"{DEEP}│{OFF} {line}"
        head = _MD_HEAD.match(line)
        if head:
            return f"{BOLD}{GLOW}{head.group(2)}{OFF}"
        line = _MD_BULLET.sub(f"\\1{LINE}•{OFF} ", line)
        return self._inline(line)

    def feed(self, text: str) -> str:
        """Take a stream fragment, return what is ready to print (styled)."""
        if not self.enabled:
            return text
        self._buf += text
        out = []
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            out.append(self._line(line) + "\n")
        # A single very long line should not sit invisible until it ends.
        if len(self._buf) > 400:
            out.append(self._inline(self._buf) if not self._fence
                       else f"{DEEP}│{OFF} {self._buf}")
            self._buf = ""
        return "".join(out)

    def flush(self) -> str:
        if not self.enabled or not self._buf:
            remainder, self._buf = self._buf, ""
            return remainder
        remainder, self._buf = self._line(self._buf), ""
        return remainder
