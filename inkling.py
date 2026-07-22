#!/usr/bin/env python3
"""Chat with thinkingmachines/Inkling via Hugging Face Inference Providers.

The model is a 975B-param MoE (~1.9 TB in bf16), so it runs remotely on
Together / DeepInfra rather than on this machine. Routed through
https://router.huggingface.co/v1, which is OpenAI-compatible.

    ./inkling.py "explain MoE routing in two sentences"
    ./inkling.py -i chart.png "what's the trend here?"
    ./inkling.py                      # interactive REPL
"""

import argparse
import base64
import mimetypes
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

MODEL = "thinkingmachines/Inkling"
BASE_URL = "https://router.huggingface.co/v1"

# Append ":together" or ":deepinfra" to MODEL to pin one provider; bare model id
# lets the router pick. Both are listed live for this model.
PROVIDERS = ("auto", "together", "deepinfra")


def build_client() -> OpenAI:
    load_dotenv()
    token = os.getenv("HF_TOKEN")
    if not token:
        sys.exit(
            "HF_TOKEN is not set.\n\n"
            "Create a token with 'Make calls to Inference Providers' permission at\n"
            "  https://huggingface.co/settings/tokens\n\n"
            "then put it in this folder's .env file:\n"
            "  echo 'HF_TOKEN=hf_xxx' > .env\n"
        )
    return OpenAI(base_url=BASE_URL, api_key=token)


def image_part(ref: str) -> dict:
    """Build an image content block from a local path or an http(s) URL."""
    if ref.startswith(("http://", "https://")):
        url = ref
    else:
        path = Path(ref).expanduser()
        if not path.is_file():
            sys.exit(f"No such image: {path}")
        mime = mimetypes.guess_type(path)[0] or "image/png"
        b64 = base64.b64encode(path.read_bytes()).decode()
        url = f"data:{mime};base64,{b64}"
    return {"type": "image_url", "image_url": {"url": url}}


def user_message(text: str, images: list[str]) -> dict:
    if not images:
        return {"role": "user", "content": text}
    parts = [image_part(ref) for ref in images]
    parts.append({"type": "text", "text": text})
    return {"role": "user", "content": parts}


def stream_reply(client: OpenAI, model: str, messages: list[dict], temperature: float) -> str:
    """Print the reply as it arrives; return the full text."""
    chunks = []
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        stream=True,
    )
    for event in stream:
        if not event.choices:
            continue
        piece = event.choices[0].delta.content
        if piece:
            chunks.append(piece)
            print(piece, end="", flush=True)
    print()
    return "".join(chunks)


def main() -> None:
    ap = argparse.ArgumentParser(description="Chat with Inkling via HF Inference Providers.")
    ap.add_argument("prompt", nargs="*", help="prompt text; omit to enter the REPL")
    ap.add_argument("-i", "--image", action="append", default=[],
                    help="image path or URL (repeatable)")
    ap.add_argument("-s", "--system", help="system prompt")
    ap.add_argument("-t", "--temperature", type=float, default=0.7)
    ap.add_argument("-p", "--provider", choices=PROVIDERS, default="auto",
                    help="pin an inference provider (default: let the router choose)")
    args = ap.parse_args()

    client = build_client()
    model = MODEL if args.provider == "auto" else f"{MODEL}:{args.provider}"

    messages: list[dict] = []
    if args.system:
        messages.append({"role": "system", "content": args.system})

    if args.prompt:
        messages.append(user_message(" ".join(args.prompt), args.image))
        stream_reply(client, model, messages, args.temperature)
        return

    # No prompt given: interactive multi-turn session. Images are attached to
    # the first turn only, matching the one-shot behaviour above.
    print(f"Inkling ({model}) — Ctrl-D or 'exit' to quit\n")
    pending_images = args.image
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        if line in ("exit", "quit"):
            return
        messages.append(user_message(line, pending_images))
        pending_images = []
        print()
        reply = stream_reply(client, model, messages, args.temperature)
        messages.append({"role": "assistant", "content": reply})
        print()


if __name__ == "__main__":
    main()
