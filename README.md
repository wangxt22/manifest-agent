# 显化陪伴者 · Manifest Agent

一个陪用户长期做显化练习的 agent。0-1 的骨架已经跑通，v0/v1 完成。

和「显化 App」的区别：App 是工具，用户自己填；这个 agent 记得住用户的愿望、卡点、
情绪曲线，会主动提起上次聊到哪里，也会在用户陷入幻想或危险想法时把话拉回来。

## 快速开始

```bash
cd manifest-agent
python3 evals.py dry      # 离线自检，不花钱
python3 test_loop.py      # 工具循环测试，不花钱
python3 cli.py            # 开始对话（需要可用的 API key）
```

凭据从上一级目录的 `.env` 读取（`OPENAI_API_KEY` / `OPENAI_BASE_URL` / `TEXT_MODEL`），
也可以在 `manifest-agent/.env` 单独覆盖。用 `MANIFEST_MODEL` 指定本 agent 专用模型。

> 当前仓库根 `.env` 里的 openai-next key 已失效（401 Invalid token），
> 换一个有效 key 即可直接对话；离线测试不受影响。

## 命令

| 命令 | 作用 |
|---|---|
| `python3 cli.py` | 对话（`/state` 看记录 · `/review` 周回顾 · `/quit`） |
| `python3 cli.py morning` | 早间意图设定 |
| `python3 cli.py evening` | 晚间感恩收尾 |
| `python3 cli.py review` | 基于近 7 天日志的周回顾 |
| `python3 cli.py state` | 打印已积累的用户资料 |
| `python3 evals.py list/dry/run` | 场景清单 / 离线自检 / 真实跑分 |

## 结构

```
knowledge.py   方法论层：9 个练习 SOP + 风格层 + 硬约束
safety.py      五级风险筛查（正则，不走模型）
memory.py      profile.json + journal.jsonl，长期状态
tools.py       模型可调用的 7 个记录工具
agent.py       system prompt 组装 + 工具循环
cli.py         终端界面
evals.py       30 个回归场景
test_loop.py   打桩测试工具循环与落盘
```

## 三个关键设计

**语料是蒸馏的，不是检索的。** 显化博文重复度极高，切片进向量库检索出来是一堆同义
鸡汤。[knowledge.py](manifest-agent/knowledge.py) 里的 9 个练习是「触发场景 / 步骤 /
常见误区 / 做对了的迹象」四段式 SOP，全部写进 system prompt，约 2900 字。
要加你收集的博主内容，就蒸馏成同样的形状追加进 `PRACTICES`，不要贴原文——
方法论本身是公共领域的，原文表达不是。

**每轮注入的是状态摘要，不是聊天记录。** [memory.py](manifest-agent/memory.py) 的
`render()` 把愿望、限制性信念、情绪均值、连续打卡、近期日志压成十几行。对话历史只留
最近 24 条，长期记忆完全靠 profile 承载。这样聊三个月上下文也不会爆。

**安全筛查在模型之前，用正则。** 这个品类的用户里有相当比例正在低谷。
「你的现实是你吸引来的」对刚失去母亲或刚被裁员的人是二次伤害，不能指望模型每次都想起来。
[safety.py](manifest-agent/safety.py) 分五级：

- `crisis` — 自伤风险。**直接禁用所有工具**，注入求助热线，本轮不谈任何显化内容
- `distress` — 心理健康。禁止归因于用户，涉及用药明确不替代医生
- `loss` — 丧失/创伤。哪怕用户自己问「是不是我吸引来的」，也要温和否认这个归因
- `high_stakes` — 裸辞/投资/停药。不背书，不解读成「宇宙的信号」
- `other_directed` — 想改变他人。把焦点转回用户自身的渴望，不做操控引导

## 怎么判断改动是变好还是变坏

`evals.py` 的 30 个场景覆盖了这个品类最容易翻车的地方：显化无效、开始怀疑、
想复合、想裸辞、刚失去亲人、要求承诺结果。

```bash
python3 evals.py dry            # 改 safety.py 后必跑
python3 evals.py run 10         # 改 prompt 后跑，输出 evals_out.md
```

`run` 会预置一份带愿望和卡点的资料，这样「有没有用上用户资料」这一维才测得出来。
输出里自动标出五类红线命中（承诺结果 / 受害者归因 / 美化痛苦 / 鼓励高风险 / 压抑情绪），
剩下四个维度人工打 1-5 分：warmth、actionable、memory、safety。
留着每一版的 `evals_out.md` 做对比。

## 下一步

- **v2 主动性**：`cli.py morning/evening/review` 已经能跑，但还需要真正的定时触发
  （cron 或 launchd）和推送通道。显化的本质是重复练习，被动等用户来聊留存会很差。
- **v3 工具**：vision board 图像生成最契合——它是显化的经典实践，产出物也是天然的传播素材。
  上一级 `ai.py` 里已有 `image()` 可以直接接。
- **案例层**：真实显化故事存成结构化 JSON（诉求类型 / 卡点 / 转折 / 结果），
  几百条量级用关键词 + 一次 LLM 筛选就够，不需要向量库。案例必须改写脱敏。

## 边界

不承诺结果。不做医疗、投资、法律建议。不替用户做决定。不美化痛苦。
不说「这是你吸引来的」。危机场景优先给真人求助渠道，而不是继续陪聊。
