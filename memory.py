"""Persistent user state. This is the part that makes it an agent rather than a chatbot.

Two stores, both plain JSON under ./data/:
  profile.json  — 愿望、被识别的限制性信念、情绪基线、练习偏好
  journal.jsonl — 逐条追加的感恩 / 共时性 / 进展 / 卡点

Design note: the full conversation history is NOT what gets injected each turn — a
compact rendering of this state is. That keeps long-term memory cheap and stops the
context from being dominated by old chat.
"""
import json
import os
import time

_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_ROOT, "data")

_EMPTY = {
    "name": None,
    "desires": [],          # {text, area, created, status, notes}
    "beliefs": [],          # {text, origin, created, status}
    "mood_log": [],         # {date, score, note}
    "practice_prefs": {},   # practice_id -> {count, last, liked}
    "created": None,
}


def _path(name):
    return os.path.join(DATA_DIR, name)


def _now():
    return time.strftime("%Y-%m-%d %H:%M")


def _today():
    return time.strftime("%Y-%m-%d")


def load():
    os.makedirs(DATA_DIR, exist_ok=True)
    p = _path("profile.json")
    if not os.path.exists(p):
        prof = json.loads(json.dumps(_EMPTY))
        prof["created"] = _today()
        return prof
    with open(p, encoding="utf-8") as f:
        prof = json.load(f)
    for k, v in _EMPTY.items():                      # forward-compat for new fields
        prof.setdefault(k, json.loads(json.dumps(v)))
    return prof


def save(prof):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(_path("profile.json"), "w", encoding="utf-8") as f:
        json.dump(prof, f, ensure_ascii=False, indent=2)


def add_desire(prof, text, area="其他"):
    for d in prof["desires"]:
        if d["text"] == text:
            return False
    prof["desires"].append(
        {"text": text, "area": area, "created": _today(), "status": "active", "notes": []}
    )
    return True


def add_belief(prof, text, origin=None):
    for b in prof["beliefs"]:
        if b["text"] == text:
            return False
    prof["beliefs"].append(
        {"text": text, "origin": origin, "created": _today(), "status": "identified"}
    )
    return True


def log_mood(prof, score, note=None):
    prof["mood_log"] = [m for m in prof["mood_log"] if m["date"] != _today()]
    prof["mood_log"].append({"date": _today(), "score": int(score), "note": note})
    prof["mood_log"] = prof["mood_log"][-90:]


def note_practice(prof, pid):
    rec = prof["practice_prefs"].setdefault(pid, {"count": 0, "last": None})
    rec["count"] += 1
    rec["last"] = _today()


def journal(kind, text, extra=None):
    """Append one entry. kind: gratitude | sync | progress | block | session"""
    os.makedirs(DATA_DIR, exist_ok=True)
    rec = {"ts": _now(), "date": _today(), "kind": kind, "text": text}
    if extra:
        rec.update(extra)
    with open(_path("journal.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def read_journal(kind=None, limit=None, days=None):
    p = _path("journal.jsonl")
    if not os.path.exists(p):
        return []
    out = []
    cutoff = None
    if days:
        cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - days * 86400))
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if kind and rec.get("kind") != kind:
                continue
            if cutoff and rec.get("date", "") < cutoff:
                continue
            out.append(rec)
    return out[-limit:] if limit else out


def streak(kind="gratitude"):
    """Consecutive days ending today (or yesterday) with an entry of this kind."""
    dates = {r["date"] for r in read_journal(kind)}
    if not dates:
        return 0
    n, t = 0, time.time()
    if _today() not in dates:
        t -= 86400                                    # allow today to be unfinished
        if time.strftime("%Y-%m-%d", time.localtime(t)) not in dates:
            return 0
    while time.strftime("%Y-%m-%d", time.localtime(t)) in dates:
        n += 1
        t -= 86400
    return n


def render(prof):
    """Compact state summary injected into the system prompt each turn."""
    lines = []
    if prof.get("name"):
        lines.append(f"称呼：{prof['name']}")

    active = [d for d in prof["desires"] if d["status"] == "active"]
    if active:
        lines.append("当前愿望：")
        for d in active[-6:]:
            note = f"（{d['notes'][-1]}）" if d["notes"] else ""
            lines.append(f"  - [{d['area']}] {d['text']}{note} · 记录于 {d['created']}")
    done = [d for d in prof["desires"] if d["status"] == "manifested"]
    if done:
        lines.append("已实现：" + "；".join(d["text"] for d in done[-4:]))

    open_beliefs = [b for b in prof["beliefs"] if b["status"] != "released"]
    if open_beliefs:
        lines.append("识别到的限制性信念：")
        for b in open_beliefs[-5:]:
            src = f"（来源：{b['origin']}）" if b.get("origin") else ""
            lines.append(f"  - {b['text']}{src}")

    if prof["mood_log"]:
        recent = prof["mood_log"][-7:]
        avg = sum(m["score"] for m in recent) / len(recent)
        lines.append(
            f"近 {len(recent)} 天情绪均值：{avg:.1f}/10（最近一次 {recent[-1]['score']}）"
        )

    gs = streak("gratitude")
    if gs:
        lines.append(f"感恩练习连续 {gs} 天")

    prefs = sorted(prof["practice_prefs"].items(), key=lambda kv: -kv[1]["count"])[:3]
    if prefs:
        lines.append("常做的练习：" + "、".join(f"{k}×{v['count']}" for k, v in prefs))

    recent_j = read_journal(limit=5, days=14)
    if recent_j:
        lines.append("最近的日志：")
        for r in recent_j:
            lines.append(f"  - [{r['date']} {r['kind']}] {r['text'][:60]}")

    return "\n".join(lines) if lines else "（这是一位新用户，还没有任何记录。）"
