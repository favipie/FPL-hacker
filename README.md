# FPL Hazard — Backend Proxy Server

Bypasses the FPL API's CORS restriction so the frontend can fetch live data directly.

## Setup (2 minutes)

### 1. Make sure you have Node.js installed
```bash
node --version   # should be v16+
```
If not, download from https://nodejs.org

### 2. Install dependencies
```bash
cd fpl-hazard-backend
npm install
```

### 3. Start the server
```bash
npm start
```

You'll see:
```
  ┌───────────────────────────────────────┐
  │  FPL HAZARD BACKEND  v1.0              │
  │  http://localhost:3001                  │
  └───────────────────────────────────────┘
```

### 4. Open the app
Open your browser and go to:
```
http://localhost:3001
```

That's it — live FPL GW27 data will load automatically! 🚀

---

## API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/` | Frontend app |
| GET | `/health` | Server health + uptime |
| GET | `/api/bootstrap` | All players, teams, GW events |
| GET | `/api/fixtures` | All fixtures with FDR ratings |
| GET | `/api/live/:gw` | Live GW scores (1-min cache) |
| GET | `/api/player/:id` | Individual player history |
| GET | `/api/entry/:id/gw/:gw` | Manager's GW picks |
| GET | `/api/cache/stats` | Cache stats |
| POST | `/api/cache/flush` | Clear cache |

---

## How it works

```
Browser (index.html)
      │
      │  fetch("http://localhost:3001/api/bootstrap")
      ▼
Express Server (server.js)
      │
      │  https.get("https://fantasy.premierleague.com/api/bootstrap-static/")
      │  + proper browser headers (bypasses CORS)
      │  + 5-minute in-memory cache (NodeCache)
      ▼
FPL API → data → cache → JSON response → frontend
```

The FPL API only blocks *browser* requests (CORS policy). 
Server-to-server requests work fine — that's all this does.

---

## Caching

| Endpoint | TTL |
|----------|-----|
| Bootstrap (players/teams) | 5 minutes |
| Fixtures | 10 minutes |
| Live GW scores | 1 minute |
| Player history | 10 minutes |

Cache auto-refreshes on next request after TTL expires.

---

## Dev mode (auto-restart on file changes)
```bash
npm run dev
```

## Deploy to the web (optional)

If you want to share the app publicly, deploy to **Railway** or **Render** (both free):

```bash
# Railway
npm install -g @railway/cli
railway login
railway init
railway up

# Render — push to GitHub, connect repo at render.com
```

Then update `BACKEND` in `index.html` to your deployed URL.
