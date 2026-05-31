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
    return HTMLResponse("<h1>⭐ Ulug'bek AI v7</h1><p><a href='/docs'>API Docs</a></p>")

# ── MAIN ─────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
