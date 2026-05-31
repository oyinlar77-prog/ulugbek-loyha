#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║ ULUG'BEK AI v7 — Railway Hosting                        ║
╚══════════════════════════════════════════════════════════╝
"""

import os, json, time, hashlib, asyncio, random, sys
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from contextlib import asynccontextmanager
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    import anthropic as _ant
    HAS_ANT = True
except ImportError:
    HAS_ANT = False

# ── CONFIG ───────────────────────────────────────────────
# Railway environment dan o'qish (yoki .env dan)
API_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
ADM_USER = os.getenv("ADMIN_USERNAME", "admin")
ADM_PASS = os.getenv("ADMIN_PASSWORD", "admin123")
SECRET   = os.getenv("SECRET_KEY", "ulugbek2026")
PORT     = int(os.getenv("PORT", "8000"))
VER      = "7.0"

# ── DATA DIR (Railway ephemeral storage) ─────────────────
DATA_DIR = Path(os.getenv("DATA_DIR", "/tmp/ulugbek-data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

def db_load(name, default=None):
    try:
        f = DATA_DIR / f"{name}.json"
        if f.exists():
            return json.loads(f.read_text())
    except Exception:
        pass
    return default if default is not None else {}

def db_save(name, data):
    try:
        (DATA_DIR / f"{name}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2)
        )
    except Exception:
        pass

users    = db_load("users", {})
sessions: Dict[str, str] = {}
agents   = db_load("agents", [])
games    = db_load("games", [])
logs     = db_load("logs", [])
analytics: Dict[str, list] = defaultdict(list)

# ── KRIPTO / AKSIYA NARXLARI ─────────────────────────────
CRYPTO: Dict[str, float] = {
    "BTC": 67420.0, "ETH": 3280.0, "SOL": 172.0,  "BNB": 598.0,
    "ADA": 0.48,    "DOGE": 0.16,  "XRP": 0.54,   "DOT": 7.2,
    "AVAX": 38.5,   "MATIC": 0.89, "SHIB": 0.000012, "LTC": 85.0,
}
STOCKS: Dict[str, float] = {
    "AAPL": 189.4, "TSLA": 248.5, "NVDA": 875.2, "GOOGL": 175.6,
    "AMZN": 192.3, "META": 508.7, "MSFT": 415.3, "NFLX": 628.4,
    "AMD":  168.9, "INTC":  30.2, "ORCL": 118.5, "CRM":  280.0,
}
# HISTORY ni CRYPTO va STOCKS dan alohida to'ldirish (oldin xato bor edi)
HISTORY: Dict[str, List[float]] = {}
for sym, price in {**CRYPTO, **STOCKS}.items():
    HISTORY[sym] = [price]

# ── ALL PRICES helper ────────────────────────────────────
def all_prices() -> Dict[str, float]:
    return {**CRYPTO, **STOCKS}

# ── WEBSOCKET MANAGER ────────────────────────────────────
class WSManager:
    def __init__(self):
        self.ws: List[WebSocket] = []

    async def add(self, w: WebSocket):
        await w.accept()
        self.ws.append(w)

    def rm(self, w: WebSocket):
        if w in self.ws:
            self.ws.remove(w)

    async def send_all(self, d: dict):
        dead = []
        for w in self.ws:
            try:
                await w.send_json(d)
            except Exception:
                dead.append(w)
        for w in dead:
            self.rm(w)

wsm = WSManager()

# ── NARX YANGILASH ───────────────────────────────────────
async def price_loop():
    while True:
        for s in list(CRYPTO.keys()):
            CRYPTO[s] = max(0.000001, CRYPTO[s] * (1 + (random.random() - 0.499) * 0.018))
            HISTORY[s] = HISTORY[s][-60:] + [CRYPTO[s]]
        for s in list(STOCKS.keys()):
            STOCKS[s] = max(0.01, STOCKS[s] * (1 + (random.random() - 0.499) * 0.008))
            HISTORY[s] = HISTORY[s][-60:] + [STOCKS[s]]
        if wsm.ws:
            await wsm.send_all({"t": "prices", "crypto": CRYPTO, "stocks": STOCKS})
        await asyncio.sleep(3)

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(price_loop())
    print(f"\n{'='*52}")
    print(f" ⭐ ULUG'BEK AI v{VER}")
    print(f" 🌐 Port: {PORT}")
    print(f" 🔑 AI: {'✅ Tayyor' if API_KEY else '❌ Railway Variables ga ANTHROPIC_API_KEY kiriting'}")
    print(f"{'='*52}\n")
    yield
    task.cancel()

UI_HTML = r"""<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>⭐ Ulug'bek AI v7</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&family=Plus+Jakarta+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --bg:       #080C10;
  --bg2:      #0D1117;
  --bg3:      #131A22;
  --panel:    #0F1923;
  --border:   rgba(200,169,110,0.15);
  --gold:     #C8A96E;
  --gold2:    #E8C87A;
  --blue:     #38BDF8;
  --green:    #34D399;
  --red:      #F87171;
  --text:     #E2E8F0;
  --muted:    #64748B;
  --card-bg:  rgba(13,17,23,0.9);
  --glow:     rgba(200,169,110,0.08);
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html { scroll-behavior: smooth; }

body {
  font-family: 'Plus Jakarta Sans', sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  overflow-x: hidden;
}

/* Animated background */
body::before {
  content: '';
  position: fixed;
  inset: 0;
  background:
    radial-gradient(ellipse 80% 50% at 20% 10%, rgba(200,169,110,0.04) 0%, transparent 60%),
    radial-gradient(ellipse 60% 40% at 80% 80%, rgba(56,189,248,0.03) 0%, transparent 50%);
  pointer-events: none;
  z-index: 0;
}

/* ── LAYOUT ──────────────────────────────── */
.app { display: flex; height: 100vh; position: relative; z-index: 1; }

/* ── SIDEBAR ─────────────────────────────── */
.sidebar {
  width: 72px;
  background: var(--bg2);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 1.2rem 0;
  gap: 0.4rem;
  flex-shrink: 0;
  position: relative;
  z-index: 10;
}

.logo {
  font-family: 'Syne', sans-serif;
  font-size: 1.5rem;
  color: var(--gold);
  margin-bottom: 1.2rem;
  line-height: 1;
  cursor: pointer;
}

.nav-btn {
  width: 46px;
  height: 46px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.3rem;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
  background: transparent;
  color: var(--muted);
  position: relative;
}

.nav-btn:hover { background: var(--glow); color: var(--gold); border-color: var(--border); }
.nav-btn.active { background: rgba(200,169,110,0.12); color: var(--gold); border-color: rgba(200,169,110,0.3); }

.nav-btn .tooltip {
  position: absolute;
  left: 58px;
  background: var(--bg3);
  border: 1px solid var(--border);
  color: var(--text);
  font-size: 0.75rem;
  padding: 0.3rem 0.7rem;
  border-radius: 6px;
  white-space: nowrap;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s;
  font-family: 'Plus Jakarta Sans', sans-serif;
}

.nav-btn:hover .tooltip { opacity: 1; }

.sidebar-bottom { margin-top: auto; display: flex; flex-direction: column; gap: 0.4rem; align-items: center; }

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--gold), var(--gold2));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.8rem;
  font-weight: 700;
  color: #000;
  cursor: pointer;
  border: 2px solid transparent;
  transition: border-color 0.2s;
}
.user-avatar:hover { border-color: var(--gold); }

/* ── MAIN ────────────────────────────────── */
.main {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* ── TOPBAR ──────────────────────────────── */
.topbar {
  height: 56px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 1.5rem;
  gap: 1rem;
  background: rgba(8,12,16,0.8);
  backdrop-filter: blur(12px);
  flex-shrink: 0;
}

.topbar-title {
  font-family: 'Syne', sans-serif;
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--gold);
  flex: 1;
}

.badge-online {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.72rem;
  color: var(--green);
  font-family: 'DM Mono', monospace;
}

.dot-pulse {
  width: 7px;
  height: 7px;
  background: var(--green);
  border-radius: 50%;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

/* ── PAGES ───────────────────────────────── */
.page { display: none; flex: 1; overflow: hidden; }
.page.active { display: flex; flex-direction: column; }

/* ── HOME PAGE ───────────────────────────── */
.home-content {
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.2rem;
  align-content: start;
}

.hero-card {
  grid-column: 1 / -1;
  background: linear-gradient(135deg, rgba(200,169,110,0.08) 0%, rgba(56,189,248,0.04) 100%);
  border: 1px solid rgba(200,169,110,0.25);
  border-radius: 16px;
  padding: 2rem;
  display: flex;
  align-items: center;
  gap: 2rem;
}

.hero-text h1 {
  font-family: 'Syne', sans-serif;
  font-size: 2rem;
  font-weight: 800;
  background: linear-gradient(135deg, var(--gold), var(--gold2), var(--blue));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 0.5rem;
}

.hero-text p { color: var(--muted); font-size: 0.9rem; line-height: 1.6; }

.hero-badge {
  padding: 0.4rem 1rem;
  background: rgba(52,211,153,0.1);
  border: 1px solid rgba(52,211,153,0.3);
  color: var(--green);
  border-radius: 20px;
  font-size: 0.78rem;
  font-family: 'DM Mono', monospace;
  margin-top: 1rem;
  display: inline-block;
}

.stat-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1.4rem;
  transition: border-color 0.2s, transform 0.2s;
  cursor: pointer;
}

.stat-card:hover { border-color: rgba(200,169,110,0.4); transform: translateY(-2px); }

.stat-card .icon { font-size: 1.8rem; margin-bottom: 0.8rem; }
.stat-card h3 { font-family: 'Syne', sans-serif; font-size: 1.5rem; font-weight: 700; color: var(--gold); }
.stat-card p { font-size: 0.8rem; color: var(--muted); margin-top: 0.2rem; }

.quick-links {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 0.8rem;
}

