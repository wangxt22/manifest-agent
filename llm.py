#!/usr/bin/env python3
"""OpenAI-compatible chat client. Stdlib only, no dependencies.

Defaults to DeepSeek. Any endpoint exposing /chat/completions with function calling
works — set OPENAI_BASE_URL / MANIFEST_MODEL in .env to switch.
"""
import json
import os
import urllib.error
import urllib.request

_ROOT = os.path.dirname(os.path.abspath(__file__))


def _load_env():
    """Load this directory's .env, without overriding real environment variables."""
    path = os.path.join(_ROOT, ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

# DEEPSEEK_API_KEY is checked first so a DeepSeek key doesn't need renaming.
API_KEY = (
    os.environ.get("DEEPSEEK_API_KEY")
    or os.environ.get("OPENAI_API_KEY")
    or ""
)
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
MODEL = os.environ.get("MANIFEST_MODEL") or os.environ.get("TEXT_MODEL") or "deepseek-chat"

# Some relays sit behind a WAF that rejects urllib's default User-Agent with 403.
_UA = "curl/8.7.1"


def configured():
    """Whether a key is present — lets the UI show setup help instead of an error."""
    return bool(API_KEY)


def chat(messages, tools=None, max_tokens=2048, temperature=0.85, model=None):
    """POST /chat/completions. Returns the assistant message dict."""
    if not API_KEY:
        raise RuntimeError(
            "没有找到 API key。在 manifest-agent/.env 里写一行：\n"
            "  DEEPSEEK_API_KEY=sk-你的key\n"
            "（key 在 https://platform.deepseek.com/api_keys 申请）"
        )
    payload = {
        "model": model or MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": _UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:600]
        raise RuntimeError(f"API {e.code}: {detail}") from None
    if "error" in body:
        raise RuntimeError(f"API error: {body['error']}")
    return body["choices"][0]["message"]


def ask(prompt, system=None, **kw):
    """One-shot convenience call. Returns text."""
    msgs = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    return (chat(msgs, **kw).get("content") or "").strip()


if __name__ == "__main__":
    print(f"model={MODEL} base={BASE_URL}")
    print("->", repr(ask("只回复两个字：在线", max_tokens=32)))
