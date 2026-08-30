#!/usr/bin/env python3
"""OpenAI-compatible chat client (openai-next relay). Stdlib only, no dependencies.

Reads credentials from the repo-root .env (OPENAI_API_KEY / OPENAI_BASE_URL / TEXT_MODEL),
so this agent needs no config of its own.
"""
import json
import os
import urllib.error
import urllib.request

_ROOT = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_ROOT)


def _load_env():
    """Load .env from this dir then the repo root, without overriding real env vars."""
    for path in (os.path.join(_ROOT, ".env"), os.path.join(_PARENT, ".env")):
        if not os.path.exists(path):
            continue
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai-next.com/v1").rstrip("/")
API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL = os.environ.get("MANIFEST_MODEL") or os.environ.get("TEXT_MODEL") or "claude-opus-5"

# The relay's WAF rejects urllib's default User-Agent with 403, so send a real one.
_UA = "curl/8.7.1"


def chat(messages, tools=None, max_tokens=2048, temperature=0.85, model=None):
    """POST /chat/completions. Returns the assistant message dict."""
    if not API_KEY:
        raise RuntimeError(
            "未找到 OPENAI_API_KEY。请在项目根目录 .env 或 manifest-agent/.env 中设置。"
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