.quick-btn {
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 0.85rem;
  color: var(--text);
}

.quick-btn .qicon { font-size: 1.4rem; display: block; margin-bottom: 0.4rem; }
.quick-btn:hover { background: var(--glow); border-color: rgba(200,169,110,0.35); color: var(--gold); }

/* ── CHAT PAGE ───────────────────────────── */
.chat-layout {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.chat-sidebar {
  width: 220px;
  border-right: 1px solid var(--border);
  background: var(--bg2);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  padding: 1rem;
  gap: 0.5rem;
  overflow-y: auto;
}

.chat-sidebar h3 {
  font-family: 'Syne', sans-serif;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--muted);
  padding: 0.3rem 0.5rem;
}

.agent-item {
  padding: 0.6rem 0.8rem;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s;
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.83rem;
  border: 1px solid transparent;
}

.agent-item:hover { background: var(--glow); border-color: var(--border); }
.agent-item.active { background: rgba(200,169,110,0.12); border-color: rgba(200,169,110,0.3); color: var(--gold); }
.agent-item .aicon { font-size: 1.1rem; }

.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.messages::-webkit-scrollbar { width: 4px; }
.messages::-webkit-scrollbar-track { background: transparent; }
.messages::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

.msg {
  display: flex;
  gap: 0.8rem;
  max-width: 72%;
  animation: msgIn 0.25s ease-out;
}

@keyframes msgIn {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

.msg.user { margin-left: auto; flex-direction: row-reverse; }

.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.85rem;
  font-weight: 700;
}

.msg.ai .msg-avatar { background: linear-gradient(135deg, var(--gold), var(--gold2)); color: #000; }
.msg.user .msg-avatar { background: linear-gradient(135deg, #1e40af, #3b82f6); color: #fff; }

.msg-bubble {
  padding: 0.75rem 1rem;
  border-radius: 14px;
  font-size: 0.88rem;
  line-height: 1.6;
}

.msg.ai .msg-bubble {
  background: var(--panel);
  border: 1px solid var(--border);
  border-top-left-radius: 4px;
  color: var(--text);
}

.msg.user .msg-bubble {
  background: linear-gradient(135deg, rgba(200,169,110,0.2), rgba(200,169,110,0.12));
  border: 1px solid rgba(200,169,110,0.3);
  border-top-right-radius: 4px;
  color: var(--text);
}

.typing-indicator {
  display: flex;
  gap: 5px;
  padding: 0.5rem;
  align-items: center;
}

.typing-dot {
  width: 7px;
  height: 7px;
  background: var(--gold);
  border-radius: 50%;
  animation: typing 1.4s infinite;
}

.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
  30% { opacity: 1; transform: scale(1); }
}

.chat-input-wrap {
  padding: 1rem 1.5rem;
  border-top: 1px solid var(--border);
  background: rgba(8,12,16,0.9);
  backdrop-filter: blur(12px);
}

.chat-input-row {
  display: flex;
  gap: 0.7rem;
  align-items: flex-end;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 0.7rem 1rem;
  transition: border-color 0.2s;
}

.chat-input-row:focus-within { border-color: rgba(200,169,110,0.4); }

#chatInput {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text);
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 0.88rem;
  resize: none;
  outline: none;
  max-height: 120px;
  min-height: 24px;
  line-height: 1.5;
}

#chatInput::placeholder { color: var(--muted); }

.send-btn {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, var(--gold), var(--gold2));
  border: none;
  border-radius: 10px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  color: #000;
  transition: opacity 0.2s, transform 0.15s;
  flex-shrink: 0;
}

.send-btn:hover { opacity: 0.85; transform: scale(1.05); }
.send-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* ── MARKET PAGE ─────────────────────────── */
.market-layout {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 300px;
  overflow: hidden;
}

.market-main {
  padding: 1.5rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
}

.market-tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.tab-btn {
  padding: 0.45rem 1rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--muted);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s;
  font-family: 'Plus Jakarta Sans', sans-serif;
}

.tab-btn.active { background: rgba(200,169,110,0.12); border-color: rgba(200,169,110,0.3); color: var(--gold); }

.prices-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.8rem;
}

.price-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1rem;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  overflow: hidden;
}

.price-card:hover { border-color: rgba(200,169,110,0.4); }
.price-card.selected { border-color: var(--gold); background: rgba(200,169,110,0.06); }

.price-card .sym {
  font-family: 'DM Mono', monospace;
  font-weight: 500;
  font-size: 0.9rem;
  color: var(--gold);
}

.price-card .price-val {
  font-family: 'Syne', sans-serif;
  font-size: 1.1rem;
  font-weight: 700;
  margin-top: 0.3rem;
}

.price-card .change {
  font-family: 'DM Mono', monospace;
  font-size: 0.75rem;
  margin-top: 0.2rem;
}

.change.up { color: var(--green); }
.change.down { color: var(--red); }

.sparkline {
  width: 100%;
  height: 36px;
  margin-top: 0.6rem;
}

/* ── TRADE PANEL ─────────────────────────── */
.trade-panel {
  border-left: 1px solid var(--border);
  background: var(--bg2);
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  overflow-y: auto;
}

.trade-panel h3 {
  font-family: 'Syne', sans-serif;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--muted);
}

.trade-input {
  width: 100%;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.7rem 1rem;
  color: var(--text);
  font-size: 0.88rem;
  font-family: 'Plus Jakarta Sans', sans-serif;
  outline: none;
  transition: border-color 0.2s;
}

.trade-input:focus { border-color: rgba(200,169,110,0.4); }

.trade-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem; }

.buy-btn, .sell-btn {
  padding: 0.7rem;
  border-radius: 10px;
  border: none;
  font-family: 'Syne', sans-serif;
  font-size: 0.85rem;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.15s;
}

.buy-btn { background: linear-gradient(135deg, #065f46, #059669); color: #fff; }
.sell-btn { background: linear-gradient(135deg, #7f1d1d, #dc2626); color: #fff; }
.buy-btn:hover, .sell-btn:hover { opacity: 0.85; transform: scale(1.02); }

.balance-display {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.8rem 1rem;
  font-family: 'DM Mono', monospace;
  font-size: 0.85rem;
}

.balance-display .label { color: var(--muted); font-size: 0.72rem; margin-bottom: 0.2rem; }
.balance-display .value { color: var(--gold); font-size: 1rem; font-weight: 500; }

.ai-analysis-box {
  background: rgba(200,169,110,0.04);
  border: 1px solid rgba(200,169,110,0.2);
  border-radius: 10px;
  padding: 0.8rem;
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--text);
  min-height: 60px;
  cursor: pointer;
  transition: border-color 0.2s;
}

.ai-analysis-box:hover { border-color: rgba(200,169,110,0.35); }
.ai-analysis-box.loading { color: var(--muted); }

/* ── AGENTS PAGE ─────────────────────────── */
.agents-content {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.3rem;
}

.section-title {
  font-family: 'Syne', sans-serif;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--muted);
}

.add-btn {
  padding: 0.4rem 1rem;
  background: rgba(200,169,110,0.1);
  border: 1px solid rgba(200,169,110,0.3);
  border-radius: 8px;
  color: var(--gold);
  font-size: 0.78rem;
  cursor: pointer;
  transition: all 0.2s;
  font-family: 'Plus Jakarta Sans', sans-serif;
}

.add-btn:hover { background: rgba(200,169,110,0.18); }

.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 0.9rem;
}

.agent-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1.2rem;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.agent-card:hover { border-color: rgba(200,169,110,0.4); transform: translateY(-2px); }

.agent-card .aemoji { font-size: 2rem; margin-bottom: 0.6rem; }
.agent-card h4 { font-family: 'Syne', sans-serif; font-size: 0.9rem; font-weight: 700; margin-bottom: 0.3rem; }
.agent-card p { font-size: 0.78rem; color: var(--muted); line-height: 1.4; }
.agent-card .cat-tag {
  margin-top: 0.7rem;
  display: inline-block;
  padding: 0.2rem 0.6rem;
  background: rgba(200,169,110,0.08);
  border: 1px solid rgba(200,169,110,0.2);
  border-radius: 6px;
  font-size: 0.7rem;
  color: var(--gold);
  font-family: 'DM Mono', monospace;
}

/* ── GAMES PAGE ──────────────────────────── */
.games-content {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.games-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.9rem;
}

.game-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1.4rem;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}

.game-card:hover { border-color: rgba(56,189,248,0.4); transform: translateY(-2px); }
.game-card .gicon { font-size: 2.5rem; margin-bottom: 0.7rem; }
.game-card h4 { font-family: 'Syne', sans-serif; font-size: 0.9rem; font-weight: 700; margin-bottom: 0.3rem; }
.game-card p { font-size: 0.78rem; color: var(--muted); }

/* ── GAME MODAL ──────────────────────────── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.7);
  z-index: 1000;
  display: none;
  align-items: center;
  justify-content: center;
  backdrop-filter: blur(4px);
}

.modal-overlay.open { display: flex; }

.modal {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 2rem;
  width: 90%;
  max-width: 520px;
  max-height: 80vh;
  overflow-y: auto;
  animation: modalIn 0.25s ease-out;
  position: relative;
}

@keyframes modalIn {
  from { opacity: 0; transform: scale(0.95); }
  to   { opacity: 1; transform: scale(1); }
}

.modal h2 { font-family: 'Syne', sans-serif; font-size: 1.2rem; color: var(--gold); margin-bottom: 1rem; }
.modal-close {
  position: absolute;
  top: 1rem;
  right: 1rem;
  width: 30px;
  height: 30px;
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
  color: var(--muted);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.9rem;
  transition: color 0.15s;
}
.modal-close:hover { color: var(--text); }

/* ── AUTH ────────────────────────────────── */
.auth-overlay {
  position: fixed;
  inset: 0;
  background: var(--bg);
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.auth-card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 2.5rem;
  width: 380px;
  animation: modalIn 0.3s ease-out;
}

