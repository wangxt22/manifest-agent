"""Tool definitions the model can call to write into persistent memory.

The agent decides when to record something; these functions are the only path that
mutates state. Every handler returns a short string that goes back to the model as
the tool result.
"""
import json

import memory

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "remember_desire",
            "description": "用户明确说出一个想要显化的目标时调用。不要为随口一提或假设性的内容调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "愿望内容，用用户自己的话概括，一句话"},
                    "area": {
                        "type": "string",
                        "enum": ["爱情", "金钱", "事业", "健康", "关系", "自我", "其他"],
                    },
                },
                "required": ["text", "area"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember_belief",
            "description": "识别出一个限制性信念时调用（通常在追问几层之后，用户自己说出「原来我一直觉得…」）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "信念本身，尽量用用户的原话，第一人称"},
                    "origin": {"type": "string", "description": "如果用户提到了来源（某段经历、某个人），写在这里"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_entry",
            "description": "记录一条日志。用户分享感恩的事、共时性迹象、进展或卡住的地方时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["gratitude", "sync", "progress", "block"],
                        "description": "gratitude=感恩 sync=共时性迹象 progress=进展 block=卡点",
                    },
                    "text": {"type": "string"},
                },
                "required": ["kind", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_mood",
            "description": "用户描述了自己的状态、你能判断出情绪水平时调用。1=极度低落 10=状态很好。",
            "parameters": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "minimum": 1, "maximum": 10},
                    "note": {"type": "string"},
                },
                "required": ["score"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_manifested",
            "description": "用户报告某个愿望实现了时调用。",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string", "description": "匹配已记录愿望的关键词即可"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "note_practice",
            "description": "带用户做完一个练习后调用，用于记录 ta 的练习偏好。",
            "parameters": {
                "type": "object",
                "properties": {
                    "practice_id": {
                        "type": "string",
                        "enum": [
                            "affirmation", "gratitude", "scripting", "visualization",
                            "release", "belief_dig", "inspired_action", "detachment", "sync_log",
                        ],
                    }
                },
                "required": ["practice_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_name",
            "description": "用户告诉你怎么称呼 ta 时调用。",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
]


def dispatch(name, args, prof):
    """Run one tool call. Mutates prof in place; caller is responsible for save()."""
    if name == "remember_desire":
        added = memory.add_desire(prof, args["text"], args.get("area", "其他"))
        return "已记下这个愿望。" if added else "这个愿望之前已经记过了。"

    if name == "remember_belief":
        added = memory.add_belief(prof, args["text"], args.get("origin"))
        return "已记下这个信念。" if added else "这个信念之前已经记过了。"

    if name == "log_entry":
        memory.journal(args["kind"], args["text"])
        if args["kind"] == "gratitude":
            n = memory.streak("gratitude")
            return f"已记录。感恩练习已连续 {n} 天。"
        return "已记录。"

    if name == "log_mood":
        memory.log_mood(prof, args["score"], args.get("note"))
        return "已记录情绪。"

    if name == "mark_manifested":
        kw = args["text"]
        for d in prof["desires"]:
            if kw in d["text"] or d["text"] in kw:
                d["status"] = "manifested"
                memory.journal("progress", f"实现了：{d['text']}")
                return f"已标记为实现：{d['text']}"
        memory.journal("progress", f"实现了：{kw}")
        return "没有找到匹配的已记录愿望，已作为进展记录下来。"

    if name == "note_practice":
        memory.note_practice(prof, args["practice_id"])
        return "已记录练习。"

    if name == "set_name":
        prof["name"] = args["name"]
        return f"好，以后称呼 {args['name']}。"

    return f"未知工具：{name}"


def run_calls(tool_calls, prof):
    """Execute a batch of tool_calls from one assistant message → tool result messages."""
    results = []
    for tc in tool_calls:
        fn = tc.get("function", {})
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        try:
            out = dispatch(fn.get("name", ""), args, prof)
        except Exception as e:                              # a bad tool call must not kill the turn
            out = f"记录失败：{e}"
        results.append(
            {"role": "tool", "tool_call_id": tc.get("id", ""), "content": out}
        )
    return results
