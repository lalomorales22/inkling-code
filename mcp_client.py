"""MCP client for the Inkling agent.

Connects to Model Context Protocol servers (stdio subprocesses or streamable
HTTP endpoints) and registers their tools into the agent's tool registry as
`mcp__<server>__<tool>`, so the model uses them exactly like builtin tools.

Servers are declared in mcp.json next to this file:

    {
      "servers": {
        "github":  {"transport": "stdio", "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_TOKEN": "..."}},
        "docs":    {"transport": "http", "url": "https://example.com/mcp"}
      }
    }

/mcp add and /mcp remove edit that file; /mcp reload reconnects.

The MCP SDK is async; the agent loop is not. A single event loop runs on a
daemon thread and every operation is submitted to it, so sessions stay open
across turns without the agent loop going async.
"""

import asyncio
import json
import os
import threading
from contextlib import AsyncExitStack
from pathlib import Path

import tools

CONFIG_PATH = Path(__file__).parent / "mcp.json"

CONNECT_TIMEOUT = 45   # first npx run may download the server package
CALL_TIMEOUT = 120

PREFIX = "mcp__"


def load_config() -> dict:
    if not CONFIG_PATH.is_file():
        return {"servers": {}}
    try:
        cfg = json.loads(CONFIG_PATH.read_text())
    except json.JSONDecodeError:
        return {"servers": {}}
    cfg.setdefault("servers", {})
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n")


def _safe_name(server: str, tool: str) -> str:
    """Qualified tool name, kept within the API's 64-char identifier limit."""
    name = f"{PREFIX}{server}__{tool}"
    if len(name) > 64:
        name = name[:56] + f"_{abs(hash(tool)) % 10**6}"
    return name


class Manager:
    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        # server name -> {"session": ClientSession, "stack": AsyncExitStack,
        #                 "tools": {qualified: real_tool_name}}
        self.servers: dict[str, dict] = {}

    # ── event loop plumbing ─────────────────────────────────────────────

    def _ensure_loop(self) -> None:
        if self._loop is not None:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    def _submit(self, coro, timeout: float):
        self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout)

    # ── connecting ──────────────────────────────────────────────────────

    async def _open(self, name: str, spec: dict):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        stack = AsyncExitStack()
        try:
            if spec.get("transport", "stdio") == "http":
                from mcp.client.streamable_http import streamablehttp_client

                read, write, _ = await stack.enter_async_context(
                    streamablehttp_client(spec["url"]))
            else:
                params = StdioServerParameters(
                    command=spec["command"],
                    args=spec.get("args", []),
                    env={**os.environ, **spec.get("env", {})},
                )
                read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            listing = await session.list_tools()
        except BaseException:
            await stack.aclose()
            raise
        return stack, session, listing.tools

    def connect(self, name: str, spec: dict) -> tuple[bool, str]:
        """Connect one server and register its tools. Returns (ok, detail)."""
        if name in self.servers:
            self.disconnect(name)
        try:
            stack, session, mcp_tools = self._submit(
                self._open(name, spec), CONNECT_TIMEOUT)
        except Exception as exc:
            reason = str(exc).strip() or type(exc).__name__
            return False, reason.splitlines()[0][:80]

        registered: dict[str, str] = {}
        for t in mcp_tools:
            qualified = _safe_name(name, t.name)
            registered[qualified] = t.name
            annotations = getattr(t, "annotations", None)
            read_only = bool(annotations and getattr(annotations, "readOnlyHint", False))
            schema = {
                "type": "function",
                "function": {
                    "name": qualified,
                    "description": (t.description or "")[:1000],
                    "parameters": t.inputSchema or {"type": "object", "properties": {}},
                },
            }
            tools.register(schema, self._make_executor(qualified), auto=read_only)

        self.servers[name] = {"stack": stack, "session": session, "tools": registered}
        return True, f"{len(registered)} tools"

    def connect_all(self) -> list[tuple[str, bool, str]]:
        results = []
        for name, spec in load_config()["servers"].items():
            ok, detail = self.connect(name, spec)
            results.append((name, ok, detail))
        return results

    def disconnect(self, name: str) -> None:
        entry = self.servers.pop(name, None)
        if entry is None:
            return
        tools.unregister_prefix(f"{PREFIX}{name}__")
        try:
            self._submit(entry["stack"].aclose(), 10)
        except Exception:
            pass  # server already gone; nothing to clean up on our side

    def shutdown(self) -> None:
        for name in list(self.servers):
            self.disconnect(name)
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)

    # ── calling ─────────────────────────────────────────────────────────

    def _make_executor(self, qualified: str):
        def executor(**args) -> str:
            return self.call(qualified, args)
        return executor

    def call(self, qualified: str, args: dict) -> str:
        for name, entry in self.servers.items():
            if qualified in entry["tools"]:
                real = entry["tools"][qualified]
                try:
                    result = self._submit(
                        entry["session"].call_tool(real, args), CALL_TIMEOUT)
                except Exception as exc:
                    return f"Error calling {qualified}: {exc}"
                return self._render(result)
        return f"Error: no connected MCP server provides {qualified}"

    @staticmethod
    def _render(result) -> str:
        parts = []
        for block in result.content or []:
            kind = getattr(block, "type", "")
            if kind == "text":
                parts.append(block.text)
            elif kind == "image":
                parts.append(f"[image: {getattr(block, 'mimeType', 'unknown')}]")
            elif kind == "resource":
                resource = getattr(block, "resource", None)
                text = getattr(resource, "text", None)
                parts.append(text if text else f"[resource: {getattr(resource, 'uri', '?')}]")
        if not parts and getattr(result, "structuredContent", None):
            parts.append(json.dumps(result.structuredContent, indent=1, default=str))
        text = "\n".join(parts).strip() or "(empty result)"
        if getattr(result, "isError", False):
            text = f"Error from MCP tool:\n{text}"
        return text[:tools.MAX_OUTPUT]

    # ── introspection ───────────────────────────────────────────────────

    def status(self) -> list[tuple[str, int]]:
        return [(name, len(entry["tools"])) for name, entry in self.servers.items()]

    def tool_lines(self) -> list[str]:
        lines = []
        for name, entry in self.servers.items():
            for qualified in sorted(entry["tools"]):
                lines.append(qualified)
        return lines
