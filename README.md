# inkling-code

An agentic terminal chatbot for [`thinkingmachines/Inkling`](https://huggingface.co/thinkingmachines/Inkling)
— tool use, a real permission system, and a glass-styled TUI.

Inkling is a 975B-parameter MoE that will not fit on your laptop. This runs it
remotely through Hugging Face Inference Providers and gives it tools that act on
your local machine, with an allow/deny policy engine deciding what runs
unattended.

```
╭──────────────────────────────────────────────────────╮
│ inkling  ·  glass interface                          │
│ Inkling:together                                     │
│ mode auto  ·  ~/code/myproject                       │
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
  │  ━━━━━━━━━━━━━━━━━━  3/3
  │  ✓ Reproduce the failure
  │  ✓ Fix median for even-length input
  │  ✓ Re-run the suite
  ╰──                               6 steps · 12.4s

Fixed median in stats.py — even-length lists took the upper middle
instead of averaging the two middles. Suite is green.
```

## Why remote

Inkling is 975B params (41B active, 66 layers, 6-of-256 experts + 2 shared,
natively multimodal). On disk:

| Variant | Size |
|---|---|
| BF16 (original, 108 shards) | ~1.9 TB |
| Q8_0 GGUF | ~908 GB |
| UD-Q4_K_XL GGUF | ~587 GB |
| UD-Q2_K_XL GGUF | ~317 GB |
| UD-IQ1_S GGUF (smallest) | ~270 GB |

The smallest quant is ~270 GB. Even where that fits on disk, MoE routing touches
~6 random experts per layer per token across 66 layers, so nearly every token
faults in several GB from SSD — seconds per token, at 1-bit quality. Running
this locally on Apple Silicon realistically wants a 512 GB M3/M4 Ultra.

So `inkling-code` talks to the hosted model. **Together** (512k context,
structured output) and **DeepInfra** (128k) both serve it live, behind HF's
OpenAI-compatible router.

## Install

Requires [uv](https://docs.astral.sh/uv/) and Python 3.13+.

```bash
git clone https://github.com/lalomorales22/inkling-code.git
cd inkling-code
uv sync
```

Create a token with the **"Make calls to Inference Providers"** permission at
<https://huggingface.co/settings/tokens>, then:

```bash
cp .env.example .env   # and put your real token in it
```

> A token cached in `~/.cache/huggingface/token` by `huggingface-cli login` may
> be a short-lived OAuth token, which 401s against the router. Use a real access
> token.

Optionally add shell functions so it works from any directory:

```bash
cat >> ~/.zshrc <<'EOF'
inkling() { uv run --project ~/path/to/inkling-code python ~/path/to/inkling-code/agent.py "$@"; }
ink()     { uv run --project ~/path/to/inkling-code python ~/path/to/inkling-code/inkling.py "$@"; }
EOF
```

## Usage

```bash
inkling                          # safe mode: everything asks first
inkling --auto                   # allowlisted commands run unprompted
inkling --auto "fix the failing test"
inkling --yolo                   # everything except hard-denied actions
ink "quick one-shot question"    # plain chat, no tools, pipe-friendly
```

It operates on the directory you launch it from.

In-session: `/help` `/mode` `/clear` `/plan` `/cwd` `/tokens` `/config` `/exit`

## Permission modes

| Mode | Behaviour |
|---|---|
| `safe` (default) | every write and shell command asks first |
| `auto` | allowlisted commands run instantly; anything else asks |
| `yolo` | everything runs except the deny list |

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
  allowed on the strength of `ls`. Splitting is quote-aware, so
  `python -c 'import x; run()'` isn't mangled into bogus segments.
- **Shell redirection counts as a file write.** `echo 'x' > main.py` asks,
  exactly like `write_file` — otherwise allowlisting `echo` would silently
  bypass the write gate. Descriptor plumbing (`2>&1`) and `> /dev/null` don't.
- **Inline interpreter code isn't allowlisted.** `python -c "…"` can do anything
  Python can, so allowlisting `python` must not extend to it. Running a *script*
  still auto-runs.

The first two were found by watching the model route around earlier versions of
the rules — without being adversarial about it.

## Tools

| Tool | Behaviour |
|---|---|
| `read_file`, `list_dir`, `search` (ripgrep), `glob` | always automatic |
| `web_fetch` | always automatic |
| `todo_write` | always automatic; renders a live plan |
| `write_file` | governed by mode; shows the content |
| `edit_file` | governed by mode; shows a `-`/`+` diff |
| `bash` | governed by mode; shows the command |

At each prompt: `y` once · `n` decline · `a` always allow that tool this session
· `q` abort. Declining is a signal, not an error — the model is told and adapts.

## Configuration

Allow and deny patterns are regexes in `config.json`, written on first run.
`/config` prints the path.

```json
{ "bash": { "allow": ["^docker (ps|logs|compose)\\b", "^terraform plan\\b"] } }
```

If the working directory contains `INKLING.md`, `AGENTS.md`, or `CLAUDE.md`, the
first 8 KB is appended to the system prompt as project instructions.

## Interface

The visual language is **glass**: terminal background shows through everywhere,
no filled blocks, thin blue hairlines as the only strong colour.

- **Latency spinner** with a live counter during the API round-trip
- **Activity rail** — tool calls hang off one continuous hairline, tinted by
  policy decision: blue auto-ran, amber asked, red blocked
- **Confirm panels** wrap rather than truncate — you must see the whole command
  you're approving
- **Paced reveal** types prose at ~1200 chars/sec but only sleeps while *ahead*
  of schedule, degrading to raw streaming under load instead of building a backlog

Flags: `--no-boot`, `--no-reveal`, `--plain`.

Animation switches off when stdout isn't a tty, `NO_COLOR=1` and `TERM=dumb`
emit zero escape bytes, and the 256-colour palette upgrades to 24-bit when
`COLORTERM` advertises truecolor. Uses only box-drawing, braille and geometric
glyphs — no Nerd Font required.

## Security

`bash` runs with your full user permissions. **There is no sandbox.** The policy
engine is a pattern matcher, not a proof — it will not catch a genuinely novel
phrasing of something destructive.

- `auto` is a good default inside a git repo, where `git diff` is your undo.
- `yolo` still blocks the deny list, but everything else runs unseen. Use it in
  scratch directories, not `$HOME`.
- `web_fetch` + `bash` deserves thought: a fetched page is untrusted text, and an
  agent that can run commands is a useful target for injected instructions.
  Fetched content is tagged as data in context and the system prompt says to
  report embedded directives rather than follow them — but in `yolo` that
  instruction is the only thing between a malicious page and your shell.

## Layout

```
agent.py        agent loop, streaming, approval flow, slash commands
tools.py        tool schemas and executors
permissions.py  policy engine — modes, allow/deny matching, shell parsing
ui.py           glass interface — boot, spinner, rail, panels, reveal
inkling.py      plain no-tools client, for one-shots and piping
config.json     editable allow/deny rules
```

## License

Apache-2.0. Inkling itself is Apache-2.0 and subject to Thinking Machines'
[acceptable use policy](https://thinkingmachines.ai/model-acceptable-use-policy).
