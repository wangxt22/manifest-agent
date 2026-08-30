#!/usr/bin/env python3
"""Offline test of the tool-use loop, with llm.chat stubbed out.

Verifies the agent survives a multi-round tool exchange and that state actually lands
on disk — the part that would otherwise only be testable with a live API key.
"""
import json
import os
import shutil
import sys

import agent
import llm
import memory


def fake_chat(script):
    """Return a chat() stand-in that replays `script` one message per call."""
    calls = {"n": 0}

    def _chat(messages, tools=None, **kw):
        i = calls["n"]
        calls["n"] += 1
        # Sanity: tool results must be threaded back in as role=tool messages.
        if i > 0:
            assert any(m.get("role") == "tool" for m in messages), "tool 结果没有回传给模型"
        return script[i]

    return _chat, calls


def main():
    real_dir, real_chat = memory.DATA_DIR, llm.chat
    memory.DATA_DIR = os.path.join(real_dir, "_looptest")
    shutil.rmtree(memory.DATA_DIR, ignore_errors=True)

    script = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {
                        "name": "set_name",
                        "arguments": json.dumps({"name": "小雨"}, ensure_ascii=False),
                    },
                },
                {
                    "id": "c2",
                    "type": "function",
                    "function": {
                        "name": "remember_desire",
                        "arguments": json.dumps(
                            {"text": "换一份能发挥创造力的工作", "area": "事业"}, ensure_ascii=False
                        ),
                    },
                },
            ],
        },
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "c3",
                    "type": "function",
                    "function": {
                        "name": "log_entry",
                        "arguments": json.dumps(
                            {"kind": "block", "text": "投简历就焦虑，然后拖着不投"}, ensure_ascii=False
                        ),
                    },
                }
            ],
        },
        {"role": "assistant", "content": "记住了，小雨。那份「投出去就焦虑」的感觉，是怕被拒绝，还是怕真的成了？"},
    ]

    llm.chat, calls = fake_chat(script)
    try:
        prof = memory.load()
        reply, history = agent.respond(
            "你可以叫我小雨。我想换一份能发挥创造力的工作，但每次投简历就焦虑，然后就拖着不投了。", [], prof
        )

        assert calls["n"] == 3, f"期望 3 次模型调用，实际 {calls['n']}"
        assert reply.startswith("记住了"), f"回复不对：{reply!r}"

        saved = memory.load()                                  # re-read from disk
        assert saved["name"] == "小雨", "name 没落盘"
        assert len(saved["desires"]) == 1, "desire 没落盘"
        blocks = memory.read_journal("block")
        assert len(blocks) == 1, "journal 没落盘"

        tool_msgs = [m for m in history if m.get("role") == "tool"]
        assert len(tool_msgs) == 3, f"tool 结果消息数不对：{len(tool_msgs)}"

        print("✓ 工具循环：3 轮，工具结果正确回传")
        print("✓ 状态落盘：", memory.render(saved).replace("\n", " | "))

        # Crisis path: tools must be disabled entirely.
        llm.chat, calls2 = fake_chat([{"role": "assistant", "content": "我在。请先打 12356。"}])
        seen = {}
        orig = llm.chat

        def spy(messages, tools=None, **kw):
            seen["tools"] = tools
            seen["system"] = messages[0]["content"]
            return orig(messages, tools=tools, **kw)

        llm.chat = spy
        agent.respond("我真的不想活了", [], memory.load())
        assert seen["tools"] is None, "危机轮次没有禁用工具"
        assert "12356" in seen["system"], "危机轮次没有注入求助资源"
        print("✓ 危机路径：工具已禁用，求助资源已注入")

        print("\n✓ 全部通过")
        return 0
    finally:
        llm.chat = real_chat
        shutil.rmtree(memory.DATA_DIR, ignore_errors=True)
        memory.DATA_DIR = real_dir


if __name__ == "__main__":
    sys.exit(main())
