"""The agent: system prompt assembly + one turn of the tool-use loop."""
import json

import knowledge
import llm
import memory
import safety

PERSONA = """你是「显化陪伴者」，一个陪用户长期练习显化的伙伴。

你的定位：你不是导师，不是灵性权威，也不是许愿池。你是那个记得住用户所有愿望和卡点、
会在 ta 泄气的时候提醒 ta 走了多远、也会在 ta 陷入幻想时温和地问一句「那你现在最想做的
一小步是什么」的人。

你相信显化的核心不是向宇宙下订单，而是：看清自己真正想要什么、松掉挡在中间的信念、
然后带着那份确定感去生活。所有练习都服务于这三件事。

重要：你手上有一份记录着这位用户的资料。**主动使用它**——提起 ta 上次说的卡点，
对比 ta 一个月前的情绪，指出 ta 反复出现的模式。这是你和一个通用聊天机器人最大的区别。"""

TOOL_POLICY = """关于记录工具：

自然对话中顺手记录，不要打断节奏，也不要向用户报告「我已经调用了工具」。
只记录用户真实说出的内容，不要替 ta 归纳出 ta 没说过的信念。
一轮对话通常 0-2 次记录，不要为了记录而记录。"""


def build_system(prof, flags):
    parts = [
        PERSONA,
        knowledge.STYLE,
        knowledge.GUARDRAILS,
        "## 你可以带用户做的练习\n\n" + knowledge.practice_book(),
        TOOL_POLICY,
        "## 这位用户的资料\n\n" + memory.render(prof),
    ]
    adv = safety.advisory(flags)
    if adv:
        parts.append("## 本轮的特别指示（优先于以上所有内容）\n\n" + adv)
    return "\n\n---\n\n".join(parts)


def respond(user_text, history, prof, max_rounds=4):
    """One user turn. Returns (reply_text, updated_history). Mutates and saves prof."""
    import tools                                    # imported here to keep module deps flat

    flags = safety.screen(user_text)
    system = build_system(prof, flags)

    history = history + [{"role": "user", "content": user_text}]
    # A crisis turn must not be diluted by memory writes or practice suggestions.
    active_tools = None if flags["crisis"] else tools.SCHEMAS

    for _ in range(max_rounds):
        msgs = [{"role": "system", "content": system}] + history
        msg = llm.chat(msgs, tools=active_tools, temperature=0.6 if flags["crisis"] else 0.85)
        history.append(msg)

        calls = msg.get("tool_calls")
        if not calls:
            memory.save(prof)
            return (msg.get("content") or "").strip(), history

        history.extend(tools.run_calls(calls, prof))
        memory.save(prof)

    # Ran out of rounds mid tool-loop: ask for a plain answer.
    msgs = [{"role": "system", "content": system}] + history
    msg = llm.chat(msgs, temperature=0.85)
    history.append(msg)
    return (msg.get("content") or "").strip(), history


def trim(history, keep=24):
    """Drop old turns without orphaning a tool result from its assistant tool_calls
    message — the API rejects a role=tool message that has no matching parent."""
    if len(history) <= keep:
        return history
    cut = len(history) - keep
    while cut < len(history) and history[cut].get("role") in ("tool", "assistant"):
        cut += 1                                     # advance to the next clean user turn
    return history[cut:]


def daily_prompt(prof, slot="morning"):
    """Proactive check-in. slot: morning (设定意图) | evening (感恩复盘)."""
    state = memory.render(prof)
    if slot == "morning":
        task = (
            "现在是早晨。基于这位用户的资料，写一段简短的早间问候：一句呼应 ta 当下处境的话，"
            "加一个今天可以带着的意图或一个 10 分钟内能做完的小动作。不要列清单，不要说教。"
            "3-4 句以内。"
        )
    else:
        task = (
            "现在是晚上。基于这位用户的资料，写一段简短的睡前收尾：温和地邀请 ta 说说今天，"
            "如果 ta 最近在做感恩练习就提一下连续天数。不要追问太多，只问一个问题。3-4 句以内。"
        )
    system = "\n\n---\n\n".join(
        [PERSONA, knowledge.STYLE, knowledge.GUARDRAILS, "## 这位用户的资料\n\n" + state]
    )
    return llm.ask(task, system=system, max_tokens=400)


def weekly_review(prof):
    """Look back over the past week using journal + profile."""
    entries = memory.read_journal(days=7)
    dump = "\n".join(f"[{e['date']} {e['kind']}] {e['text']}" for e in entries) or "（这一周没有日志记录）"
    system = "\n\n---\n\n".join(
        [PERSONA, knowledge.STYLE, knowledge.GUARDRAILS, "## 这位用户的资料\n\n" + memory.render(prof)]
    )
    task = f"""这是用户过去 7 天的日志：

{dump}

写一份简短的周回顾，包含四部分，每部分 1-3 句：
1. 这周实际发生了什么（具体，不要空话）
2. 你注意到的一个模式（重复出现的情绪、话题或卡点）
3. 一个你想温和指出的盲点（如果没有就跳过这条）
4. 下周可以试的一件事（只一件，具体到能立刻做）

如果日志很少，就说实话，并邀请 ta 下周多记一点，不要硬凑内容。"""
    return llm.ask(task, system=system, max_tokens=900)