.auth-card h2 {
  font-family: 'Syne', sans-serif;
  font-size: 1.5rem;
  font-weight: 800;
  color: var(--gold);
  margin-bottom: 0.3rem;
}

.auth-card p { color: var(--muted); font-size: 0.85rem; margin-bottom: 2rem; }

.field { margin-bottom: 1rem; }
.field label { display: block; font-size: 0.78rem; color: var(--muted); margin-bottom: 0.4rem; }

.field input {
  width: 100%;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.7rem 1rem;
  color: var(--text);
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 0.88rem;
  outline: none;
  transition: border-color 0.2s;
}

.field input:focus { border-color: rgba(200,169,110,0.4); }

.auth-submit {
  width: 100%;
  padding: 0.85rem;
  background: linear-gradient(135deg, var(--gold), var(--gold2));
  border: none;
  border-radius: 12px;
  color: #000;
  font-family: 'Syne', sans-serif;
  font-size: 0.95rem;
  font-weight: 700;
  cursor: pointer;
  margin-top: 0.5rem;
  transition: opacity 0.2s;
}

.auth-submit:hover { opacity: 0.88; }

.auth-toggle {
  text-align: center;
  margin-top: 1rem;
  font-size: 0.82rem;
  color: var(--muted);
}

.auth-toggle span { color: var(--gold); cursor: pointer; }
.auth-toggle span:hover { text-decoration: underline; }

.auth-skip {
  text-align: center;
  margin-top: 0.8rem;
  font-size: 0.78rem;
  color: var(--muted);
  cursor: pointer;
}
.auth-skip:hover { color: var(--text); }

/* ── FORM ────────────────────────────────── */
.form-group { margin-bottom: 0.9rem; }
.form-group label { display: block; font-size: 0.78rem; color: var(--muted); margin-bottom: 0.4rem; }
.form-control {
  width: 100%;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.65rem 0.9rem;
  color: var(--text);
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 0.85rem;
  outline: none;
  transition: border-color 0.2s;
}
.form-control:focus { border-color: rgba(200,169,110,0.4); }

.btn-primary {
  padding: 0.65rem 1.4rem;
  background: linear-gradient(135deg, var(--gold), var(--gold2));
  border: none;
  border-radius: 10px;
  color: #000;
  font-family: 'Syne', sans-serif;
  font-size: 0.85rem;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.2s;
}
.btn-primary:hover { opacity: 0.85; }

/* ── QUIZ GAME ───────────────────────────── */
.quiz-q { font-size: 1rem; font-weight: 600; margin-bottom: 1.2rem; line-height: 1.5; }
.quiz-opts { display: flex; flex-direction: column; gap: 0.6rem; }
.quiz-opt {
  padding: 0.8rem 1rem;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  cursor: pointer;
  font-size: 0.87rem;
  transition: all 0.15s;
}
.quiz-opt:hover { border-color: rgba(200,169,110,0.35); background: var(--glow); }
.quiz-opt.correct { border-color: var(--green); background: rgba(52,211,153,0.08); color: var(--green); }
.quiz-opt.wrong { border-color: var(--red); background: rgba(248,113,113,0.08); color: var(--red); }
.quiz-explain { margin-top: 1rem; padding: 0.8rem; background: rgba(200,169,110,0.05); border: 1px solid rgba(200,169,110,0.2); border-radius: 8px; font-size: 0.82rem; color: var(--muted); }

/* ── STORY GAME ──────────────────────────── */
.story-text { line-height: 1.7; font-size: 0.9rem; color: var(--text); margin-bottom: 1.2rem; }
.story-choices { display: flex; flex-direction: column; gap: 0.5rem; }
.story-choice {
  padding: 0.7rem 1rem;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.15s;
}
.story-choice:hover { border-color: rgba(56,189,248,0.4); color: var(--blue); }

/* ── WORD GAME ───────────────────────────── */
.word-display {
  font-family: 'Syne', sans-serif;
  font-size: 2rem;
  font-weight: 800;
  letter-spacing: 0.3em;
  color: var(--gold);
  text-align: center;
  margin: 1.2rem 0;
  filter: blur(8px);
  transition: filter 0.3s;
}
.word-display.revealed { filter: none; }
.word-hint { text-align: center; color: var(--muted); font-size: 0.85rem; margin-bottom: 1rem; }
.word-input-row { display: flex; gap: 0.5rem; }

/* ── TOAST ───────────────────────────────── */
.toast {
  position: fixed;
  bottom: 1.5rem;
  right: 1.5rem;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.toast-item {
  padding: 0.7rem 1.2rem;
  border-radius: 10px;
  font-size: 0.83rem;
  border: 1px solid;
  animation: toastIn 0.25s ease-out;
  max-width: 280px;
}

@keyframes toastIn {
  from { opacity: 0; transform: translateX(20px); }
  to   { opacity: 1; transform: translateX(0); }
}

.toast-item.success { background: rgba(52,211,153,0.1); border-color: rgba(52,211,153,0.3); color: var(--green); }
.toast-item.error { background: rgba(248,113,113,0.1); border-color: rgba(248,113,113,0.3); color: var(--red); }
.toast-item.info { background: rgba(200,169,110,0.08); border-color: rgba(200,169,110,0.25); color: var(--gold); }

/* ── SCROLLBAR ───────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

/* ── LOADING ─────────────────────────────── */
.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--border);
  border-top-color: var(--gold);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  display: inline-block;
}

@keyframes spin { to { transform: rotate(360deg); } }

.section-loader { display: flex; align-items: center; justify-content: center; padding: 2rem; gap: 0.7rem; color: var(--muted); font-size: 0.85rem; }

/* ── PORTFOLIO ───────────────────────────── */
.portfolio-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.7rem 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.85rem;
}
.portfolio-row:last-child { border-bottom: none; }
.portfolio-sym { font-family: 'DM Mono', monospace; color: var(--gold); }
.portfolio-val { color: var(--green); font-family: 'DM Mono', monospace; }

/* Mobile */
@media (max-width: 768px) {
  .sidebar { width: 56px; }
  .chat-sidebar { display: none; }
  .market-layout { grid-template-columns: 1fr; }
  .trade-panel { display: none; }
  .hero-card { flex-direction: column; }
  .hero-text h1 { font-size: 1.4rem; }
}
</style>
</head>
<body>

<!-- ── AUTH OVERLAY ─────────────────────────── -->
<div class="auth-overlay" id="authOverlay">
  <div class="auth-card">
    <h2>⭐ Ulug'bek AI</h2>
    <p>Platformaga kirish yoki ro'yxatdan o'tish</p>
    <div id="authForm">
      <div class="field">
        <label>Foydalanuvchi nomi</label>
        <input type="text" id="authUser" placeholder="username" autocomplete="off">
      </div>
      <div class="field">
        <label>Parol</label>
        <input type="password" id="authPass" placeholder="••••••••">
      </div>
      <button class="auth-submit" onclick="doAuth()">Kirish</button>
      <div class="auth-toggle">
        Akkaunt yo'qmi? <span onclick="toggleAuthMode()">Ro'yxatdan o'tish</span>
      </div>
    </div>
    <div class="auth-skip" onclick="skipAuth()">Mehmon sifatida davom etish →</div>
  </div>
</div>

