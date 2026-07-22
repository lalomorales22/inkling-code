"""Permission policy for the Inkling agent.

Three modes control how much runs without asking:

    safe   every mutating tool asks first            (default)
    auto   allowlisted commands run; the rest ask    (the useful one)
    yolo   everything runs except the deny list

Deny rules are absolute — they block in every mode, including yolo. They cover
actions that cannot be undone or that hand control of the machine to something
else, not merely risky ones.

Rules live in config.json next to this file and are meant to be edited.
"""

import json
import re
from pathlib import Path

ALLOW, ASK, DENY = "allow", "ask", "deny"
MODES = ("safe", "auto", "yolo")

CONFIG_PATH = Path(__file__).parent / "config.json"

# Constructs whose real command cannot be read off the string, so an allowlist
# match on the visible text proves nothing.
OPAQUE = re.compile(r"\$\(|`|\beval\b|\bexec\b")

# An interpreter given inline source can do anything the language can do —
# including write files and open sockets — so allowlisting `python` must not
# extend to `python -c "..."`. Running a script file is still fine.
INLINE_CODE = re.compile(
    r"\b(python3?|node|deno|bun|ruby|perl|php|osascript|ba?sh|zsh|fish)\s+"
    r"(-\S*[ce]\b|--eval\b|--command\b)"
)


def split_segments(command: str) -> list[str]:
    """Split a compound command on shell operators, ignoring quoted regions.

    A naive regex split breaks `python -c 'a; b'` into nonsense, and more
    importantly would let `ls && rm -rf ~` pass on the strength of `ls` if only
    the first segment were checked.
    """
    segments: list[str] = []
    current: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(command):
        ch = command[i]
        if quote:
            current.append(ch)
            if ch == quote and (i == 0 or command[i - 1] != "\\"):
                quote = None
        elif ch in "'\"":
            quote = ch
            current.append(ch)
        elif ch in ";\n":
            segments.append("".join(current))
            current = []
        elif command.startswith("&&", i) or command.startswith("||", i):
            segments.append("".join(current))
            current = []
            i += 1
        elif ch == "|":
            segments.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    segments.append("".join(current))
    return [s.strip() for s in segments if s.strip()]


def writes_to_file(command: str) -> bool:
    """True if the command redirects output into a file.

    `echo x > notes.py` mutates the filesystem just as much as write_file does,
    so it must not sail through on `echo` being allowlisted. Descriptor
    plumbing (`2>&1`) and /dev/null are not file writes.
    """
    quote: str | None = None
    i = 0
    while i < len(command):
        ch = command[i]
        if quote:
            if ch == quote and command[i - 1] != "\\":
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == ">":
            rest = command[i:].lstrip(">").lstrip()
            if not rest.startswith("&") and not rest.startswith("/dev/null"):
                return True
        i += 1
    return False

