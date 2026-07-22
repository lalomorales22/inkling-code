# inkling-code

An agentic terminal client for [`thinkingmachines/Inkling`](https://huggingface.co/thinkingmachines/Inkling)
— tool use, a real permission system, skills, MCP, subagents, persistent
memory and sessions, all behind a glass-styled TUI.

Inkling is a 975B-parameter MoE that will not fit on your laptop. This runs it
remotely through Hugging Face Inference Providers and gives it tools that act on
your local machine, with an allow/deny policy engine deciding what runs
unattended.

```
╭──────────────────────────────────────────────────────╮
│ inkling  ·  glass interface                          │
│ Inkling:together                                     │
│ mode auto  ·  ~/code/myproject                       │
├╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌┤
│ 27 tools · 8 skills · session 20260722-141200        │
│ mcp ✓ github · 12 tools                              │
│ / commands · @ files · ! shell · ^T mode · /help     │
╰──────────────────────────────────────────────────────╯

› fix the failing test

  ⠹ thinking ······ 1.4s

  │
  ├▸ read_file    tests/test_stats.py
  │  38 lines                                      12ms
  ├▸ bash         pytest -q
  │  1 failed, 13 passed                           1.8s
  ├▸ edit_file    stats.py
  │  Edited stats.py                                2ms
  ├▸ bash         pytest -q
  │  14 passed                                     1.7s
  ╰──                               6 steps · 12.4s

Fixed median in stats.py — even-length lists took the upper middle
instead of averaging the two middles. Suite is green.
```

## What's inside

- **A completing input line** — type `/` for a live command menu with
  descriptions, `@` to complete file paths into your prompt, `!cmd` to run
  shell directly. History persists across sessions. `Ctrl-T` cycles the
  permission mode, `Ctrl-J` inserts a newline, and a status toolbar shows
  mode · model · context size · tool count · cwd.
- **Skills** — markdown playbooks the model pulls into context on demand.
  Eight ship builtin (`commit`, `review`, `debug`, `refactor`, `test`,
  `research`, `explore`, `init`); drop your own in `~/.inkling/skills/` or a
  project's `.inkling/skills/`. Run one with `/skill <name>`, or let the model
  load one itself via its `skill` tool when a task matches.
- **MCP client** — connect any Model Context Protocol server (stdio or HTTP)
  and its tools appear to the model as `mcp__server__tool`, policy-gated like
  everything else. `/mcp add github npx -y @modelcontextprotocol/server-github`
  and it's saved to `mcp.json` and connected.
- **Subagents** — a `task` tool that delegates self-contained work (broad
  searches, summarizing big trees) to a fresh-context subagent that returns
  only its findings.
- **Web** — `web_search` (DuckDuckGo, no key needed) plus `web_fetch`.
- **Memory** — a `remember` tool and `/remember` command append durable facts
  to `~/.inkling/memory.md`, loaded into every future session.
- **Sessions** — every session autosaves to `~/.inkling/sessions/`.
  `inkling -c` continues the last one, `/resume <id>` any older one,
  `/compact` summarizes a long conversation in place to free context,
  `/export` writes a markdown transcript.
- **Markdown-lite rendering** — headings, bullets, inline `code`/bold and
  fenced code render properly in the stream, still glass-styled.

## Why remote

Inkling is 975B params (41B active, 66 layers, 6-of-256 experts + 2 shared,
natively multimodal). On disk:

| Variant | Size |
|---|---|
| BF16 (original, 108 shards) | ~1.9 TB |
| Q8_0 GGUF | ~908 GB |
| UD-Q4_K_XL GGUF | ~587 GB |
| UD-IQ1_S GGUF (smallest) | ~270 GB |

The smallest quant is ~270 GB, and MoE routing faults in several GB from SSD
per token when it doesn't fit in RAM. So `inkling-code` talks to the hosted
model: **Together** (512k context) and **DeepInfra** (128k) both serve it live
behind HF's OpenAI-compatible router. Switch in-session with `/model`.

## Install

One command, macOS or Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/lalomorales22/inkling-code/main/install.sh | bash
```

Or from a clone:

```bash
git clone https://github.com/lalomorales22/inkling-code.git
cd inkling-code
./install.sh
```

The installer covers everything: installs [uv](https://docs.astral.sh/uv/) if
missing (uv fetches its own Python 3.13, so no system Python is needed), syncs
dependencies, asks for your Hugging Face token, and puts `inkling` and `ink`
launchers on your PATH so both commands work from any directory. Re-running it
updates an existing install; it never touches your shell config unless
`~/.local/bin` isn't already on your PATH.

You'll need a token with the **"Make calls to Inference Providers"**
permission from <https://huggingface.co/settings/tokens> — the installer
prompts for it (or reads `HF_TOKEN` from the environment).

<details>
<summary>Manual install instead</summary>

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/lalomorales22/inkling-code.git
cd inkling-code
uv sync
cp .env.example .env   # and put your real token in it
uv run python agent.py
```

</details>

## Usage

```bash
inkling                          # interactive session in this directory
inkling "fix the failing test"   # start with a prompt
inkling -c                       # continue the most recent session
inkling -r 20260722-1412         # resume a specific session (prefix ok)
inkling --safe                   # everything asks first
ink "quick one-shot question"    # plain chat, no tools, pipe-friendly
```

### Slash commands

| | |
|---|---|
| `/help` | commands, modes, tools and keys |
| `/mode [safe\|auto\|yolo]` | show or change the permission mode |
| `/model [together\|deepinfra\|auto]` | switch inference provider |
| `/tools` · `/skills` | what the model can use right now |
| `/skill <name> [args]` | run a skill playbook |
| `/mcp [add\|remove\|tools\|reload]` | manage MCP servers |
| `/plan` · `/compact` · `/clear` | plan, shrink or wipe the conversation |
| `/sessions` · `/resume <id>` | list and reopen saved sessions |
| `/export [path]` | write the conversation to markdown |
| `/memory` · `/remember <fact>` | persistent memory |
| `/init` | generate INKLING.md for this project |
| `/cwd` · `/tokens` · `/config` | environment and usage |

`!command` runs shell directly, no model involved. `@` completes file paths.

## Permission modes

| Mode | Behaviour |
|---|---|
| `safe` | every write and shell command asks first |
| `auto` | allowlisted commands run instantly; anything else asks |
| `yolo` | everything runs except the deny list |

The startup default lives in `config.json` as `default_mode` (shipped: `yolo` —
change it to `auto` if you want the gate back; `--safe`/`--auto`/`--yolo`
override per run).

**Deny rules apply in every mode, including `yolo`.** They cover actions that
can't be undone or that hand control of the machine to something else:

- `rm -rf` targeting `/`, `~`, `$HOME`, or top-level system dirs
- `mkfs`, `diskutil erase`, `dd of=/dev/…`
- `sudo` / `su`
- `curl … | sh` — piping the network into a shell
- exfiltrating `~/.ssh`, `~/.aws`, `.env`, `id_rsa` over curl/nc/scp
- `git push --force`, `history -c`, fork bombs

`auto` mode is deliberately careful about three things that look safe:

- **Compound commands are checked per segment.** `ls && rm -rf ~` is denied, not
  allowed on the strength of `ls`. Splitting is quote-aware.
- **Shell redirection counts as a file write.** `echo 'x' > main.py` asks,
  exactly like `write_file`. Descriptor plumbing (`2>&1`) and `> /dev/null` don't.
- **Inline interpreter code isn't allowlisted.** `python -c "…"` can do anything
  Python can. Running a *script* still auto-runs.

MCP tools are gated too: ones a server annotates read-only run automatically,
the rest ask (or run in `yolo`). Answering `a` at any prompt allows that tool
for the rest of the session.

## Tools

| Tool | Behaviour |
|---|---|
| `read_file`, `list_dir`, `search` (ripgrep), `glob` | always automatic |
| `web_fetch`, `web_search` | always automatic |
| `todo_write`, `skill`, `remember`, `task` | always automatic |
| `write_file` | governed by mode; shows the content |
| `edit_file` | governed by mode; shows a `-`/`+` diff |
| `bash` | governed by mode; shows the command |
| `mcp__*` | read-only annotated: automatic; otherwise governed by mode |

At each prompt: `y` once · `n` decline · `a` always allow that tool this session
· `q` abort. Declining is a signal, not an error — the model is told and adapts.

## MCP

Servers live in `mcp.json` (gitignored — it can hold env secrets; see
`mcp.json.example`):

```json
{
  "servers": {
    "github": {"transport": "stdio", "command": "npx",
               "args": ["-y", "@modelcontextprotocol/server-github"],
               "env": {"GITHUB_TOKEN": "ghp_…"}},
    "docs":   {"transport": "http", "url": "https://example.com/mcp"}
  }
}
```

Everything connects at launch (`--no-mcp` skips); `/mcp add`, `/mcp remove`,
`/mcp reload` manage it live, `/mcp tools` lists what's connected.

## Skills

A skill is a markdown file with frontmatter:

```markdown
---
name: deploy
description: Ship this service to staging safely
---
1. Run the test suite first…
```

Search order (later shadows earlier): builtin `skills/` → `~/.inkling/skills/`
→ `./.inkling/skills/`. The model sees the name+description list in its system
prompt and pulls the full body only when needed — context is spent on demand.

## Configuration

Allow/deny patterns are regexes in `config.json`, written on first run.
If the working directory contains `INKLING.md`, `AGENTS.md`, or `CLAUDE.md`,
the first 8 KB is appended to the system prompt (`/init` writes one for you).
Persistent memory (`~/.inkling/memory.md`) is appended too.

## Interface

The visual language is **glass**: terminal background shows through everywhere,
no filled blocks, thin blue hairlines as the only strong colour.

- **Latency spinner** with a live counter during the API round-trip
- **Activity rail** — tool calls hang off one continuous hairline, tinted by
  policy decision: blue auto-ran, amber asked, red blocked; subagent activity
  nests dimmer under its parent
- **Confirm panels** wrap rather than truncate — you must see the whole command
  you're approving
- **Paced reveal** types prose at ~1200 chars/sec but only sleeps while *ahead*
  of schedule, degrading to raw streaming under load
- **Status toolbar** under the input line: mode · model · context · tools · cwd

Flags: `--no-boot`, `--no-reveal`, `--plain`, `--no-mcp`.

Animation switches off when stdout isn't a tty, `NO_COLOR=1` and `TERM=dumb`
emit zero escape bytes, and the 256-colour palette upgrades to 24-bit when
`COLORTERM` advertises truecolor. No Nerd Font required.

## Security

`bash` runs with your full user permissions. **There is no sandbox.** The policy
engine is a pattern matcher, not a proof — it will not catch a genuinely novel
phrasing of something destructive.

- The shipped default mode is `yolo` for full autonomy. Inside a git repo,
  `git diff` is your undo — outside one, consider `default_mode: "auto"`.
- `web_fetch`/`web_search` content and MCP tool results are untrusted text.
  They are tagged as data in context and the system prompt says to report
  embedded directives rather than follow them — but in `yolo`, that instruction
  is the main thing between a malicious page and your shell. So is the deny
  list. Think before pointing it at hostile input.
- MCP servers you add run with your permissions and their tools do whatever
  they do — add servers you trust.

## Layout

```
agent.py        app state, agent loop, streaming, approval flow, slash commands
tools.py        tool registry and executors (fs, shell, web, memory, skills)
permissions.py  policy engine — modes, allow/deny matching, shell parsing
mcp_client.py   MCP servers: config, connections, tool bridging
skills.py       skill discovery (builtin · user · project)
sessions.py     autosave, resume, listing
repl.py         input line: completions, keybindings, toolbar
commands.py     slash-command catalog (menu + help render from it)
ui.py           glass interface — boot, spinner, rail, panels, markdown-lite
inkling.py      plain no-tools client, for one-shots and piping
config.json     editable mode default + allow/deny rules
mcp.json        your MCP servers (gitignored; see mcp.json.example)
skills/         builtin skill playbooks
install.sh      macOS/Linux installer — uv, deps, token, PATH launchers
```

## License

Apache-2.0. Inkling itself is Apache-2.0 and subject to Thinking Machines'
[acceptable use policy](https://thinkingmachines.ai/model-acceptable-use-policy).