<!-- ── MAIN APP ──────────────────────────────── -->
<div class="app">

  <!-- SIDEBAR -->
  <nav class="sidebar">
    <div class="logo" onclick="showPage('home')">⭐</div>
    <div class="nav-btn active" id="nav-home" onclick="showPage('home')">
      🏠<span class="tooltip">Bosh sahifa</span>
    </div>
    <div class="nav-btn" id="nav-chat" onclick="showPage('chat')">
      💬<span class="tooltip">AI Chat</span>
    </div>
    <div class="nav-btn" id="nav-market" onclick="showPage('market')">
      📈<span class="tooltip">Bozor</span>
    </div>
    <div class="nav-btn" id="nav-agents" onclick="showPage('agents')">
      🤖<span class="tooltip">Agentlar</span>
    </div>
    <div class="nav-btn" id="nav-games" onclick="showPage('games')">
      🎮<span class="tooltip">O'yinlar</span>
    </div>
    <div class="sidebar-bottom">
      <div class="nav-btn" id="nav-portfolio" onclick="showPage('portfolio')">
        💼<span class="tooltip">Portfolio</span>
      </div>
      <div class="user-avatar" id="userAvatar" onclick="toggleAuth()">?</div>
    </div>
  </nav>

  <!-- MAIN CONTENT -->
  <div class="main">

    <!-- TOPBAR -->
    <div class="topbar">
      <div class="topbar-title" id="pageTitle">Bosh sahifa</div>
      <div class="badge-online">
        <div class="dot-pulse"></div>
        <span id="wsStatus">Ulanmoqda...</span>
      </div>
    </div>

    <!-- HOME PAGE -->
    <div class="page active" id="page-home">
      <div class="home-content">
        <div class="hero-card">
          <div style="font-size:3rem">⭐</div>
          <div class="hero-text">
            <h1>Ulug'bek AI v7</h1>
            <p>Sun'iy intellekt, real vaqt bozori va o'yinlar — hammasi bir platformada. Claude AI asosidagi eng ilg'or O'zbek AI platformasi.</p>
            <span class="hero-badge">✅ Online · WebSocket · v7.0</span>
          </div>
        </div>
        <div class="stat-card" onclick="showPage('chat')">
          <div class="icon">💬</div>
          <h3 id="statChats">—</h3>
          <p>AI Suhbatlar</p>
        </div>
        <div class="stat-card" onclick="showPage('agents')">
          <div class="icon">🤖</div>
          <h3 id="statAgents">—</h3>
          <p>Faol agentlar</p>
        </div>
        <div class="stat-card" onclick="showPage('games')">
          <div class="icon">🎮</div>
          <h3 id="statGames">—</h3>
          <p>O'yinlar</p>
        </div>
        <div class="stat-card" onclick="showPage('market')">
          <div class="icon">💹</div>
          <h3>24/7</h3>
          <p>Real vaqt bozori</p>
        </div>
        <div class="quick-links">
          <div class="quick-btn" onclick="showPage('chat')"><span class="qicon">💬</span>AI Chat</div>
          <div class="quick-btn" onclick="showPage('market')"><span class="qicon">📈</span>Kripto Bozor</div>
          <div class="quick-btn" onclick="openGame('quiz')"><span class="qicon">🧠</span>Quiz O'yin</div>
          <div class="quick-btn" onclick="openGame('story')"><span class="qicon">📖</span>Hikoya O'yin</div>
          <div class="quick-btn" onclick="openGame('word')"><span class="qicon">🔤</span>So'z O'yin</div>
          <div class="quick-btn" onclick="discoverAgent()"><span class="qicon">✨</span>Agent Kashf</div>
        </div>
      </div>
    </div>

    <!-- CHAT PAGE -->
    <div class="page" id="page-chat">
      <div class="chat-layout">
        <div class="chat-sidebar">
          <h3>Agentlar</h3>
          <div class="agent-item active" id="agent-default" onclick="selectAgent(null, 'Ulug\'bek AI', '⭐')">
            <span class="aicon">⭐</span> Ulug'bek AI
          </div>
          <div id="agentList"></div>
        </div>
        <div class="chat-area">
          <div class="messages" id="messages">
            <div class="msg ai">
              <div class="msg-avatar">⭐</div>
              <div class="msg-bubble">Salom! Men <b>Ulug'bek AI</b>man. Savolingizni bering, yordam beraman! 🌟</div>
            </div>
          </div>
          <div class="chat-input-wrap">
            <div class="chat-input-row">
              <textarea id="chatInput" rows="1" placeholder="Savolingizni yozing..." onkeydown="chatKeydown(event)" oninput="autoResize(this)"></textarea>
              <button class="send-btn" id="sendBtn" onclick="sendChat()">➤</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- MARKET PAGE -->
    <div class="page" id="page-market">
      <div class="market-layout">
        <div class="market-main">
          <div class="market-tabs">
            <button class="tab-btn active" onclick="filterMarket('all', this)">Hammasi</button>
            <button class="tab-btn" onclick="filterMarket('crypto', this)">🪙 Kripto</button>
            <button class="tab-btn" onclick="filterMarket('stock', this)">📊 Aksiya</button>
          </div>
          <div class="prices-grid" id="pricesGrid">
            <div class="section-loader"><div class="loading-spinner"></div> Narxlar yuklanmoqda...</div>
          </div>
        </div>
        <div class="trade-panel">
          <h3>Savdo</h3>
          <div class="balance-display">
            <div class="label">Balans</div>
            <div class="value" id="tradeBalance">$10,000.00</div>
          </div>
          <div>
            <div class="balance-display">
              <div class="label">Tanlangan</div>
              <div class="value" id="selectedSym">—</div>
            </div>
          </div>
          <div class="form-group">
            <label>Miqdor</label>
            <input class="trade-input" type="number" id="tradeQty" placeholder="0.00" min="0" step="0.01">
          </div>
          <div class="trade-actions">
            <button class="buy-btn" onclick="executeTrade('buy')">📈 Sotib ol</button>
            <button class="sell-btn" onclick="executeTrade('sell')">📉 Sot</button>
          </div>
          <div>
            <div class="section-title" style="margin-bottom:0.5rem">🤖 AI Tahlil</div>
            <div class="ai-analysis-box" id="aiAnalysis" onclick="getAnalysis()">
              Tahlil uchun coin tanlang...
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- AGENTS PAGE -->
    <div class="page" id="page-agents">
      <div class="agents-content">
        <div class="section-header">
          <span class="section-title">Barcha agentlar</span>
          <button class="add-btn" onclick="openAddAgent()">+ Yangi agent</button>
        </div>
        <div class="agents-grid" id="agentsGrid">
          <div class="section-loader"><div class="loading-spinner"></div> Yuklanmoqda...</div>
        </div>
      </div>
    </div>

    <!-- GAMES PAGE -->
    <div class="page" id="page-games">
      <div class="games-content">
        <div class="section-header">
          <span class="section-title">O'yinlar</span>
        </div>
        <div class="games-grid">
          <div class="game-card" onclick="openGame('quiz')">
            <div class="gicon">🧠</div>
            <h4>Bilim Testi</h4>
            <p>AI tomonidan yaratilgan savollar</p>
          </div>
          <div class="game-card" onclick="openGame('story')">
            <div class="gicon">📖</div>
            <h4>Interaktiv Hikoya</h4>
            <p>O'zing tanla, hikoya davom etsin</p>
          </div>
          <div class="game-card" onclick="openGame('word')">
            <div class="gicon">🔤</div>
            <h4>So'z Topish</h4>
            <p>Yashirin so'zni top</p>
          </div>
        </div>
        <div class="section-header">
          <span class="section-title">Foydalanuvchi o'yinlari</span>
          <button class="add-btn" onclick="openAddGame()">+ Yangi o'yin</button>
        </div>
        <div class="games-grid" id="userGamesGrid">
          <div class="section-loader"><div class="loading-spinner"></div> Yuklanmoqda...</div>
        </div>
      </div>
    </div>

    <!-- PORTFOLIO PAGE -->
    <div class="page" id="page-portfolio">
      <div class="home-content">
        <div class="hero-card">
          <div style="font-size:2.5rem">💼</div>
          <div class="hero-text">
            <h1>Portfolio</h1>
            <p>Sizning investitsiyalaringiz va balans ko'rsatkichlari.</p>
          </div>
        </div>
        <div class="stat-card">
          <div class="icon">💰</div>
          <h3 id="portBalance">—</h3>
          <p>Naqd pul</p>
        </div>
        <div class="stat-card">
          <div class="icon">📊</div>
          <h3 id="portTotal">—</h3>
          <p>Umumiy qiymat</p>
        </div>
        <div class="stat-card">
          <div class="icon" id="portPnlIcon">📈</div>
          <h3 id="portPnl">—</h3>
          <p>Foyda/Zarar</p>
        </div>
        <div style="grid-column:1/-1; background:var(--panel); border:1px solid var(--border); border-radius:14px; padding:1.4rem;">
          <div class="section-title" style="margin-bottom:1rem">Aktiv pozitsiyalar</div>
          <div id="portfolioList"><div class="section-loader"><div class="loading-spinner"></div></div></div>
        </div>
      </div>
    </div>

  </div>
</div>

<!-- ── MODALS ─────────────────────────────────── -->

<!-- Quiz Modal -->
<div class="modal-overlay" id="quizModal">
  <div class="modal">
    <button class="modal-close" onclick="closeModal('quizModal')">✕</button>
    <h2>🧠 Bilim Testi</h2>
    <div class="form-group">
      <label>Mavzu</label>
      <input class="form-control" id="quizTopic" placeholder="Masalan: tarix, fan, sport..." value="umumiy bilim">
    </div>
    <button class="btn-primary" onclick="loadQuiz()" style="margin-bottom:1.2rem">Savol yuklash</button>
    <div id="quizContent"></div>
  </div>
</div>

<!-- Story Modal -->
<div class="modal-overlay" id="storyModal">
  <div class="modal">
    <button class="modal-close" onclick="closeModal('storyModal')">✕</button>
    <h2>📖 Interaktiv Hikoya</h2>
    <div id="storyContent"><div class="section-loader"><div class="loading-spinner"></div> Hikoya boshlanmoqda...</div></div>
  </div>
</div>

<!-- Word Modal -->
<div class="modal-overlay" id="wordModal">
  <div class="modal">
    <button class="modal-close" onclick="closeModal('wordModal')">✕</button>
    <h2>🔤 So'z Topish</h2>
    <div id="wordContent"></div>
  </div>
</div>

<!-- Add Agent Modal -->
<div class="modal-overlay" id="addAgentModal">
  <div class="modal">
    <button class="modal-close" onclick="closeModal('addAgentModal')">✕</button>
    <h2>🤖 Yangi Agent</h2>
    <div class="form-group"><label>ID (snake_case)</label><input class="form-control" id="agId" placeholder="my_agent"></div>
    <div class="form-group"><label>Emoji</label><input class="form-control" id="agIcon" placeholder="🤖"></div>
    <div class="form-group"><label>Nom</label><input class="form-control" id="agName" placeholder="Agent nomi"></div>
    <div class="form-group"><label>Tavsif</label><input class="form-control" id="agDesc" placeholder="Qisqa tavsif"></div>
    <div class="form-group"><label>System Prompt</label><textarea class="form-control" id="agSystem" rows="3" placeholder="Sen..."></textarea></div>
    <div style="display:flex;gap:0.6rem;margin-top:0.5rem">
      <button class="btn-primary" onclick="saveAgent()">Saqlash</button>
      <button class="btn-primary" style="background:linear-gradient(135deg,#1e3a5f,#2563eb);color:#fff" onclick="genSystem()">✨ AI Yaratsin</button>
    </div>
  </div>
</div>

<!-- Add Game Modal -->
<div class="modal-overlay" id="addGameModal">
  <div class="modal">
    <button class="modal-close" onclick="closeModal('addGameModal')">✕</button>
    <h2>🎮 Yangi O'yin</h2>
    <div class="form-group"><label>ID</label><input class="form-control" id="gmId" placeholder="my_game"></div>
    <div class="form-group"><label>Emoji</label><input class="form-control" id="gmIcon" placeholder="🎮"></div>
    <div class="form-group"><label>Nom</label><input class="form-control" id="gmName" placeholder="O'yin nomi"></div>
    <div class="form-group"><label>Tavsif</label><input class="form-control" id="gmDesc" placeholder="Qisqa tavsif"></div>
    <button class="btn-primary" onclick="saveGame()" style="margin-top:0.5rem">Saqlash</button>
  </div>
</div>

