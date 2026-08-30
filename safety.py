#!/usr/bin/env python3
"""Crisis and risk screening. Runs before every model call — pattern matching only, no LLM.

Rationale: manifestation communities attract people in real distress, and
"你的现实是你吸引来的" is actively harmful to someone in crisis or grief. A hardcoded
tripwire is more reliable than trusting the model to notice.

Five tiers, each mapping to a distinct guardrail:
  crisis        — 自伤风险，中断正常回应
  distress      — 心理健康问题，禁止任何归因于用户的表达
  loss          — 丧失/创伤，最容易被「是你吸引来的」二次伤害的场景
  high_stakes   — 有现实后果的决定，不背书
  other_directed— 想改变他人，不做操控引导
"""
import re

# Tier 1 — immediate risk. Bypass the normal reply and surface help resources.
_CRISIS = [
    r"想死", r"不想活", r"活不下去", r"活着(没|无)意义", r"自杀", r"结束(自己的)?生命", r"了结自己",
    r"割腕", r"跳楼", r"跳下去", r"上吊", r"安眠药.*(全部|一整瓶|吞)",
    r"离开这个世界", r"没有我(会|更)好", r"报复社会", r"撑不(下去|住了)",
]

# Tier 2 — mental health. Softens tone, bans any "manifest harder" framing.
_DISTRESS = [
    r"抑郁", r"焦虑症", r"惊恐", r"双相", r"躁狂", r"确诊", r"精神科", r"心理医生", r"咨询师",
    r"停药", r"断药", r"抗抑郁", r"吃药", r"失眠(很久|好久|几个月)",
    r"崩溃", r"绝望", r"没有意义", r"废物", r"恨自己", r"自我厌恶", r"我是不是没救",
]

# Tier 3 — loss and trauma. The single most dangerous place for attribution language.
_LOSS = [
    r"(走了|去世|离世|没了|过世|病危|绝症|癌)", r"葬礼", r"临终",
    r"裁员", r"被裁", r"辞退", r"开除", r"失业", r"公司倒闭", r"破产",
    r"家暴", r"被打", r"性侵", r"强奸", r"骚扰", r"霸凌", r"欺凌", r"虐待",
    r"车祸", r"意外", r"流产", r"背叛", r"出轨", r"被骗(了|走)", r"诈骗",
]

# Tier 4 — real-world consequences. Never endorse the concrete action.
_HIGH_STAKES = [
    r"裸辞", r"辞职", r"离职", r"梭哈", r"全仓", r"重仓", r"加杠杆", r"借贷", r"网贷",
    r"贷款", r"(存款|积蓄|全部钱|所有钱).*(投|买|放)", r"全(投|押)进去", r"投资",
    r"彩票", r"赌", r"合约", r"币圈", r"追高", r"创业",
    r"离婚", r"打胎", r"怀孕", r"移民", r"退学",
    r"不吃药", r"停止治疗", r"保健品.*(代替|替代)", r"不去(医院|看医生)",
]

# Tier 5 — aimed at changing someone else.
_OTHER_DIRECTED = [
    r"(前男友|前女友|前任|他|她).*(回来|回头|联系我|找我|爱我|想我)",
    r"复合", r"挽回", r"让(我|你)?(他|她|ta|领导|老板|上司|妈|爸|父母|对方|前任).{0,4}(改变|态度|不要|同意|答应|喜欢|爱我|后悔|回来)",
    r"灵魂伴侣", r"特定人", r"sp显化", r"指定对象",
]

HELP_TEXT = """如果你正在考虑伤害自己，请先联系能立刻帮到你的人：

- 全国24小时心理援助热线 **12356**
- 希望24热线 **400-161-9995**（24小时）
- 紧急情况直接拨 **120** 或 **110**

这些电话是免费的，接线的是受过训练的真人。我会一直在这儿，但这一刻你需要的是他们，不是我。"""


def _hits(text, patterns):
    return [p for p in patterns if re.search(p, text)]


def screen(text):
    """Return the risk signals in one user message."""
    return {
        "crisis": bool(_hits(text, _CRISIS)),
        "distress": bool(_hits(text, _DISTRESS)),
        "loss": bool(_hits(text, _LOSS)),
        "high_stakes": bool(_hits(text, _HIGH_STAKES)),
        "other_directed": bool(_hits(text, _OTHER_DIRECTED)),
    }


def tier(flags):
    for k in ("crisis", "distress", "loss", "high_stakes", "other_directed"):
        if flags.get(k):
            return k
    return None


def advisory(flags):
    """Turn screen() output into an instruction block injected into the system prompt."""
    notes = []
    if flags["crisis"]:
        notes.append(
            "【最高优先级】用户可能有自伤风险。放弃本轮所有显化教学。"
            "先共情两三句，明确告诉对方值得被专业的人帮助，并原样给出下面的求助资源，"
            "然后只问一个问题：此刻身边有没有人可以陪着 ta。"
            "不要谈吸引力法则、不要谈信念、不要给练习。\n\n" + HELP_TEXT
        )
    if flags["distress"]:
        notes.append(
            "用户正处在明显的情绪痛苦或可能的心理健康问题中。本轮禁止任何形式的"
            "「是你自己吸引来的」「你的频率不够」「要保持正能量」表达——那是二次伤害。"
            "先完整地承接情绪，不要急着给方法。如果涉及诊断或用药，"
            "明确说明你不能替代医生，鼓励继续遵医嘱，绝不支持自行停药。"
        )
    if flags["loss"]:
        notes.append(
            "用户在讲述一件丧失、创伤或被伤害的经历。这是最需要克制的场景。"
            "绝对不要说这是 ta 吸引来的、是功课、是更好安排的铺垫、或和 ta 的念头有任何因果关系——"
            "哪怕 ta 自己这样问，也要温和而明确地否认这个归因。"
            "本轮的任务只是陪着 ta，不要给练习，不要转向显化教学。"
        )
    if flags["high_stakes"]:
        notes.append(
            "用户提到了有现实后果的重大决定。不要以任何方式鼓励、背书，"
            "也不要把它解读成「宇宙的信号」。可以陪 ta 看清背后的渴望和恐惧，"
            "但要明说：现实层面的取舍需要 ta 自己判断，最好和了解具体情况的人商量。"
            "绝不给出投资、医疗、法律层面的建议。"
        )
    if flags["other_directed"]:
        notes.append(
            "用户想显化的是他人的改变。不要提供任何针对特定对象的操控式引导。"
            "把焦点转回 ta 自己：ta 真正渴望的是什么感受（被爱、被认可、被看见），"
            "以及这份渴望除了这个特定的人还能从哪里得到满足。"
        )
    return "\n\n".join(notes)


if __name__ == "__main__":
    for s in [
        "我最近显化了一个新工作，好开心",
        "我想显化前男友回来找我",
        "我被裁员了，我做了那么多显化练习",
        "我妈上个月走了，是我没守住好念头吗",
        "我被确诊抑郁症了，是不是因为我念头太负面",
        "要不要把存款全投进去",
        "我真的不想活了",
    ]:
        print(f"[{(tier(screen(s)) or 'ok'):14}] {s}")
