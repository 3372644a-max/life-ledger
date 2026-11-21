#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
人生账本 · 行情引擎 v1.0
在云服务器上 7x24 运行各板块的横盘模拟并记录 K 线，手机 App 打开时拉取续上。

接口（均为 POST + JSON，Header/Body 里带 token）：
  POST /sync   {token, dims:{wealth:<sinceT>, growth:..., mood:..., health:...}}
               -> {serverTime, dims:{wealth:{base, cur, pts:[[t,v],...]}, ...}}
                  pts 为上次同步点之后的行情点：间隔 <=30 分钟时是 1 秒 tick，
                  更久则是 1 分钟收盘价（App 渲染管线两者通用）。
  POST /anchor {token, dims:{wealth:<新基准值>, ...}}
               -> 手机记账后调用，把板块基准切到新真实值（K 线上表现为一次跳变）。
  GET  /health -> {ok, uptime, dims:{wealth:{base, cur, ticks, candles}}}

数据文件：data/state.json（每 30 秒落盘 + 每次锚点变更后立即落盘）
  - 1 秒 tick 内存保留最近 2 小时（足够手机打开时无缝续上）
  - 1 分钟 K 线保留 30 天
"""
import json
import os
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
STATE_FILE = os.path.join(DATA_DIR, "state.json")
TOKEN_FILE = os.path.join(BASE, "token.txt")
PORT = int(os.environ.get("PORT", "8787"))

# 与 App 内横盘参数保持一致（index.html simTick）
DIMS = ["wealth", "growth", "mood", "health"]   # 持仓(assets)走真实行情同步，不模拟
STEP_RATIO = 0.00025    # 每秒收盘变化幅度（相对基准值）
WICK_RATIO = 0.0010     # 影线幅度
WALK = 2.0              # 随机游走乘数
REVERT = 0.08           # 均值回归系数
TICK_MS = 1000
TICK_KEEP_MS = 2 * 3600 * 1000            # 秒级 tick 保留 2 小时
CANDLE_KEEP_MS = 30 * 24 * 3600 * 1000    # 1 分钟 K 线保留 30 天
MIN_STEP = {"wealth": 0.1, "growth": 0.02, "mood": 0.03, "health": 0.03}
MIN_WICK = {"wealth": 0.3, "growth": 0.05, "mood": 0.08, "health": 0.08}
SCORE_RANGE = (1.2, 10.8)                 # score 类板块钳制
SAVE_EVERY_S = 30

lock = threading.Lock()
START_T = time.time()

def load_token():
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()

TOKEN = load_token()

def default_dim():
    return {"base": None, "cur": 0.0, "ticks": [], "candles": [], "curCandle": None}

def load_state():
    st = {k: default_dim() for k in DIMS}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        for k in DIMS:
            if k in saved:
                st[k].update({kk: saved[k][kk] for kk in ("base", "cur", "ticks", "candles")})
                st[k]["base"] = None if st[k]["base"] is None else float(st[k]["base"])
                st[k]["cur"] = float(st[k]["cur"])
        print("[engine] 已从磁盘恢复状态")
    except Exception as e:
        print("[engine] 无历史状态，从头开始:", e)
    return st

state = load_state()

def save_state():
    os.makedirs(DATA_DIR, exist_ok=True)
    snap = {}
    with lock:
        for k in DIMS:
            snap[k] = {"base": state[k]["base"], "cur": state[k]["cur"],
                       "ticks": state[k]["ticks"][-21600:], "candles": state[k]["candles"]}
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(snap, f, separators=(",", ":"))
    os.replace(tmp, STATE_FILE)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def tick_once():
    now = int(time.time() * 1000)
    with lock:
        for k in DIMS:
            st = state[k]
            if st["base"] is None:
                continue
            base = st["base"]
            step = max(abs(base) * STEP_RATIO, MIN_STEP.get(k, 0.1))
            st["cur"] += (random.random() - 0.5) * 2 * step * WALK
            st["cur"] += (base - st["cur"]) * REVERT
            if st["cur"] < 0:
                st["cur"] = 0
            if k in ("mood", "health"):
                st["cur"] = clamp(st["cur"], SCORE_RANGE[0], SCORE_RANGE[1])
            wick = max(abs(base) * WICK_RATIO, MIN_WICK.get(k, 0.3))
            st["ticks"].append([now, st["cur"] + random.random() * wick * 1.7])
            st["ticks"].append([now, st["cur"] - random.random() * wick * 1.7])
            st["ticks"].append([now, st["cur"]])
            # 秒级 tick 修剪（保留 2h）
            cut = now - TICK_KEEP_MS
            if st["ticks"] and st["ticks"][0][0] < cut:
                st["ticks"] = [p for p in st["ticks"] if p[0] >= cut]
            # 聚合 1 分钟 K 线
            bucket = now // 60000 * 60000
            cc = st["curCandle"]
            if cc is None:
                st["curCandle"] = {"t": bucket, "o": st["cur"], "h": st["cur"], "l": st["cur"], "c": st["cur"]}
            elif bucket != cc["t"]:
                st["candles"].append([cc["t"], cc["o"], cc["h"], cc["l"], cc["c"]])
                st["curCandle"] = {"t": bucket, "o": st["cur"], "h": st["cur"], "l": st["cur"], "c": st["cur"]}
            else:
                cc["h"] = max(cc["h"], st["cur"])
                cc["l"] = min(cc["l"], st["cur"])
                cc["c"] = st["cur"]
            # 1 分钟 K 线修剪（保留 30 天）
            ccut = now - CANDLE_KEEP_MS
            if st["candles"] and st["candles"][0][0] < ccut:
                st["candles"] = [c for c in st["candles"] if c[0] >= ccut]

def tick_loop():
    while True:
        try:
            tick_once()
        except Exception as e:
            print("[engine] tick 异常:", e)
        time.sleep(TICK_MS / 1000.0)

def save_loop():
    while True:
        time.sleep(SAVE_EVERY_S)
        try:
            save_state()
        except Exception as e:
            print("[engine] 落盘异常:", e)

class Handler(BaseHTTPRequestHandler):
    server_version = "LedgerEngine/1.0"

    def log_message(self, fmt, *args):
        pass  # 静默访问日志

    def _json(self, code, obj):
        body = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path.split("?")[0] == "/health":
            with lock:
                dims = {k: {"base": state[k]["base"], "cur": state[k]["cur"],
                            "ticks": len(state[k]["ticks"]), "candles": len(state[k]["candles"])}
                        for k in DIMS}
            self._json(200, {"ok": True, "uptime": int(time.time() - START_T), "dims": dims})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as e:
            self._json(400, {"error": "bad json: " + str(e)})
            return
        if req.get("token") != TOKEN:
            self._json(403, {"error": "token mismatch"})
            return
        path = self.path.split("?")[0]
        if path == "/anchor":
            dims = req.get("dims") or {}
            with lock:
                for k, v in dims.items():
                    if k not in state or v is None:
                        continue
                    v = float(v)
                    st = state[k]
                    if st["base"] is None or abs(st["base"] - v) > max(abs(v) * 1e-9, 1e-9):
                        st["base"] = v
                        st["cur"] = v
            save_state()
            self._json(200, {"ok": True})
        elif path == "/sync":
            want = req.get("dims") or {}
            now = int(time.time() * 1000)
            out = {}
            with lock:
                for k in DIMS:
                    st = state[k]
                    if st["base"] is None:
                        out[k] = {"base": None, "cur": None, "pts": []}
                        continue
                    since = int(want.get(k) or 0)
                    pts = []
                    if since > 0 and since >= now - TICK_KEEP_MS:
                        pts = [p for p in st["ticks"] if p[0] > since]
                    elif since > 0:
                        # 间隔较久：给 1 分钟收盘价，量小且够渲染
                        pts = [[c[0] + 59999, c[4]] for c in st["candles"] if c[0] > since]
                    else:
                        # 首次同步（无基准时间）：给最近 30 分钟的秒级 tick
                        pts = [p for p in st["ticks"] if p[0] >= now - 30 * 60 * 1000]
                    if len(pts) > 5000:
                        pts = pts[-5000:]
                    out[k] = {"base": st["base"], "cur": st["cur"], "pts": pts}
            self._json(200, {"serverTime": now, "dims": out})
        else:
            self._json(404, {"error": "not found"})

if __name__ == "__main__":
    threading.Thread(target=tick_loop, daemon=True).start()
    threading.Thread(target=save_loop, daemon=True).start()
    print("[engine] 行情引擎启动, 端口 %d, 板块: %s" % (PORT, ",".join(DIMS)))
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