<!-- Toast container -->
<div class="toast" id="toastContainer"></div>

<script>
// ── STATE ────────────────────────────────────────────────
const BASE = window.location.origin;
let token = localStorage.getItem('ub_token') || '';
let currentUser = localStorage.getItem('ub_user') || '';
let isLoginMode = true;
let currentAgent = { system: '', name: 'Ulug\'bek AI' };
let chatHistory = [];
let selectedSym = null;
let allPrices = {};
let marketFilter = 'all';
let ws = null;

// ── INIT ─────────────────────────────────────────────────
window.addEventListener('load', () => {
  if (token) {
    hideAuth();
    initApp();
  } else {
    // Show auth but allow skip
  }
});

function initApp() {
  updateAvatar();
  connectWS();
  loadHealth();
  loadAgents();
  loadPrices();
  loadGames();
  if (token) loadPortfolio();
}

function skipAuth() {
  document.getElementById('authOverlay').style.display = 'none';
  initApp();
}

function hideAuth() {
  document.getElementById('authOverlay').style.display = 'none';
}

function toggleAuth() {
  if (token) {
    if (confirm('Chiqishni xohlaysizmi?')) {
      token = ''; currentUser = '';
      localStorage.removeItem('ub_token');
      localStorage.removeItem('ub_user');
      updateAvatar();
      document.getElementById('authOverlay').style.display = 'flex';
    }
  } else {
    document.getElementById('authOverlay').style.display = 'flex';
  }
}

function toggleAuthMode() {
  isLoginMode = !isLoginMode;
  document.querySelector('.auth-submit').textContent = isLoginMode ? 'Kirish' : 'Ro\'yxatdan o\'tish';
  document.querySelector('.auth-toggle span').textContent = isLoginMode ? 'Ro\'yxatdan o\'tish' : 'Kirish';
}

async function doAuth() {
  const u = document.getElementById('authUser').value.trim();
  const p = document.getElementById('authPass').value;
  if (!u || !p) { toast('Ma\'lumotlar to\'liq emas', 'error'); return; }
  const endpoint = isLoginMode ? '/api/login' : '/api/register';
  try {
    const r = await api(endpoint, { username: u, password: p });
    if (r.ok) {
      token = r.token; currentUser = r.username;
      localStorage.setItem('ub_token', token);
      localStorage.setItem('ub_user', currentUser);
      hideAuth();
      initApp();
      toast(`Xush kelibsiz, ${r.username}! 👋`, 'success');
    }
  } catch(e) { toast(e.message, 'error'); }
}

function updateAvatar() {
  const av = document.getElementById('userAvatar');
  av.textContent = currentUser ? currentUser[0].toUpperCase() : '?';
}

// ── API ──────────────────────────────────────────────────
async function api(path, body, method) {
  const opts = {
    method: method || (body ? 'POST' : 'GET'),
    headers: { 'Content-Type': 'application/json' },
  };
  if (token) opts.headers['Authorization'] = 'Bearer ' + token;
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(BASE + path, opts);
  const d = await r.json();
  if (!r.ok) throw new Error(d.detail || 'Xato');
  return d;
}

// ── WEBSOCKET ────────────────────────────────────────────
function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => { setWS('Ulangan ✓'); };
  ws.onclose = () => { setWS('Uzildi'); setTimeout(connectWS, 3000); };
  ws.onerror = () => setWS('Xato');
  ws.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data);
      if (d.t === 'prices') {
        Object.assign(allPrices, d.crypto, d.stocks);
        updatePriceCards(d.crypto, d.stocks);
      }
      if (d.t === 'new_agent') addAgentToUI(d.agent);
      if (d.t === 'new_game') refreshGames();
    } catch(_) {}
  };
}

function setWS(s) { document.getElementById('wsStatus').textContent = s; }

// ── PAGES ────────────────────────────────────────────────
const pageTitles = { home: 'Bosh sahifa', chat: '💬 AI Chat', market: '📈 Bozor', agents: '🤖 Agentlar', games: '🎮 O\'yinlar', portfolio: '💼 Portfolio' };

function showPage(name) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  document.getElementById('nav-' + name)?.classList.add('active');
  document.getElementById('pageTitle').textContent = pageTitles[name] || name;
  if (name === 'market') renderPrices();
  if (name === 'portfolio' && token) loadPortfolio();
}

// ── HEALTH ───────────────────────────────────────────────
async function loadHealth() {
  try {
    const d = await api('/health');
    document.getElementById('statChats').textContent = d.users || 0;
    document.getElementById('statAgents').textContent = d.agents || 0;
    document.getElementById('statGames').textContent = d.games || 0;
  } catch(_) {}
}

// ── AGENTS ───────────────────────────────────────────────
let agentsList = [];

async function loadAgents() {
  try {
    const d = await api('/api/agents');
    agentsList = d.agents || [];
    renderAgents();
  } catch(_) {}
}

function renderAgents() {
  // Sidebar
  const list = document.getElementById('agentList');
  list.innerHTML = agentsList.slice(0, 10).map(a =>
    `<div class="agent-item" onclick="selectAgent('${escHtml(a.system)}','${escHtml(a.name)}','${a.icon}')">
      <span class="aicon">${a.icon}</span> ${escHtml(a.name)}
    </div>`
  ).join('');

  // Agents page
  const grid = document.getElementById('agentsGrid');
  if (!agentsList.length) {
    grid.innerHTML = '<div class="section-loader">Agentlar yo\'q. Birinchi bo\'ling! 🚀</div>';
    return;
  }
  grid.innerHTML = agentsList.map(a =>
    `<div class="agent-card" onclick="selectAgent('${escHtml(a.system)}','${escHtml(a.name)}','${a.icon}'); showPage('chat')">
      <div class="aemoji">${a.icon}</div>
      <h4>${escHtml(a.name)}</h4>
      <p>${escHtml(a.desc || '')}</p>
      <span class="cat-tag">${a.cat || 'ai'}</span>
    </div>`
  ).join('');
}

function addAgentToUI(a) {
  if (!agentsList.find(x => x.id === a.id)) {
    agentsList.push(a);
    renderAgents();
  }
}

function selectAgent(system, name, icon) {
  currentAgent = { system: system || '', name };
  chatHistory = [];
  document.querySelectorAll('.agent-item').forEach(i => i.classList.remove('active'));
  document.getElementById('agent-default')?.classList.toggle('active', !system);
  const msgs = document.getElementById('messages');
  msgs.innerHTML = `<div class="msg ai">
    <div class="msg-avatar">${icon || '⭐'}</div>
    <div class="msg-bubble">Salom! Men <b>${escHtml(name)}</b>man. Qanday yordam bera olaman?</div>
  </div>`;
  showPage('chat');
}

// ── CHAT ─────────────────────────────────────────────────
function chatKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

async function sendChat() {
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if (!text) return;
  input.value = ''; input.style.height = 'auto';
  const btn = document.getElementById('sendBtn');
  btn.disabled = true;

  addMsg('user', '👤', text);
  chatHistory.push({ role: 'user', content: text });

  // typing indicator
  const typing = document.createElement('div');
  typing.className = 'msg ai';
  typing.id = 'typing';
  typing.innerHTML = `<div class="msg-avatar">⭐</div>
    <div class="msg-bubble"><div class="typing-indicator">
      <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
    </div></div>`;
  document.getElementById('messages').appendChild(typing);
  scrollMsgs();

  try {
    const d = await api('/api/chat', {
      messages: chatHistory.slice(-12),
      system: currentAgent.system,
      user: currentUser || 'guest',
    });
    document.getElementById('typing')?.remove();
    addMsg('ai', '⭐', d.text);
    chatHistory.push({ role: 'assistant', content: d.text });
  } catch(e) {
    document.getElementById('typing')?.remove();
    addMsg('ai', '⭐', '❌ Xato: ' + e.message);
  }
  btn.disabled = false;
}

function addMsg(role, icon, text) {
  const msgs = document.getElementById('messages');
  const d = document.createElement('div');
  d.className = 'msg ' + role;
  d.innerHTML = `<div class="msg-avatar">${icon}</div>
    <div class="msg-bubble">${escHtml(text).replace(/\n/g,'<br>')}</div>`;
  msgs.appendChild(d);
  scrollMsgs();
}

function scrollMsgs() {
  const m = document.getElementById('messages');
  m.scrollTop = m.scrollHeight;
}

// ── MARKET ───────────────────────────────────────────────
async function loadPrices() {
  try {
    const d = await api('/api/prices');
    allPrices = {};
    Object.values(d.crypto).forEach(c => { allPrices[c.symbol] = c; });
    Object.values(d.stocks).forEach(s => { allPrices[s.symbol] = s; });
    renderPrices();
  } catch(_) {}
}

function filterMarket(f, btn) {
  marketFilter = f;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderPrices();
}

function renderPrices() {
  const grid = document.getElementById('pricesGrid');
  const items = Object.values(allPrices).filter(p =>
    marketFilter === 'all' || p.type === marketFilter
  );
  if (!items.length) return;
  grid.innerHTML = items.map(p => {
    const up = p.change >= 0;
    const spark = sparklineSVG(p.history || [p.price], up ? '#34D399' : '#F87171');
    return `<div class="price-card ${selectedSym === p.symbol ? 'selected' : ''}" onclick="selectSymbol('${p.symbol}')">
      <div class="sym">${p.symbol}</div>
      <div class="price-val">$${fmt(p.price)}</div>
      <div class="change ${up ? 'up' : 'down'}">${up ? '▲' : '▼'} ${Math.abs(p.change).toFixed(3)}%</div>
      <svg class="sparkline" viewBox="0 0 100 36">${spark}</svg>
    </div>`;
  }).join('');
}