DEFAULT_CONFIG = {
    "default_mode": "auto",
    "auto_approve_tools": ["read_file", "list_dir", "search", "glob", "web_fetch", "todo_write"],
    "bash": {
        "allow": [
            r"^ls\b", r"^pwd$", r"^cat\b", r"^head\b", r"^tail\b", r"^wc\b",
            r"^file\b", r"^stat\b", r"^tree\b", r"^which\b", r"^echo\b", r"^date$",
            r"^find\b", r"^rg\b", r"^grep\b", r"^diff\b", r"^sort\b", r"^uniq\b",
            r"^git (status|diff|log|show|branch|remote|stash list|ls-files|rev-parse)\b",
            r"^git add\b", r"^git commit\b",
            r"^npm (test|run|ls)\b", r"^npx\b", r"^node\b",
            r"^uv (run|add|sync|pip|lock|tree)\b", r"^python3?\b", r"^pytest\b", r"^ruff\b",
            r"^cargo (build|test|check|run|fmt|clippy)\b", r"^go (build|test|run|vet|fmt)\b",
            r"^make\b", r"^mkdir\b", r"^touch\b",
        ],
        "deny": [
            # Unrecoverable filesystem destruction. Scoped to catastrophic targets
            # — root, $HOME, top-level system dirs — rather than every `rm -rf`,
            # so that `rm -rf build` merely asks instead of being blocked outright.
            r"\brm\s+(-\S+\s+)*(/|~|\$HOME|\.)\s*/?\*?\s*$",
            r"\brm\s+(-\S+\s+)*~/\s*\*?\s*$",
            r"\brm\s+(-\S+\s+)*/(Users|etc|usr|bin|sbin|var|System|Applications|Library|opt|private)/?\s*\*?\s*$",
            r"\bmkfs\b", r"\bdiskutil\s+(erase|partition|reformat)",
            r"\bdd\b.*\bof=/dev/", r">\s*/dev/(disk|sd|nvme)",
            # Privilege escalation — also just hangs waiting for a password
            r"^\s*sudo\b", r"^\s*su\b", r"\bchown\s+-R\b.*\s/\s*$", r"\bchmod\s+-R\s+777\s+/",
            # Piping the network straight into a shell
            r"(curl|wget)[^|]*\|\s*(sudo\s+)?(ba|z|k|)sh\b",
            # Exfiltrating credentials
            r"(curl|wget|nc|scp)\b.*(\.ssh/|\.aws/|\.env\b|id_rsa|credentials)",
            r"\bcat\b.*\bid_rsa\b",
            # Wiping history / covering tracks, and fork bombs
            r"\bhistory\s+-c\b", r":\(\)\s*\{.*\}\s*;?\s*:",
            # Rewriting shared history
            r"\bgit\s+push\b.*(--force|-f)\b",
        ],
    },
}


def load_config() -> dict:
    """Read config.json, writing the defaults out on first run."""
    if not CONFIG_PATH.is_file():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n")
        return DEFAULT_CONFIG
    try:
        raw = json.loads(CONFIG_PATH.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"config.json is not valid JSON: {exc}")
    # Merge shallowly so a partial config still gets the default deny rules.
    cfg = {**DEFAULT_CONFIG, **raw}
    cfg["bash"] = {**DEFAULT_CONFIG["bash"], **raw.get("bash", {})}
    return cfg


def default_mode() -> str:
    mode = load_config().get("default_mode", "auto")
    return mode if mode in MODES else "auto"


class Policy:
    def __init__(self, mode: str = "safe", config: dict | None = None):
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        self.mode = mode
        cfg = config if config is not None else load_config()
        self._config_auto = set(cfg["auto_approve_tools"])
        self.auto_tools = set(self._config_auto)
        self.allow = [re.compile(p, re.I) for p in cfg["bash"]["allow"]]
        self.deny = [re.compile(p, re.I) for p in cfg["bash"]["deny"]]
        self.session_allow: set[str] = set()

    def refresh_auto(self, names: set[str]) -> None:
        """Sync with the live tool registry — tools marked auto plus config."""
        self.auto_tools = self._config_auto | names

    def denied_reason(self, command: str) -> str | None:
        for rx in self.deny:
            if rx.search(command):
                return rx.pattern
        return None

    def _bash_segments_allowed(self, command: str) -> bool:
        """Every segment of a compound command must independently match allow.

        Without this, `ls && rm -rf ~` would pass on the strength of `ls`.
        """
        if OPAQUE.search(command) or writes_to_file(command) or INLINE_CODE.search(command):
            return False
        for segment in split_segments(command):
            if not any(rx.search(segment) for rx in self.allow):
                return False
        return True

    def check(self, tool: str, args: dict) -> tuple[str, str]:
        """Return (decision, reason) for a pending tool call."""
        if tool == "bash":
            command = args.get("command", "")
            hit = self.denied_reason(command)
            if hit:
                return DENY, f"matches deny rule: {hit}"

        if tool in self.auto_tools:
            return ALLOW, "read-only"

        if self.mode == "yolo":
            return ALLOW, "yolo mode"

        if tool in self.session_allow:
            return ALLOW, "approved for this session"

        if self.mode == "auto":
            if tool == "bash":
                if self._bash_segments_allowed(args.get("command", "")):
                    return ALLOW, "matches allow rule"
                return ASK, "not on the allow list"
            if tool.startswith("mcp__"):
                return ASK, "external MCP tool"
            return ASK, "modifies files"

        return ASK, "safe mode"
