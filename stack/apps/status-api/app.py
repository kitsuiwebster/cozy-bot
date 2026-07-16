import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp
import aiosqlite
from fastapi import FastAPI, HTTPException, Query

STATUS_DB_PATH = os.getenv("STATUS_DB_PATH", "/data/status.db")
STATUS_HISTORY_INTERVAL = int(os.getenv("STATUS_HISTORY_INTERVAL_SECONDS", "60"))
STATUS_HISTORY_RETENTION_DAYS = int(os.getenv("STATUS_HISTORY_RETENTION_DAYS", "90"))

STATUS_PAGE_SLUG = os.getenv("STATUS_PAGE_SLUG", "cozy")
STATUS_PAGE_URL = os.getenv("STATUS_PAGE_URL", "http://uptime-kuma:3001")

TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "0") == "1"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_IDS = [c.strip() for c in os.getenv("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]

MONITORS = [
    {
        "id": "public-api",
        "name": "Public API",
        "url": os.getenv("STATUS_MONITOR_PUBLIC_URL", "http://cozy-public-api:8000/api/public/health"),
    },
    {
        "id": "live-bot",
        "name": "Live Bot",
        "url": os.getenv("STATUS_MONITOR_LIVE_URL", "http://cozy-live-bot:8002/api/live/bot/health"),
    },
    {
        "id": "db",
        "name": "Database",
        "url": os.getenv("STATUS_MONITOR_DB_URL", "http://cozy-couchdb:5984/_up"),
    },
]

app = FastAPI()

# Edge-triggered Telegram alerting: mirrors exactly what the status page shows,
# since it reacts to the same `checks` computed by collect_status_point() below.
# None means "not observed yet this process lifetime" - the first observation
# after a status-api restart just seeds state, it never fires an alert, so a
# routine redeploy of status-api can't itself trigger a burst of notifications.
_last_up: Dict[str, Optional[bool]] = {monitor["id"]: None for monitor in MONITORS}
_down_since: Dict[str, float] = {}


def _format_downtime(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


async def send_telegram(session: aiohttp.ClientSession, text: str) -> None:
    if not (TELEGRAM_ENABLED and TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS):
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for chat_id in TELEGRAM_CHAT_IDS:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)):
                pass
        except Exception:
            pass


async def alert_status_transitions(session: aiohttp.ClientSession, checks: List[Dict[str, Any]]) -> None:
    now = time.monotonic()
    for check in checks:
        monitor_id = check["id"]
        current_up = bool(check["up"])
        previous_up = _last_up.get(monitor_id)

        if previous_up is not None and previous_up != current_up:
            name = next((m["name"] for m in MONITORS if m["id"] == monitor_id), monitor_id)
            if current_up:
                downtime = _format_downtime(now - _down_since.get(monitor_id, now))
                await send_telegram(session, f"🟢 <b>{name}</b> is back up (was down {downtime})")
            else:
                _down_since[monitor_id] = now
                await send_telegram(session, f"🔴 <b>{name}</b> is down")

        _last_up[monitor_id] = current_up


async def init_db() -> None:
    async with aiosqlite.connect(STATUS_DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS status_points (
                timestamp_ms INTEGER PRIMARY KEY,
                checks_json TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS maintenance (
                id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            )
            """
        )
        await db.commit()


async def insert_status_point(timestamp_ms: int, checks: List[Dict[str, Any]]) -> None:
    async with aiosqlite.connect(STATUS_DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO status_points (timestamp_ms, checks_json) VALUES (?, ?)",
            (timestamp_ms, json.dumps(checks)),
        )
        await db.commit()


async def load_status_points(start_ms: int, end_ms: int) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(STATUS_DB_PATH) as db:
        cursor = await db.execute(
            "SELECT timestamp_ms, checks_json FROM status_points WHERE timestamp_ms BETWEEN ? AND ? ORDER BY timestamp_ms ASC",
            (start_ms, end_ms),
        )
        rows = await cursor.fetchall()
        await cursor.close()

    points = []
    for ts, checks_json in rows:
        try:
            checks = json.loads(checks_json)
        except json.JSONDecodeError:
            checks = []
        points.append({"timestamp_ms": ts, "checks": checks})
    return points


async def prune_status_points(cutoff_ms: int) -> None:
    async with aiosqlite.connect(STATUS_DB_PATH) as db:
        await db.execute("DELETE FROM status_points WHERE timestamp_ms < ?", (cutoff_ms,))
        await db.commit()


async def save_maintenance(maintenance_id: str, payload: Dict[str, Any]) -> None:
    async with aiosqlite.connect(STATUS_DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO maintenance (id, payload_json) VALUES (?, ?)",
            (maintenance_id, json.dumps(payload)),
        )
        await db.commit()


async def load_maintenance() -> Dict[str, Dict[str, Any]]:
    async with aiosqlite.connect(STATUS_DB_PATH) as db:
        cursor = await db.execute("SELECT id, payload_json FROM maintenance")
        rows = await cursor.fetchall()
        await cursor.close()

    payloads: Dict[str, Dict[str, Any]] = {}
    for maintenance_id, payload_json in rows:
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError:
            payload = {}
        payloads[maintenance_id] = payload
    return payloads


async def fetch_maintenance() -> List[Dict[str, Any]]:
    url = f"{STATUS_PAGE_URL}/api/status-page/{STATUS_PAGE_SLUG}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status < 200 or response.status >= 300:
                    return []
                payload = await response.json()
                return payload.get("maintenanceList", []) or []
        except Exception:
            return []


async def sync_maintenance() -> List[Dict[str, Any]]:
    active_items = await fetch_maintenance()
    existing = await load_maintenance()

    active_ids = set()
    for item in active_items:
        maintenance_id = str(item.get("id"))
        if not maintenance_id:
            continue
        active_ids.add(maintenance_id)
        previous = existing.get(maintenance_id, {})
        payload = {
            "id": item.get("id"),
            "title": item.get("title"),
            "description": item.get("description"),
            "status": item.get("status") or "under-maintenance",
            "active": True,
            "timezone": item.get("timezone") or item.get("timezoneOption"),
            "started_at": previous.get("started_at") or datetime.now(timezone.utc).isoformat(),
            "ended_at": previous.get("ended_at"),
            "date_range": item.get("dateRange"),
            "time_range": item.get("timeRange"),
        }
        await save_maintenance(maintenance_id, payload)

    for maintenance_id, doc in existing.items():
        if doc.get("active") and maintenance_id not in active_ids:
            payload = dict(doc)
            payload["active"] = False
            payload["status"] = "completed"
            payload["ended_at"] = payload.get("ended_at") or datetime.now(timezone.utc).isoformat()
            await save_maintenance(maintenance_id, payload)

    history = await load_maintenance()
    return [{"id": key, **value} for key, value in history.items()]


async def check_url(session: aiohttp.ClientSession, url: str) -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            latency_ms = int((time.perf_counter() - start) * 1000)
            return {
                "up": 200 <= response.status < 300,
                "latency_ms": latency_ms,
                "status": response.status,
            }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "up": False,
            "latency_ms": latency_ms,
            "status": None,
            "error": str(exc),
        }


async def collect_status_point() -> List[Dict[str, Any]]:
    async with aiohttp.ClientSession() as session:
        checks = []
        for monitor in MONITORS:
            result = await check_url(session, monitor["url"])
            checks.append({
                "id": monitor["id"],
                "up": bool(result.get("up")),
                "latency_ms": result.get("latency_ms", 0),
                "status": result.get("status"),
            })
        await alert_status_transitions(session, checks)
        return checks


async def status_loop() -> None:
    await init_db()
    iteration = 0
    while True:
        timestamp_ms = int(time.time() * 1000)
        try:
            checks = await collect_status_point()
            await insert_status_point(timestamp_ms, checks)
            iteration += 1

            if iteration % 60 == 0:
                cutoff_ms = int(time.time() * 1000) - (STATUS_HISTORY_RETENTION_DAYS * 24 * 60 * 60 * 1000)
                await prune_status_points(cutoff_ms)

            if iteration % 5 == 0:
                await sync_maintenance()
        except Exception:
            pass

        await asyncio.sleep(STATUS_HISTORY_INTERVAL)


@app.on_event("startup")
async def on_startup() -> None:
    asyncio.create_task(status_loop())


@app.get("/api/status/monitors")
async def get_status_monitors() -> Dict[str, Any]:
    return {"monitors": [{"id": monitor["id"], "name": monitor["name"]} for monitor in MONITORS]}


@app.get("/api/status/history")
async def get_status_history(
    window: str = Query("90d", description="Window: 1h, 24h, 7d, 30d, 90d")
) -> Dict[str, Any]:
    window = window.strip().lower()
    if window.endswith("h"):
        hours = int(window[:-1])
        window_ms = hours * 60 * 60 * 1000
    elif window.endswith("d"):
        days = int(window[:-1])
        window_ms = days * 24 * 60 * 60 * 1000
    else:
        raise HTTPException(status_code=400, detail="Invalid window format")

    now_ms = int(time.time() * 1000)
    start_ms = now_ms - window_ms
    points = await load_status_points(start_ms, now_ms)
    return {"points": points}


@app.get("/api/status/maintenance")
async def get_status_maintenance() -> Dict[str, Any]:
    history = await sync_maintenance()
    active = [item for item in history if item.get("active")]
    inactive = [item for item in history if not item.get("active")]
    inactive.sort(key=lambda item: item.get("id", 0), reverse=True)
    return {"active": active, "history": inactive}
