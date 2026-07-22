"""Slash-command catalog for the Inkling agent.

This is metadata only — the completion menu and /help both render from it, and
agent.py dispatches on the names. Keeping it in one place means the menu, the
help text and the dispatcher can never disagree about what exists.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    name: str
    usage: str        # argument hint shown in help, "" if none
    description: str


COMMANDS: list[Command] = [
    Command("/help",     "",                    "commands, modes, tools and keys"),
    Command("/mode",     "[safe|auto|yolo]",    "show or change the permission mode"),
    Command("/model",    "[together|deepinfra|auto]", "show or switch the inference provider"),
    Command("/tools",    "",                    "every tool the model can use right now"),
    Command("/skills",   "",                    "list available skills"),
    Command("/skill",    "<name> [args]",       "run a skill playbook"),
    Command("/mcp",      "[add|remove|tools|reload]", "manage MCP servers"),
    Command("/plan",     "",                    "re-print the current todo list"),
    Command("/compact",  "",                    "summarize history to free context"),
    Command("/clear",    "",                    "wipe conversation history"),
    Command("/sessions", "",                    "list saved sessions"),
    Command("/resume",   "<id>",                "resume a saved session"),
    Command("/export",   "[path]",              "write the conversation to markdown"),
    Command("/memory",   "",                    "show persistent memory"),
    Command("/remember", "<fact>",              "add a fact to persistent memory"),
    Command("/init",     "",                    "generate INKLING.md for this project"),
    Command("/cwd",      "[path]",              "show or change the working directory"),
    Command("/tokens",   "",                    "context size and usage this session"),
    Command("/config",   "",                    "paths to the editable config files"),
    Command("/exit",     "",                    "quit (Ctrl-D also works)"),
]

BY_NAME = {c.name: c for c in COMMANDS}

MCP_SUBCOMMANDS = {
    "add": "add a server:  /mcp add <name> <command args…>  or  /mcp add <name> --http <url>",
    "remove": "remove a server from mcp.json",
    "tools": "list every connected MCP tool",
    "reload": "reconnect all servers from mcp.json",
}
