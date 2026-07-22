"""Skill discovery for the Inkling agent.

A skill is a markdown playbook the model can pull into context on demand —
a stored way of doing one kind of task well. Skills are plain files:

    ---
    name: commit
    description: Stage changes and write a clean commit
    ---
    (instructions the model follows)

They are discovered from three places, later ones shadowing earlier ones:

    skills/               builtin, ships with the repo
    ~/.inkling/skills/    yours, on every project
    .inkling/skills/      this project's own

The user runs one with /skill <name>; the model can also load one itself via
the `skill` tool when a task matches a listed description.
"""

import re
from dataclasses import dataclass
from pathlib import Path

BUILTIN_DIR = Path(__file__).parent / "skills"
USER_DIR = Path.home() / ".inkling" / "skills"

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


@dataclass
class Skill:
    name: str
    description: str
    path: Path
    source: str  # "builtin" | "user" | "project"

    def body(self) -> str:
        try:
            text = self.path.read_text()
        except OSError as exc:
            return f"(could not read skill: {exc})"
        return _FRONTMATTER.sub("", text).strip()


def _parse(path: Path, source: str) -> Skill:
    name, description = path.stem, ""
    try:
        head = path.read_text()[:2000]
    except OSError:
        head = ""
    match = _FRONTMATTER.match(head)
    if match:
        for line in match.group(1).splitlines():
            key, _, value = line.partition(":")
            if key.strip() == "name" and value.strip():
                name = value.strip()
            elif key.strip() == "description":
                description = value.strip()
    return Skill(name=name, description=description, path=path, source=source)


def discover() -> dict[str, Skill]:
    """All available skills by name. Project shadows user shadows builtin."""
    found: dict[str, Skill] = {}
    for directory, source in (
        (BUILTIN_DIR, "builtin"),
        (USER_DIR, "user"),
        (Path.cwd() / ".inkling" / "skills", "project"),
    ):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            skill = _parse(path, source)
            found[skill.name] = skill
    return found


def summary() -> str:
    """One line per skill, for the system prompt."""
    return "\n".join(
        f"- {s.name}: {s.description or '(no description)'}"
        for s in discover().values()
    )
