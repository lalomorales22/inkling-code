#!/usr/bin/env bash
# inkling installer — macOS and Linux.
#
# Installs uv if missing (which brings its own Python 3.13), syncs the app's
# dependencies, sets up your Hugging Face token, and puts `inkling` and `ink`
# launchers on your PATH so the app opens from any directory.
#
# Run it either way:
#   from a clone :  ./install.sh
#   from nowhere :  curl -fsSL https://raw.githubusercontent.com/lalomorales22/inkling-code/main/install.sh | bash
#
# Re-running is safe: it updates the app and rewrites the launchers.

set -euo pipefail

REPO_URL="https://github.com/lalomorales22/inkling-code.git"
CLONE_DIR="$HOME/.inkling/app"
BIN_DIR="$HOME/.local/bin"

# ── glass-ish output, degrading to plain when not a tty ─────────────────────
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    BLUE=$'\033[38;5;39m'; GLOW=$'\033[38;5;45m'; MUTE=$'\033[38;5;242m'
    OK=$'\033[38;5;78m'; WARN=$'\033[38;5;214m'; STOP=$'\033[38;5;203m'
    BOLD=$'\033[1m'; OFF=$'\033[0m'
else
    BLUE=""; GLOW=""; MUTE=""; OK=""; WARN=""; STOP=""; BOLD=""; OFF=""
fi

say()  { printf '%s\n' "${BLUE}│${OFF} $*"; }
ok()   { printf '%s\n' "${BLUE}│${OFF} ${OK}✓${OFF} $*"; }
warn() { printf '%s\n' "${BLUE}│${OFF} ${WARN}!${OFF} $*"; }
die()  { printf '%s\n' "${BLUE}│${OFF} ${STOP}✗ $*${OFF}" >&2; exit 1; }

printf '%s\n' "${BLUE}╭──────────────────────────────────────────╮${OFF}"
printf '%s\n' "${BLUE}│${OFF} ${GLOW}${BOLD}inkling${OFF}${MUTE}  ·  installer${OFF}                    ${BLUE}│${OFF}"
printf '%s\n' "${BLUE}╰──────────────────────────────────────────╯${OFF}"
printf '%s\n' "${BLUE}│${OFF}"

# ── platform ────────────────────────────────────────────────────────────────
case "$(uname -s)" in
    Darwin) PLATFORM="macOS" ;;
    Linux)  PLATFORM="Linux" ;;
    *)      die "unsupported platform: $(uname -s) (macOS and Linux only)" ;;
esac
ok "platform: $PLATFORM"

command -v git  >/dev/null 2>&1 || die "git is required — install it and re-run"
command -v curl >/dev/null 2>&1 || die "curl is required — install it and re-run"

# ── locate or fetch the app ─────────────────────────────────────────────────
# If this script sits inside a checkout, install from there; otherwise clone.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd || true)"
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/agent.py" ] && [ -f "$SCRIPT_DIR/pyproject.toml" ]; then
    APP_DIR="$SCRIPT_DIR"
    ok "installing from checkout: ${MUTE}$APP_DIR${OFF}"
elif [ -d "$CLONE_DIR/.git" ]; then
    APP_DIR="$CLONE_DIR"
    say "updating existing install…"
    git -C "$APP_DIR" pull --ff-only >/dev/null 2>&1 && ok "updated ${MUTE}$APP_DIR${OFF}" \
        || warn "could not fast-forward $APP_DIR — using it as-is"
else
    APP_DIR="$CLONE_DIR"
    say "cloning inkling…"
    mkdir -p "$(dirname "$CLONE_DIR")"
    git clone --depth 1 "$REPO_URL" "$CLONE_DIR" >/dev/null 2>&1 \
        || die "clone failed: $REPO_URL"
    ok "cloned to ${MUTE}$APP_DIR${OFF}"
fi

# ── uv (brings its own Python 3.13, no system Python needed) ────────────────
# Remember the PATH the user's shell actually had — the export below is only
# for this script's own use, and must not fool the on-PATH check later.
ORIG_PATH="$PATH"
export PATH="$BIN_DIR:$HOME/.cargo/bin:$PATH"
if command -v uv >/dev/null 2>&1; then
    ok "uv $(uv --version 2>/dev/null | awk '{print $2}')"
else
    say "installing uv (https://astral.sh/uv)…"
    curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 \
        || die "uv install failed — see https://docs.astral.sh/uv/getting-started/installation/"
    export PATH="$BIN_DIR:$HOME/.cargo/bin:$PATH"
    command -v uv >/dev/null 2>&1 || die "uv installed but not on PATH — open a new shell and re-run"
    ok "uv installed"