function updatePriceCards(crypto, stocks) {
  const merged = { ...crypto, ...stocks };
  Object.entries(merged).forEach(([sym, price]) => {
    if (allPrices[sym]) {
      const prev = allPrices[sym].price;
      const ch = ((price - prev) / prev * 100);
      allPrices[sym].price = price;
      allPrices[sym].change = ch;
      allPrices[sym].history = [...(allPrices[sym].history || [price]).slice(-40), price];
    }
  });
  if (document.getElementById('page-market').classList.contains('active')) renderPrices();
}

function sparklineSVG(data, color) {
  if (data.length < 2) return '';
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * 100;
    const y = 34 - ((v - min) / range) * 32;
    return `${x},${y}`;
  }).join(' ');
  return `<polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>`;
}

function selectSymbol(sym) {
  selectedSym = sym;
  document.getElementById('selectedSym').textContent = sym;
  document.querySelectorAll('.price-card').forEach(c => c.classList.remove('selected'));
  document.querySelectorAll('.price-card').forEach(c => {
    if (c.querySelector('.sym')?.textContent === sym) c.classList.add('selected');
  });
  document.getElementById('aiAnalysis').textContent = 'AI tahlil uchun bosing...';
}

async function getAnalysis() {
  if (!selectedSym) { toast('Avval coin tanlang', 'error'); return; }
  const box = document.getElementById('aiAnalysis');
  box.textContent = '⏳ Tahlil qilinmoqda...';
  box.className = 'ai-analysis-box loading';
  try {
    const d = await api('/api/ai-analysis', { symbol: selectedSym });
    box.textContent = d.text || 'Tahlil mavjud emas';
    box.className = 'ai-analysis-box';
  } catch(e) {
    box.textContent = '❌ Xato: ' + e.message;
    box.className = 'ai-analysis-box';
  }
}

async function executeTrade(action) {
  if (!token) { toast('Savdo uchun tizimga kiring', 'error'); return; }
  if (!selectedSym) { toast('Symbol tanlang', 'error'); return; }
  const qty = parseFloat(document.getElementById('tradeQty').value);
  if (!qty || qty <= 0) { toast('Miqdor kiriting', 'error'); return; }
  try {
    const d = await api('/api/trade', { symbol: selectedSym, action, qty, market: 'crypto' });
    document.getElementById('tradeBalance').textContent = '$' + d.balance.toLocaleString('en', { minimumFractionDigits: 2 });
    toast(`${action === 'buy' ? '📈 Sotib olindi' : '📉 Sotildi'}: ${qty} ${selectedSym} $${d.total}`, 'success');
  } catch(e) { toast(e.message, 'error'); }
}

async function loadPortfolio() {
  if (!token) {
    document.getElementById('portfolioList').innerHTML = '<div class="section-loader">Kirish kerak</div>';
    return;
  }
  try {
    const d = await api('/api/portfolio');
    document.getElementById('portBalance').textContent = '$' + d.balance.toLocaleString('en', { minimumFractionDigits: 2 });
    document.getElementById('portTotal').textContent = '$' + (d.balance + d.total_value).toLocaleString('en', { minimumFractionDigits: 2 });
    const pnl = d.pnl;
    document.getElementById('portPnl').textContent = (pnl >= 0 ? '+' : '') + '$' + pnl.toFixed(2);
    document.getElementById('portPnlIcon').textContent = pnl >= 0 ? '📈' : '📉';
    document.getElementById('tradeBalance').textContent = '$' + d.balance.toLocaleString('en', { minimumFractionDigits: 2 });
    const list = document.getElementById('portfolioList');
    const entries = Object.entries(d.portfolio);
    if (!entries.length) {
      list.innerHTML = '<div style="color:var(--muted);font-size:0.85rem;padding:0.5rem 0">Pozitsiyalar yo\'q</div>';
      return;
    }
    list.innerHTML = entries.map(([sym, info]) =>
      `<div class="portfolio-row">
        <span class="portfolio-sym">${sym}</span>
        <span style="color:var(--muted);font-size:0.8rem">${info.qty} × $${fmt(info.price)}</span>
        <span class="portfolio-val">$${info.value.toFixed(2)}</span>
      </div>`
    ).join('');
  } catch(_) {}
}

// ── GAMES ────────────────────────────────────────────────
async function loadGames() {
  try {
    const d = await api('/api/games');
    const grid = document.getElementById('userGamesGrid');
    const gs = d.games || [];
    if (!gs.length) { grid.innerHTML = '<div class="section-loader">Foydalanuvchi o\'yinlari yo\'q</div>'; return; }
    grid.innerHTML = gs.map(g =>
      `<div class="game-card">
        <div class="gicon">${g.icon}</div>
        <h4>${escHtml(g.name)}</h4>
        <p>${escHtml(g.desc || '')}</p>
      </div>`
    ).join('');
  } catch(_) {}
}

function refreshGames() { loadGames(); }

function openGame(type) {
  if (type === 'quiz') { openModal('quizModal'); loadQuiz(); }
  else if (type === 'story') { openModal('storyModal'); loadStory(''); }
  else if (type === 'word') { openModal('wordModal'); loadWord(); }
}

// Quiz
async function loadQuiz() {
  const topic = document.getElementById('quizTopic')?.value || 'umumiy bilim';
  const box = document.getElementById('quizContent');
  box.innerHTML = '<div class="section-loader"><div class="loading-spinner"></div> Savol tayyorlanmoqda...</div>';
  try {
    const d = await api('/api/game/quiz', { topic });
    const q = d.q;
    box.innerHTML = `<div class="quiz-q">${escHtml(q.q)}</div>
      <div class="quiz-opts">
        ${q.a.map((ans, i) =>
          `<div class="quiz-opt" onclick="checkQuiz(this,${i},${q.correct},'${escHtml(q.explain || '')}')">${escHtml(ans)}</div>`
        ).join('')}
      </div>
      <div class="quiz-explain" id="quizExplain" style="display:none"></div>`;
  } catch(e) { box.innerHTML = `<div style="color:var(--red)">❌ ${e.message}</div>`; }
}

function checkQuiz(el, idx, correct, explain) {
  document.querySelectorAll('.quiz-opt').forEach(o => {
    o.style.pointerEvents = 'none';
  });
  if (idx === correct) { el.classList.add('correct'); toast('✅ To\'g\'ri!', 'success'); }
  else {
    el.classList.add('wrong');
    document.querySelectorAll('.quiz-opt')[correct]?.classList.add('correct');
    toast('❌ Xato', 'error');
  }
  const expBox = document.getElementById('quizExplain');
  if (explain) { expBox.textContent = '💡 ' + explain; expBox.style.display = 'block'; }
}

// Story
async function loadStory(choice) {
  const box = document.getElementById('storyContent');
  box.innerHTML = '<div class="section-loader"><div class="loading-spinner"></div></div>';
  try {
    const d = await api('/api/game/story', { choice });
    const s = d.s;
    box.innerHTML = `<div class="story-text">${escHtml(s.story).replace(/\n/g,'<br>')}</div>
      <div class="story-choices">
        ${(s.choices || []).map(c =>
          `<div class="story-choice" onclick="loadStory('${escHtml(c)}')">${escHtml(c)}</div>`
        ).join('')}
      </div>`;
  } catch(e) { box.innerHTML = `<div style="color:var(--red)">❌ ${e.message}</div>`; }
}

// Word
let currentWord = '';

async function loadWord() {
  const box = document.getElementById('wordContent');
  box.innerHTML = '<div class="section-loader"><div class="loading-spinner"></div></div>';
  try {
    const d = await api('/api/game/word');
    currentWord = d.w.word;
    box.innerHTML = `
      <div class="word-hint">💡 Maslahat: ${escHtml(d.w.hint)}</div>
      <div class="word-display" id="wordDisplay">${currentWord}</div>
      <div class="word-input-row">
        <input class="form-control" id="wordInput" placeholder="So'zni taxmin qiling..." style="flex:1" onkeydown="if(event.key==='Enter')checkWord()">
        <button class="btn-primary" onclick="checkWord()">Tekshir</button>
      </div>
      <div id="wordResult" style="margin-top:0.7rem;font-size:0.85rem"></div>
      <button class="btn-primary" style="margin-top:1rem;background:rgba(200,169,110,0.1);border:1px solid rgba(200,169,110,0.3);color:var(--gold)" onclick="revealWord()">Ko'rish</button>
    `;
  } catch(_) {}
}

function checkWord() {
  const guess = document.getElementById('wordInput').value.trim().toUpperCase();
  const res = document.getElementById('wordResult');
  if (guess === currentWord) {
    res.innerHTML = '<span style="color:var(--green)">✅ To\'g\'ri! Barakalla!</span>';
    document.getElementById('wordDisplay').classList.add('revealed');
    toast('🎉 To\'g\'ri topdingiz!', 'success');
  } else {
    res.innerHTML = '<span style="color:var(--red)">❌ Xato. Qayta urining.</span>';
  }
}

function revealWord() {
  document.getElementById('wordDisplay').classList.add('revealed');
}

// ── ADD AGENT / GAME ─────────────────────────────────────
function openAddAgent() { if (!token) { toast('Kirish kerak', 'error'); return; } openModal('addAgentModal'); }
function openAddGame()  { if (!token) { toast('Kirish kerak', 'error'); return; } openModal('addGameModal'); }

async function saveAgent() {
  const body = {
    id: document.getElementById('agId').value || 'ag_' + Date.now(),
    icon: document.getElementById('agIcon').value || '🤖',
    name: document.getElementById('agName').value,
    desc: document.getElementById('agDesc').value,
    system: document.getElementById('agSystem').value,
  };
  if (!body.name || !body.system) { toast('Nom va system prompt kerak', 'error'); return; }
  try {
    await api('/api/agents', body);
    closeModal('addAgentModal');
    loadAgents();
    toast('Agent yaratildi! 🤖', 'success');
  } catch(e) { toast(e.message, 'error'); }
}

