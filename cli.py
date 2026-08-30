#!/usr/bin/env python3
"""显化陪伴者 CLI.

    python3 cli.py              # 对话
    python3 cli.py morning      # 早间意图
    python3 cli.py evening      # 晚间复盘
    python3 cli.py review       # 周回顾
    python3 cli.py state        # 查看已记录的资料
"""
import sys

import agent
import memory
import safety

DIM, BOLD, CYAN, YELLOW, RESET = "\033[2m", "\033[1m", "\033[36m", "\033[33m", "\033[0m"


def chat_loop():
    prof = memory.load()
    print(f"{BOLD}显化陪伴者{RESET} {DIM}· /state 查看记录 · /review 周回顾 · /quit 退出{RESET}\n")
    if not prof["desires"] and not prof.get("name"):
        print(f"{CYAN}第一次见面。你现在最想在生活里发生什么变化？{RESET}\n")

    history = []
    while True:
        try:
            text = input(f"{BOLD}你{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text in ("/quit", "/exit", "q"):
            break
        if text == "/state":
            print(f"\n{DIM}{memory.render(prof)}{RESET}\n")
            continue
        if text == "/review":
            print(f"\n{CYAN}{agent.weekly_review(prof)}{RESET}\n")
            continue

        flags = safety.screen(text)
        if flags["crisis"]:
            print(f"\n{YELLOW}⚠ 已切换到安全模式{RESET}")

        try:
            reply, history = agent.respond(text, history, prof)
        except Exception as e:
            print(f"\n{YELLOW}出错了：{e}{RESET}\n")
            continue

        print(f"\n{CYAN}{reply}{RESET}\n")
        history = agent.trim(history)                 # profile carries long-term state

    memory.save(prof)
    print(f"{DIM}已保存到 data/{RESET}")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "chat"
    if cmd == "chat":
        chat_loop()
    elif cmd in ("morning", "evening"):
        print(agent.daily_prompt(memory.load(), slot=cmd))
    elif cmd == "review":
        print(agent.weekly_review(memory.load()))
    elif cmd == "state":
        print(memory.render(memory.load()))
    else:
        print(__doc__.strip())
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