fi

say "syncing dependencies (first run may fetch Python 3.13)…"
(cd "$APP_DIR" && uv sync >/dev/null 2>&1) || die "uv sync failed — run 'uv sync' in $APP_DIR to see why"
ok "dependencies ready"

# ── Hugging Face token ──────────────────────────────────────────────────────
ENV_FILE="$APP_DIR/.env"
if [ -f "$ENV_FILE" ] && grep -q "^HF_TOKEN=hf_" "$ENV_FILE" 2>/dev/null; then
    ok "HF token already configured"
elif [ -n "${HF_TOKEN:-}" ]; then
    printf 'HF_TOKEN=%s\n' "$HF_TOKEN" > "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    ok "HF token taken from environment"
elif [ -t 0 ]; then
    printf '%s\n' "${BLUE}│${OFF}"
    say "inkling needs a Hugging Face token with the"
    say "${BOLD}\"Make calls to Inference Providers\"${OFF} permission:"
    say "${MUTE}https://huggingface.co/settings/tokens${OFF}"
    printf '%s' "${BLUE}│${OFF} ${WARN}›${OFF} paste token (or Enter to skip): "
    read -rs TOKEN
    printf '\n'
    if [ -n "$TOKEN" ]; then
        printf 'HF_TOKEN=%s\n' "$TOKEN" > "$ENV_FILE"
        chmod 600 "$ENV_FILE"
        ok "token saved to ${MUTE}$ENV_FILE${OFF}"
    else
        warn "skipped — add it later:  echo 'HF_TOKEN=hf_xxx' > $ENV_FILE"
    fi
else
    warn "no token configured — add one:  echo 'HF_TOKEN=hf_xxx' > $ENV_FILE"
fi

# ── launchers on PATH ───────────────────────────────────────────────────────
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/inkling" <<LAUNCHER
#!/usr/bin/env bash
# inkling — agentic terminal client (installed by install.sh)
exec uv run --project "$APP_DIR" python "$APP_DIR/agent.py" "\$@"
LAUNCHER
chmod +x "$BIN_DIR/inkling"

cat > "$BIN_DIR/ink" <<LAUNCHER
#!/usr/bin/env bash
# ink — plain one-shot Inkling chat, no tools (installed by install.sh)
exec uv run --project "$APP_DIR" python "$APP_DIR/inkling.py" "\$@"
LAUNCHER
chmod +x "$BIN_DIR/ink"
ok "launchers: ${MUTE}$BIN_DIR/inkling · $BIN_DIR/ink${OFF}"

# ── make sure BIN_DIR is on PATH in future shells ───────────────────────────
case ":$ORIG_PATH:" in
    *":$BIN_DIR:"*) ON_PATH=1 ;;
    *)              ON_PATH=0 ;;
esac

RC_FILE=""
case "$(basename "${SHELL:-}")" in
    zsh)  RC_FILE="$HOME/.zshrc" ;;
    bash) RC_FILE="$HOME/.bashrc" ;;
    *)    RC_FILE="$HOME/.profile" ;;
esac

PATH_LINE="export PATH=\"\$HOME/.local/bin:\$PATH\""
if [ "$ON_PATH" -eq 0 ]; then
    if ! grep -qsF '.local/bin' "$RC_FILE" 2>/dev/null; then
        printf '\n# added by inkling installer\n%s\n' "$PATH_LINE" >> "$RC_FILE"
        ok "added ~/.local/bin to PATH in ${MUTE}$RC_FILE${OFF}"
    fi
    NEED_RELOAD=1
else
    ok "~/.local/bin already on PATH"
    NEED_RELOAD=0
fi

# ── done ────────────────────────────────────────────────────────────────────
printf '%s\n' "${BLUE}│${OFF}"
printf '%s\n' "${BLUE}╰──${OFF} ${OK}installed${OFF}"
printf '%s\n' ""
if [ "$NEED_RELOAD" -eq 1 ]; then
    printf '%s\n' "  open a new terminal (or:  source $RC_FILE ), then:"
fi
printf '%s\n' "  ${GLOW}inkling${OFF}   ${MUTE}agentic session in the current directory${OFF}"
printf '%s\n' "  ${GLOW}ink${OFF}       ${MUTE}quick one-shot chat, pipe-friendly${OFF}"
printf '%s\n' ""
