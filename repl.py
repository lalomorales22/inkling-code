"""The input line: prompt_toolkit session with completions, keys and toolbar.

This is where the app stops feeling like input() and starts feeling like a
tool. Typing `/` opens a live menu of commands with descriptions; `@` completes
file paths into the prompt; history persists across sessions; Enter submits
while Ctrl-J inserts a newline; Ctrl-T cycles the permission mode in place.

The toolbar keeps the glass aesthetic: no reverse video, just dim text under a
hairline, showing mode · provider · context size · connections · cwd.
"""

import os
from pathlib import Path

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

import commands
import ui

HISTORY_PATH = Path.home() / ".inkling" / "history"

STYLE = Style.from_dict({
    "bottom-toolbar": "noreverse noinherit fg:#64748b bg:default",
    "bottom-toolbar.text": "noreverse noinherit fg:#64748b bg:default",
    "completion-menu": "bg:#101826 fg:#94a3b8",
    "completion-menu.completion": "bg:#101826 fg:#94a3b8",
    "completion-menu.completion.current": "bg:#164e63 fg:#e2f4fd bold",
    "completion-menu.meta.completion": "bg:#0b1220 fg:#475569",
    "completion-menu.meta.completion.current": "bg:#164e63 fg:#a5f3fc",
    "scrollbar.background": "bg:#0b1220",
    "scrollbar.button": "bg:#164e63",
})


def _iter_paths(fragment: str) -> list[str]:
    """Filesystem completions for an @path fragment, directories first.

    Completions echo back exactly what the user typed as the prefix, so
    'src/ag' completes to 'src/agent.py' and '~/De' to '~/Desktop/'.
    """
    base = Path(fragment).expanduser()
    if fragment.endswith("/") or not fragment:
        directory, stem = (base if fragment else Path(".")), ""
    else:
        directory, stem = base.parent, base.name
    if not directory.is_dir():
        return []
    typed_prefix = fragment[: len(fragment) - len(stem)]
    out = []
    try:
        entries = sorted(directory.iterdir(),
                         key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError:
        return []
    for p in entries:
        if p.name.startswith(".") and not stem.startswith("."):
            continue
        if not p.name.lower().startswith(stem.lower()):
            continue
        out.append(typed_prefix + p.name + ("/" if p.is_dir() else ""))
        if len(out) >= 40:
            break
    return out


class InklingCompleter(Completer):
    """Slash commands with descriptions, argument values, and @file paths."""

    def __init__(self, ctx):
        # ctx supplies live lists: skills(), sessions(), mcp_servers()
        self.ctx = ctx

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # @path completion works anywhere in the line.
        word = document.get_word_before_cursor(pattern=None) or ""
        at = text.rfind("@")
        if at != -1 and " " not in text[at:]:
            fragment = text[at + 1:]
            for path in _iter_paths(fragment):
                yield Completion(path, start_position=-len(fragment))
            return

        if not text.startswith("/"):
            return

        parts = text.split(" ")
        if len(parts) == 1:
            # Completing the command itself.
            for cmd in commands.COMMANDS:
                if cmd.name.startswith(text):
                    yield Completion(
                        cmd.name, start_position=-len(text),
                        display=cmd.name + (" " + cmd.usage if cmd.usage else ""),
                        display_meta=cmd.description)
            return

        # Completing an argument.
        head, fragment = parts[0], parts[-1]
        values: list[tuple[str, str]] = []
        if head == "/mode":
            values = [(m, "") for m in ("safe", "auto", "yolo")]
        elif head == "/model":
            values = [(m, "") for m in ("together", "deepinfra", "auto")]
        elif head == "/skill" and len(parts) == 2:
            values = [(name, s.description)
                      for name, s in sorted(self.ctx.skills().items())]
        elif head == "/mcp":
            if len(parts) == 2:
                values = [(k, v) for k, v in commands.MCP_SUBCOMMANDS.items()]
            elif parts[1] == "remove":
                values = [(name, "") for name in self.ctx.mcp_servers()]
        elif head == "/resume" and len(parts) == 2:
            values = [(m["id"], m.get("title") or "")
                      for m in self.ctx.sessions()]
        elif head == "/cwd":
            for path in _iter_paths(fragment):
                if path.endswith("/"):
                    yield Completion(path, start_position=-len(fragment))
            return

        for value, meta in values:
            if value.startswith(fragment):
                yield Completion(value, start_position=-len(fragment),
                                 display_meta=meta or None)


def _bindings(mode_cycle) -> KeyBindings:
    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        buf = event.current_buffer
        if buf.complete_state:
            completion = buf.complete_state.current_completion
            if completion:
                buf.apply_completion(completion)
                return
            buf.cancel_completion()
        buf.validate_and_handle()

    @kb.add("c-j")
    @kb.add("escape", "enter")
    def _(event):
        event.current_buffer.insert_text("\n")

    @kb.add("c-t")
    def _(event):
        mode_cycle()
        event.app.invalidate()

    return kb


class Repl:
    def __init__(self, ctx):
        """ctx must provide: skills(), sessions(), mcp_servers(),
        toolbar() -> str (ANSI), mode() -> str, cycle_mode() -> None."""
        self.ctx = ctx
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.session = PromptSession(
            history=FileHistory(str(HISTORY_PATH)),
            completer=InklingCompleter(ctx),
            complete_while_typing=True,
            key_bindings=_bindings(ctx.cycle_mode),
            style=STYLE,
            multiline=True,
            prompt_continuation=ANSI(f"{ui.DEEP}… {ui.OFF}"),
            reserve_space_for_menu=6,
        )

    def read(self) -> str:
        return self.session.prompt(
            ANSI(ui.prompt_line(self.ctx.mode())),
            bottom_toolbar=lambda: ANSI(self.ctx.toolbar()),
        )