async function genSystem() {
  const name = document.getElementById('agName').value;
  const desc = document.getElementById('agDesc').value;
  if (!name) { toast('Avval nom kiriting', 'error'); return; }
  toast('AI system prompt yaratmoqda...', 'info');
  try {
    const d = await api('/api/game/ai-gen-system', { name, desc });
    document.getElementById('agSystem').value = d.system;
  } catch(e) { toast(e.message, 'error'); }
}

async function saveGame() {
  const body = {
    id: document.getElementById('gmId').value || 'gm_' + Date.now(),
    icon: document.getElementById('gmIcon').value || '🎮',
    name: document.getElementById('gmName').value,
    desc: document.getElementById('gmDesc').value,
  };
  if (!body.name) { toast('Nom kerak', 'error'); return; }
  try {
    await api('/api/games', body);
    closeModal('addGameModal');
    loadGames();
    toast('O\'yin yaratildi! 🎮', 'success');
  } catch(e) { toast(e.message, 'error'); }
}

async function discoverAgent() {
  toast('✨ Agent kashf qilinmoqda...', 'info');
  try {
    const d = await api('/api/discover');
    if (d.ok && d.agent) {
      toast(`Yangi agent: ${d.agent.icon} ${d.agent.name}`, 'success');
      if (token) await api('/api/agents', { ...d.agent, system: d.agent.system || '' });
      loadAgents();
    }
  } catch(e) { toast(e.message, 'error'); }
}

// ── MODAL ────────────────────────────────────────────────
function openModal(id) { document.getElementById(id).classList.add('open'); }
function closeModal(id) { document.getElementById(id).classList.remove('open'); }

// Close on overlay click
document.querySelectorAll('.modal-overlay').forEach(o => {
  o.addEventListener('click', e => { if (e.target === o) o.classList.remove('open'); });
});

