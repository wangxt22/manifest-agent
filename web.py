#!/usr/bin/env python3
"""网页界面。

    python3 web.py

然后浏览器打开 http://127.0.0.1:8000

没有 API key 也能打开——界面能看，右上角会提示怎么配置。
标准库 http.server，不装任何依赖。
"""
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import agent
import llm
import memory
import safety

PORT = int(os.environ.get("PORT", "8000"))

# 单用户本地工具，进程内保存对话历史即可；长期状态在 profile 里。
_state = {"history": []}
_lock = threading.Lock()


PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>显化陪伴者</title>
<style>
  :root{
    --bg:#faf7f5; --card:#fff; --ink:#2e2a28; --sub:#8b8480;
    --line:#eae4e0; --me:#f0ebe6; --accent:#a8734f; --warn:#b4553f;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:16px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC","Helvetica Neue",sans-serif}
  header{position:sticky;top:0;background:rgba(250,247,245,.92);
    backdrop-filter:blur(8px);border-bottom:1px solid var(--line);padding:14px 20px;
    display:flex;align-items:center;gap:12px;z-index:5}
  h1{font-size:16px;font-weight:600;margin:0;letter-spacing:.02em}
  .tag{font-size:12px;color:var(--sub)}
  .grow{flex:1}
  button{font:inherit;font-size:13px;cursor:pointer;border:1px solid var(--line);
    background:var(--card);color:var(--sub);padding:5px 12px;border-radius:999px}
  button:hover{color:var(--ink);border-color:#d8d0ca}
  main{max-width:720px;margin:0 auto;padding:24px 20px 140px}
  .msg{margin:18px 0;display:flex}
  .msg.me{justify-content:flex-end}
  .bubble{max-width:82%;padding:12px 16px;border-radius:16px;white-space:pre-wrap;
    word-break:break-word}
  .them .bubble{background:var(--card);border:1px solid var(--line);
    border-bottom-left-radius:5px}
  .me .bubble{background:var(--me);border-bottom-right-radius:5px}
  .sys{text-align:center;font-size:13px;color:var(--sub);margin:22px 0}
  .sys.warn{color:var(--warn)}
  .note{background:#fff8f0;border:1px solid #f0e0cc;border-radius:12px;
    padding:16px 18px;font-size:14px;color:#6b5844;margin:0 0 20px}
  .note code{background:#f5ece0;padding:1px 6px;border-radius:4px;font-size:13px}
  .note a{color:var(--accent)}
  footer{position:fixed;bottom:0;left:0;right:0;background:rgba(250,247,245,.94);
    backdrop-filter:blur(8px);border-top:1px solid var(--line);padding:14px 20px}
  .box{max-width:720px;margin:0 auto;display:flex;gap:10px;align-items:flex-end}
  textarea{flex:1;font:inherit;resize:none;padding:11px 15px;border-radius:20px;
    border:1px solid var(--line);background:var(--card);color:var(--ink);
    max-height:140px;outline:none}
  textarea:focus{border-color:#d8c8b8}
  .send{background:var(--ink);color:#fff;border:none;padding:11px 20px;border-radius:20px;
    font-size:14px}
  .send:disabled{opacity:.4;cursor:default}
  .hint{max-width:720px;margin:8px auto 0;font-size:12px;color:var(--sub);text-align:center}
  .dots span{animation:b 1.4s infinite both;display:inline-block}
  .dots span:nth-child(2){animation-delay:.2s}
  .dots span:nth-child(3){animation-delay:.4s}
  @keyframes b{0%,80%,100%{opacity:.2}40%{opacity:1}}
  pre.state{background:var(--card);border:1px solid var(--line);border-radius:12px;
    padding:14px 16px;font-size:13px;line-height:1.7;white-space:pre-wrap;color:#5c5450;
    font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
</style>
</head>
<body>
<header>
  <h1>显化陪伴者</h1>
  <span class="tag" id="model"></span>
  <span class="grow"></span>
  <button onclick="showState()">我的记录</button>
  <button onclick="review()">周回顾</button>
</header>

<main id="feed"></main>

<footer>
  <div class="box">
    <textarea id="input" rows="1" placeholder="说点什么…"></textarea>
    <button class="send" id="send">发送</button>
  </div>
  <div class="hint">Enter 发送 · Shift+Enter 换行</div>
</footer>

<script>
const feed = document.getElementById('feed');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
let busy = false;

function el(cls, html){ const d=document.createElement('div'); d.className=cls; d.innerHTML=html; return d; }
function esc(s){ return s.replace(/[&<>]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

function bubble(who, text){
  const m = el('msg '+who, '<div class="bubble">'+esc(text)+'</div>');
  feed.appendChild(m); scroll(); return m;
}
function sys(text, warn){
  feed.appendChild(el('sys'+(warn?' warn':''), esc(text))); scroll();
}
function scroll(){ window.scrollTo({top:document.body.scrollHeight, behavior:'smooth'}); }

input.addEventListener('input', ()=>{ input.style.height='auto'; input.style.height=input.scrollHeight+'px'; });
input.addEventListener('keydown', e=>{
  if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); send(); }
});
sendBtn.onclick = send;

async function send(){
  const text = input.value.trim();
  if(!text || busy) return;
  input.value=''; input.style.height='auto';
  bubble('me', text);
  busy=true; sendBtn.disabled=true;
  const wait = el('msg them','<div class="bubble dots"><span>·</span><span>·</span><span>·</span></div>');
  feed.appendChild(wait); scroll();
  try{
    const r = await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text})});
    const d = await r.json();
    wait.remove();
    if(d.tier==='crisis') sys('已切换到安全模式', true);
    if(d.error) sys('出错了：'+d.error, true);
    else bubble('them', d.reply);
  }catch(e){ wait.remove(); sys('请求失败：'+e.message, true); }
  busy=false; sendBtn.disabled=false; input.focus();
}

async function showState(){
  const d = await (await fetch('/api/state')).json();
  feed.appendChild(el('sys','—— 我的记录 ——'));
  const p=document.createElement('pre'); p.className='state'; p.textContent=d.state;
  feed.appendChild(p); scroll();
}

async function review(){
  if(busy) return;
  busy=true;
  feed.appendChild(el('sys','—— 周回顾 ——'));
  const wait = el('msg them','<div class="bubble dots"><span>·</span><span>·</span><span>·</span></div>');
  feed.appendChild(wait); scroll();
  const d = await (await fetch('/api/review')).json();
  wait.remove();
  d.error ? sys('出错了：'+d.error, true) : bubble('them', d.reply);
  busy=false;
}

(async ()=>{
  const d = await (await fetch('/api/hello')).json();
  document.getElementById('model').textContent = d.model;
  if(!d.configured){
    feed.appendChild(el('note',
      '<b>还没配置 API key，现在只能看界面。</b><br><br>'+
      '1. 去 <a href="https://platform.deepseek.com/api_keys" target="_blank">platform.deepseek.com</a> 申请一个 key（充 10 块能聊很久）<br>'+
      '2. 在 <code>manifest-agent</code> 目录里新建文件 <code>.env</code>，写一行：<br>'+
      '<code>DEEPSEEK_API_KEY=sk-你的key</code><br>'+
      '3. 终端里按 Ctrl+C 停掉，重新 <code>python3 web.py</code>'));
  }
  if(d.greeting) bubble('them', d.greeting);
  input.focus();
})();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        raw = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def log_message(self, *a):
        pass                                    # 不要把每个请求都打到终端上

    def do_GET(self):
        if self.path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")

        if self.path == "/api/hello":
            prof = memory.load()
            fresh = not prof["desires"] and not prof.get("name")
            return self._json({
                "configured": llm.configured(),
                "model": llm.MODEL if llm.configured() else "未配置",
                "greeting": "第一次见面。你现在最想在生活里发生什么变化？" if fresh else
                            "我们又见面了。上次聊到的事，后来怎么样了？",
            })

        if self.path == "/api/state":
            return self._json({"state": memory.render(memory.load())})

        if self.path == "/api/review":
            try:
                with _lock:
                    return self._json({"reply": agent.weekly_review(memory.load())})
            except Exception as e:
                return self._json({"error": str(e)})

        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/api/chat":
            return self._json({"error": "not found"}, 404)
        try:
            n = int(self.headers.get("Content-Length", 0))
            text = (json.loads(self.rfile.read(n)) or {}).get("text", "").strip()
        except Exception:
            return self._json({"error": "bad request"}, 400)
        if not text:
            return self._json({"error": "empty"}, 400)

        tier = safety.tier(safety.screen(text))
        try:
            with _lock:                          # 串行化，避免并发请求把 profile 写坏
                prof = memory.load()
                reply, hist = agent.respond(text, _state["history"], prof)
                _state["history"] = agent.trim(hist)
            return self._json({"reply": reply, "tier": tier})
        except Exception as e:
            return self._json({"error": str(e), "tier": tier})


def main():
    url = f"http://127.0.0.1:{PORT}"
    print(f"\n  显化陪伴者 → {url}")
    print(f"  模型：{llm.MODEL if llm.configured() else '未配置 API key（界面仍可打开）'}")
    print("  Ctrl+C 退出\n")
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  已退出，记录保存在 data/\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
