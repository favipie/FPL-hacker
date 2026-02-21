const express = require("express");
const cors = require("cors");
const https = require("https");
const path = require("path");
const NodeCache = require("node-cache");

const app = express();
const cache = new NodeCache({ stdTTL: 300 }); // 5-min cache

app.use(cors({ origin: "*" }));
app.use(express.json());

// Serve frontend
app.use(express.static(path.join(__dirname)));
app.get("/", (req, res) => res.sendFile(path.join(__dirname, "index.html")));

const FPL_BASE = "https://fantasy.premierleague.com/api";
const FPL_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
  Accept: "application/json, text/plain, */*",
  "Accept-Language": "en-US,en;q=0.9",
  Referer: "https://fantasy.premierleague.com/",
  Origin: "https://fantasy.premierleague.com",
  Connection: "keep-alive",
};

// ─── FPL fetch helper (raw https, no axios needed) ───────────────────────────
function fetchFPL(path) {
  return new Promise((resolve, reject) => {
    const url = FPL_BASE + path;
    const req = https.get(url, { headers: FPL_HEADERS }, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(new Error(`Parse error on ${path}: ${e.message}`));
        }
      });
    });
    req.on("error", reject);
    req.setTimeout(10000, () => {
      req.destroy();
      reject(new Error(`Timeout on ${path}`));
    });
  });
}

// ─── Cached wrapper ───────────────────────────────────────────────────────────
async function cachedFetch(key, path, ttl = 300) {
  const hit = cache.get(key);
  if (hit) {
    console.log(`  [CACHE HIT] ${key}`);
    return hit;
  }
  console.log(`  [FETCH] ${FPL_BASE}${path}`);
  const data = await fetchFPL(path);
  cache.set(key, data, ttl);
  return data;
}

// ─── ROUTES ──────────────────────────────────────────────────────────────────

// Health check
app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    uptime: Math.round(process.uptime()) + "s",
    cache_keys: cache.keys().length,
    timestamp: new Date().toISOString(),
  });
});

// Bootstrap (players, teams, events) — heavy, cache 5 min
app.get("/api/bootstrap", async (req, res) => {
  try {
    const data = await cachedFetch("bootstrap", "/bootstrap-static/", 300);
    res.json({ ok: true, data });
  } catch (e) {
    console.error("bootstrap error:", e.message);
    res.status(502).json({ ok: false, error: e.message });
  }
});

// Fixtures — cache 10 min
app.get("/api/fixtures", async (req, res) => {
  try {
    const data = await cachedFetch("fixtures", "/fixtures/", 600);
    res.json({ ok: true, data });
  } catch (e) {
    res.status(502).json({ ok: false, error: e.message });
  }
});

// Individual player detail (history, season history)
app.get("/api/player/:id", async (req, res) => {
  const id = parseInt(req.params.id);
  if (!id || id < 1 || id > 1000) return res.status(400).json({ ok: false, error: "Invalid id" });
  try {
    const data = await cachedFetch(`player_${id}`, `/element-summary/${id}/`, 600);
    res.json({ ok: true, data });
  } catch (e) {
    res.status(502).json({ ok: false, error: e.message });
  }
});

// Live gameweek scores
app.get("/api/live/:gw", async (req, res) => {
  const gw = parseInt(req.params.gw);
  if (!gw || gw < 1 || gw > 38) return res.status(400).json({ ok: false, error: "Invalid GW" });
  try {
    const data = await cachedFetch(`live_${gw}`, `/event/${gw}/live/`, 60); // 1-min cache for live
    res.json({ ok: true, data });
  } catch (e) {
    res.status(502).json({ ok: false, error: e.message });
  }
});

// Gameweek picks for a manager
app.get("/api/entry/:id/gw/:gw", async (req, res) => {
  const { id, gw } = req.params;
  try {
    const data = await cachedFetch(`entry_${id}_${gw}`, `/entry/${id}/event/${gw}/picks/`, 300);
    res.json({ ok: true, data });
  } catch (e) {
    res.status(502).json({ ok: false, error: e.message });
  }
});

// Flush cache (dev only)
app.post("/api/cache/flush", (req, res) => {
  cache.flushAll();
  res.json({ ok: true, message: "Cache flushed" });
});

// Cache stats
app.get("/api/cache/stats", (req, res) => {
  res.json({ ok: true, keys: cache.keys(), stats: cache.getStats() });
});

// ─── START ────────────────────────────────────────────────────────────────────
const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`\n  ┌───────────────────────────────────────┐`);
  console.log(`  │  FPL HAZARD BACKEND  v1.0              │`);
  console.log(`  │  http://localhost:${PORT}                  │`);
  console.log(`  │                                       │`);
  console.log(`  │  Routes:                              │`);
  console.log(`  │   GET  /health                        │`);
  console.log(`  │   GET  /api/bootstrap                 │`);
  console.log(`  │   GET  /api/fixtures                  │`);
  console.log(`  │   GET  /api/live/:gw                  │`);
  console.log(`  │   GET  /api/player/:id                │`);
  console.log(`  │   GET  /api/entry/:id/gw/:gw          │`);
  console.log(`  └───────────────────────────────────────┘\n`);
});