// ── TOAST ────────────────────────────────────────────────
function toast(msg, type = 'info') {
  const c = document.getElementById('toastContainer');
  const t = document.createElement('div');
  t.className = `toast-item ${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.remove(), 3500);
}

// ── UTILS ────────────────────────────────────────────────
function escHtml(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}

function fmt(n) {
  if (n < 0.001) return n.toFixed(8);
  if (n < 1) return n.toFixed(4);
  if (n < 1000) return n.toFixed(2);
  return n.toLocaleString('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
</script>
</body>
</html>
"""

app = FastAPI(title="Ulug'bek AI", version=VER, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static fayllar
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── MODELS ───────────────────────────────────────────────
class ChatReq(BaseModel):
    messages: list
    system: str = ""
    max_tokens: int = 900
    user: str = "anon"

class AuthReq(BaseModel):
    username: str
    password: str

class AgentReq(BaseModel):
    id: str
    icon: str
    name: str
    cat: str = "ai"
    desc: str = ""
    system: str
    color: str = "#C8A96E"
    public: bool = True

class GameReq(BaseModel):
    id: str
    icon: str
    name: str
    desc: str = ""
    color: str = "#60a5fa"
    game_type: str = "quiz"
    public: bool = True

class TradeReq(BaseModel):
    symbol: str
    action: str
    qty: float
    market: str = "crypto"

# ── AUTH ─────────────────────────────────────────────────
def mktoken(username: str) -> str:
    return hashlib.sha256(
        f"{username}{time.time()}{SECRET}".encode()
    ).hexdigest()[:32]

def mkhash(pw: str) -> str:
    return hashlib.sha256(f"{pw}{SECRET}".encode()).hexdigest()

def checkpw(raw: str, hsh: str) -> bool:
    return mkhash(raw) == hsh

def get_user(auth: str = Header(None)):
    if not auth:
        raise HTTPException(401, "Token kerak")
    tok = auth.replace("Bearer ", "").strip()
    if tok not in sessions:
        raise HTTPException(401, "Token noto'g'ri")
    u = sessions[tok]
    if u not in users:
        raise HTTPException(401, "User topilmadi")
    return {"username": u, **users[u]}

def get_admin(auth: str = Header(None)):
    if not auth:
        raise HTTPException(401, "Token kerak")
    tok = auth.replace("Bearer ", "").strip()
    u = sessions.get(tok, "")
    if not u.startswith("admin"):
        raise HTTPException(403, "Admin huquqi yo'q")
    return u

# ── AI ───────────────────────────────────────────────────
async def call_ai(messages: list, system: str = "", max_tokens: int = 900) -> dict:
    if not API_KEY:
        return {
            "ok": False, "text": "",
            "error": "ANTHROPIC_API_KEY yo'q. Railway → Variables ga kiriting."
        }
    if not HAS_ANT:
        return {"ok": False, "text": "", "error": "anthropic paketi o'rnatilmagan"}
    try:
        client = _ant.Anthropic(api_key=API_KEY)
        r = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=system or "Sen Ulug'bek AI yordamchisi. O'zbek tilida qisqa, foydali javob ber.",
            messages=messages,
        )
        return {"ok": True, "text": r.content[0].text}
    except Exception as e:
        return {"ok": False, "text": "", "error": str(e)}

# ════════════════════════════════════════════════════════
# API ENDPOINTLAR
# ════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {
        "ok": True, "version": VER,
        "ai": bool(API_KEY and HAS_ANT),
        "users": len(users), "agents": len(agents),
        "games": len(games), "ws": len(wsm.ws),
        "time": datetime.now().isoformat(),
    }

# ── REGISTER / LOGIN ─────────────────────────────────────
@app.post("/api/register")
def register(r: AuthReq):
    if len(r.username) < 3:
        raise HTTPException(400, "Username kamida 3 belgi")
    if r.username in users:
        raise HTTPException(400, "Username band")
    users[r.username] = {
        "id": str(int(time.time() * 1000)),
        "password": mkhash(r.password),
        "plan": "free",
        "balance": 10000.0,
        "portfolio": {},
        "created": datetime.now().isoformat(),
    }
    db_save("users", users)
    tok = mktoken(r.username)
    sessions[tok] = r.username
    return {"ok": True, "token": tok, "username": r.username}

@app.post("/api/login")
def login(r: AuthReq):
    if r.username not in users:
        raise HTTPException(404, "User topilmadi")
    if not checkpw(r.password, users[r.username]["password"]):
        raise HTTPException(401, "Parol xato")
    tok = mktoken(r.username)
    sessions[tok] = r.username
    return {
        "ok": True, "token": tok,
        "username": r.username,
        "plan": users[r.username].get("plan", "free"),
    }

@app.get("/api/me")
def me(u=Depends(get_user)):
    return {"ok": True, "user": {k: v for k, v in u.items() if k != "password"}}

# ── AI CHAT ──────────────────────────────────────────────
@app.post("/api/chat")
async def chat(r: ChatReq):
    res = await call_ai(r.messages, r.system, r.max_tokens)
    logs.append({
        "t": datetime.now().isoformat(), "u": r.user,
        "n": len(r.messages), "ok": res["ok"],
        "len": len(res.get("text", "")),
    })
    if len(logs) > 5000:
        logs[:] = logs[-3000:]
    db_save("logs", logs[-500:])
    if not res["ok"]:
        raise HTTPException(500, res["error"])
    return {"ok": True, "text": res["text"]}

# ── BOZOR ────────────────────────────────────────────────
@app.get("/api/prices")
def prices():
    def fmt(sym, price, mtype):
        h = HISTORY.get(sym, [price])
        prev = h[-2] if len(h) > 1 else price
        ch = ((price - prev) / prev * 100) if prev else 0
        return {
            "symbol": sym, "price": round(price, 6),
            "change": round(ch, 3), "history": h[-40:], "type": mtype,
        }
    return {
        "crypto": {s: fmt(s, p, "crypto") for s, p in CRYPTO.items()},
        "stocks": {s: fmt(s, p, "stock")  for s, p in STOCKS.items()},
        "time": datetime.now().isoformat(),
    }

@app.post("/api/trade")
def trade(r: TradeReq, u=Depends(get_user)):
    nm  = u["username"]
    ap  = all_prices()
    if r.symbol not in ap:
        raise HTTPException(404, f"{r.symbol} topilmadi")
    price = ap[r.symbol]
    total = r.qty * price
    bal   = float(users[nm].get("balance", 10000))
    port  = users[nm].get("portfolio", {})
    hold  = float(port.get(r.symbol, 0))

    if r.action == "buy":
        if total > bal:
            raise HTTPException(400, f"Mablag' yetarli emas. Kerak: ${total:.2f}")
        users[nm]["balance"] = round(bal - total, 2)
        users[nm].setdefault("portfolio", {})[r.symbol] = round(hold + r.qty, 6)
    elif r.action == "sell":
        if r.qty > hold:
            raise HTTPException(400, f"Yetarli {r.symbol} yo'q. Mavjud: {hold}")
        users[nm]["balance"] = round(bal + total, 2)
        nh = round(hold - r.qty, 6)
        if nh <= 0:
            users[nm].get("portfolio", {}).pop(r.symbol, None)
        else:
            users[nm].setdefault("portfolio", {})[r.symbol] = nh
    else:
        raise HTTPException(400, "action: buy yoki sell")

    db_save("users", users)
    analytics["trades"].append({
        "t": datetime.now().isoformat(), "u": nm,
        "sym": r.symbol, "act": r.action,
        "qty": r.qty, "price": price, "total": total,
    })
    return {
        "ok": True, "symbol": r.symbol, "action": r.action,
        "qty": r.qty, "price": price, "total": round(total, 2),
        "balance": users[nm]["balance"],
        "portfolio": users[nm].get("portfolio", {}),
    }

@app.get("/api/portfolio")
def portfolio(u=Depends(get_user)):
    nm   = u["username"]
    port = users[nm].get("portfolio", {})
    ap   = all_prices()
    tv   = 0.0
    res  = {}
    for s, q in port.items():
        p = ap.get(s, 0)
        v = q * p
        tv += v
        res[s] = {"qty": q, "price": round(p, 6), "value": round(v, 2)}
    bal = float(users[nm].get("balance", 10000))
    return {
        "ok": True, "balance": bal,
        "portfolio": res,
        "total_value": round(tv, 2),
        "pnl": round(bal + tv - 10000, 2),
    }

# ── AI TAHLIL ────────────────────────────────────────────
@app.post("/api/ai-analysis")
async def ai_analysis(req: Request):
    b      = await req.json()
    sym    = b.get("symbol", "BTC")
    price  = all_prices().get(sym, 0)
    hist   = HISTORY.get(sym, [price])
    ch     = ((hist[-1] - hist[-2]) / hist[-2] * 100) if len(hist) > 1 else 0
    res    = await call_ai(
        [{"role": "user", "content":
          f"{sym} narxi: ${price:.4f}, o'zgarish: {ch:+.2f}%. Qisqa tahlil va buy/sell/hold tavsiya ber."}],
        "Sen moliyaviy tahlilchi. Qisqa va aniq javob ber. O'zbek tilida.",
    )
    return {"ok": res["ok"], "text": res["text"], "error": res.get("error", "")}

# ── AGENTLAR ─────────────────────────────────────────────
@app.get("/api/agents")
def get_agents():
    return {"ok": True, "agents": [a for a in agents if a.get("public", True)]}

@app.post("/api/agents")
async def create_agent(r: AgentReq, u=Depends(get_user)):
    new = {
        **r.dict(), "creator": u["username"],
        "created": datetime.now().isoformat(),
        "rating": 0.0, "installs": 0, "userCreated": True,
    }
    agents.append(new)
    db_save("agents", agents)
    if r.public:
        await wsm.send_all({"t": "new_agent", "agent": new})
    return {"ok": True, "agent": new}

@app.delete("/api/agents/{aid}")
async def del_agent(aid: str, u=Depends(get_user)):
    before = len(agents)
    agents[:] = [
        a for a in agents
        if not (a["id"] == aid and a.get("creator") == u["username"])
    ]
    if len(agents) == before:
        raise HTTPException(404, "Topilmadi yoki ruxsat yo'q")
    db_save("agents", agents)
    return {"ok": True}

# ── O'YINLAR ─────────────────────────────────────────────
@app.get("/api/games")
def get_games():
    return {"ok": True, "games": [g for g in games if g.get("public", True)]}

@app.post("/api/games")
async def create_game(r: GameReq, u=Depends(get_user)):
    new = {
        **r.dict(), "creator": u["username"],
        "created": datetime.now().isoformat(),
        "rating": 0.0, "installs": 0,
    }
    games.append(new)
    db_save("games", games)
    if r.public:
        await wsm.send_all({"t": "new_game", "game": new})
    return {"ok": True, "game": new}

# ── AI O'YIN ENDPOINTLAR ─────────────────────────────────
@app.post("/api/game/quiz")
async def quiz(req: Request):
    b     = await req.json()
    topic = b.get("topic", "umumiy bilim")
    res   = await call_ai(
        [{"role": "user", "content":
          f"O'zbek tilida {topic} bo'yicha test savoli. "
          f'JSON: {{"q":"savol","a":["to\'g\'ri","xato1","xato2","xato3"],"correct":0,"explain":"izoh"}}. FAQAT JSON.'}],
        "Faqat toza JSON qaytargin.", 300,
    )
    if not res["ok"]:
        raise HTTPException(500, res["error"])
    try:
        text = res["text"].replace("```json", "").replace("```", "").strip()
        d    = json.loads(text)
        return {"ok": True, "q": d}
    except Exception:
        raise HTTPException(500, "JSON xatosi")

@app.post("/api/game/word")
async def word_game():
    res = await call_ai(
        [{"role": "user", "content":
          'O\'zbek tilida 5-7 harfli so\'z va izoh. JSON: {"word":"SO\'Z","hint":"ma\'nosi"}. FAQAT JSON.'}],
        "Faqat toza JSON.", 150,
    )
    try:
        text = res["text"].replace("```json", "").replace("```", "").strip()
        d    = json.loads(text)
        return {"ok": True, "w": d}
    except Exception:
        return {"ok": True, "w": {"word": "KITOB", "hint": "O'qish uchun"}}

@app.post("/api/game/story")
async def story(req: Request):
    b      = await req.json()
    choice = b.get("choice", "")
    if not choice:
        prompt = "O'zbek tilida qiziqarli interaktiv hikoya boshlang."
    else:
        prompt = f'Tanlangan yo\'l: "{choice}". Hikoya davom etsin.'
    prompt += ' JSON: {"story":"2-3 jumla","choices":["tanlov1","tanlov2","tanlov3"]}. FAQAT JSON.'
    res = await call_ai(
        [{"role": "user", "content": prompt}],
        "Faqat toza JSON.", 400,
    )
    try:
        text = res["text"].replace("```json", "").replace("```", "").strip()
        d    = json.loads(text)
        return {"ok": True, "s": d}
    except Exception:
        raise HTTPException(500, "JSON xatosi")

@app.post("/api/game/ai-gen-system")
async def gen_system(req: Request):
    b    = await req.json()
    name = b.get("name", "")
    desc = b.get("desc", "")
    res  = await call_ai(
        [{"role": "user", "content":
          f"Agent nomi: {name}\nVazifasi: {desc}\n\nProfessional system prompt yoz. O'zbek tilida. FAQAT PROMPT."}],
        "Faqat toza system prompt yoz. Hech qanday izoh yo'q.", 400,
    )
    return {"ok": res["ok"], "system": res["text"], "error": res.get("error", "")}

@app.post("/api/discover")
async def discover_agent():
    res = await call_ai(
        [{"role": "user", "content":
          '2025-2026 yangi AI texnologiyasidan BITTA agent. '
          'JSON: {"id":"snake_id","icon":"emoji","name":"O\'zbek nom",'
          '"cat":"ai|media|finance|dev|social","desc":"ta\'rif","system":"O\'zbek prompt","color":"#hex"}. FAQAT JSON.'}],
        "Faqat toza JSON.", 350,
    )
    if not res["ok"]:
        return {"ok": False, "error": res["error"]}
    try:
        text = res["text"].replace("```json", "").replace("```", "").strip()
        d    = json.loads(text)
        return {"ok": True, "agent": d}
    except Exception:
        return {"ok": False, "error": "JSON xatosi"}

# ── WEBSOCKET ────────────────────────────────────────────
@app.websocket("/ws")
async def ws_ep(websocket: WebSocket):
    await wsm.add(websocket)
    try:
        await websocket.send_json({
            "t": "welcome", "v": VER,
            "agents": len(agents), "games": len(games),
        })
        for a in agents:
            if a.get("public"):
                await websocket.send_json({"t": "new_agent", "agent": a})
        for g in games:
            if g.get("public"):
                await websocket.send_json({"t": "new_game", "game": g})
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=25)
                if msg == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_json({"t": "heartbeat"})
    except WebSocketDisconnect:
        wsm.rm(websocket)
    except Exception:
        wsm.rm(websocket)

# ════════════════════════════════════════════════════════
# ADMIN API
# ════════════════════════════════════════════════════════

@app.post("/admin/login")
def adm_login(r: AuthReq):
    if r.username != ADM_USER or r.password != ADM_PASS:
        raise HTTPException(401, "Xato login/parol")
    tok = mktoken(f"admin_{r.username}")
    sessions[tok] = f"admin{r.username}"
    return {"ok": True, "token": tok}

@app.get("/admin/stats")
def adm_stats(a=Depends(get_admin)):
    today  = datetime.now().strftime("%Y-%m-%d")
    trades = analytics.get("trades", [])
    return {
        "users": len(users), "sessions": len(sessions),
        "chats": len(logs),
        "today_chats": sum(1 for l in logs if l.get("t", "").startswith(today)),
        "ws": len(wsm.ws), "agents": len(agents), "games": len(games),
        "trades": len(trades),
        "today_trades": sum(1 for t in trades if t.get("t", "").startswith(today)),
        "version": VER,
    }

@app.get("/admin/users")
def adm_users(a=Depends(get_admin)):
    return {
        "ok": True,
        "users": [
            {"username": k, **{x: v for x, v in u.items() if x != "password"}}
            for k, u in users.items()
        ],
    }

@app.delete("/admin/users/{username}")
async def adm_del_user(username: str, a=Depends(get_admin)):
    if username not in users:
        raise HTTPException(404, "User topilmadi")
    del users[username]
    db_save("users", users)
    return {"ok": True}

@app.get("/admin/agents")
def adm_agents(a=Depends(get_admin)):
    return {"ok": True, "agents": agents}

@app.post("/admin/agents")
async def adm_add_agent(req: Request, a=Depends(get_admin)):
    data = await req.json()
    data["adminAdded"] = True
    data["created"]    = datetime.now().isoformat()
    agents.append(data)
    db_save("agents", agents)
    await wsm.send_all({"t": "new_agent", "agent": data})
    return {"ok": True, "broadcast": len(wsm.ws)}

@app.delete("/admin/agents/{aid}")
async def adm_del_agent(aid: str, a=Depends(get_admin)):
    agents[:] = [x for x in agents if x.get("id") != aid]
    db_save("agents", agents)
    await wsm.send_all({"t": "rm_agent", "id": aid})
    return {"ok": True}

@app.get("/admin/games")
def adm_games(a=Depends(get_admin)):
    return {"ok": True, "games": games}

@app.delete("/admin/games/{gid}")
async def adm_del_game(gid: str, a=Depends(get_admin)):
    games[:] = [x for x in games if x.get("id") != gid]
    db_save("games", games)
    return {"ok": True}

@app.get("/admin/logs")
def adm_logs(a=Depends(get_admin)):
    return {"ok": True, "logs": logs[-200:]}

# ── ROOT ─────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def root():
    index_file = Path(__file__).parent / "static" / "index.html"
    if index_file.exists():
        return HTMLResponse(index_file.read_text(encoding="utf-8"))
    return HTMLResponse(UI_HTML)

# ── MAIN ─────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
