# ⭐ Ulug'bek AI v7

FastAPI + Anthropic Claude asosidagi AI platforma.

## 🚀 Railway ga Deploy qilish

### 1. GitHub ga yuklash
```bash
git init
git add .
git commit -m "Ulugbek AI v7"
git remote add origin https://github.com/SIZNING_USERNAME/ulugbek-ai.git
git push -u origin main
```

### 2. Railway da sozlash
1. [railway.app](https://railway.app) ga kiring
2. **New Project → Deploy from GitHub repo** tanlang
3. Reponi tanlang
4. **Variables** bo'limiga quyidagilarni kiriting:

| Variable | Qiymat |
|----------|--------|
| `ANTHROPIC_API_KEY` | `sk-ant-...` (majburiy) |
| `ADMIN_USERNAME` | `admin` |
| `ADMIN_PASSWORD` | kuchli parol kiriting |
| `SECRET_KEY` | tasodifiy uzun satr |

5. Deploy avtomatik boshlanadi ✅

## 📡 API Endpointlar

| Endpoint | Method | Tavsif |
|----------|--------|--------|
| `/health` | GET | Server holati |
| `/api/register` | POST | Ro'yxatdan o'tish |
| `/api/login` | POST | Kirish |
| `/api/chat` | POST | AI chat |
| `/api/prices` | GET | Kripto/aksiya narxlari |
| `/api/trade` | POST | Savdo (auth kerak) |
| `/api/portfolio` | GET | Portfolio (auth kerak) |
| `/api/agents` | GET/POST | Agentlar |
| `/api/games` | GET/POST | O'yinlar |
| `/ws` | WS | Real-time WebSocket |
| `/admin/login` | POST | Admin kirish |
| `/docs` | GET | Swagger UI |

## 🔑 Muhim eslatma
Railway **ephemeral storage** ishlatadi — server restart bo'lsa ma'lumotlar o'chadi.
Doimiy saqlash uchun Railway PostgreSQL yoki Redis qo'shing.
