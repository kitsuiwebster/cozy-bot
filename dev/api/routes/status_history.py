import asyncio
import logging
import os
import time
from typing import List, Dict, Any

import aiohttp
from fastapi import APIRouter, HTTPException, Query

from utils.storage.couchdb_client import get_couchdb_client

router = APIRouter()

_MONITOR_CONFIG = [
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

STATUS_HISTORY_ENABLED = os.getenv("STATUS_HISTORY_ENABLED", "1") == "1"
STATUS_HISTORY_INTERVAL = int(os.getenv("STATUS_HISTORY_INTERVAL_SECONDS", "60"))
STATUS_HISTORY_RETENTION_DAYS = int(os.getenv("STATUS_HISTORY_RETENTION_DAYS", "90"))
STATUS_PAGE_SLUG = os.getenv("STATUS_PAGE_SLUG", "cozy")
STATUS_PAGE_URL = os.getenv("STATUS_PAGE_URL", "http://uptime-kuma:3001")


def _status_doc_id(timestamp_ms: int) -> str:
    return f"status:{timestamp_ms:013d}"


async def _check_url(session: aiohttp.ClientSession, url: str) -> Dict[str, Any]:
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


async def _collect_status_point() -> Dict[str, Any]:
    async with aiohttp.ClientSession() as session:
        checks = []
        for monitor in _MONITOR_CONFIG:
            result = await _check_url(session, monitor["url"])
            checks.append({
                "id": monitor["id"],
                "up": bool(result.get("up")),
                "latency_ms": result.get("latency_ms", 0),
                "status": result.get("status"),
            })
        return checks


async def _fetch_maintenance() -> List[Dict[str, Any]]:
    url = f"{STATUS_PAGE_URL}/api/status-page/{STATUS_PAGE_SLUG}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(f"status {response.status}")
                payload = await response.json()
                return payload.get("maintenanceList", []) or []
    except Exception as exc:
        logging.error(f"❌ Failed to fetch maintenance list: {exc}")
        return []


async def _save_status_point(timestamp_ms: int, checks: List[Dict[str, Any]]) -> None:
    db = get_couchdb_client()
    doc_id = _status_doc_id(timestamp_ms)
    payload = {
        "type": "status",
        "timestamp_ms": timestamp_ms,
        "checks": checks,
    }
    await asyncio.to_thread(db.save_document, db.db, doc_id, payload)


async def _prune_old_points() -> None:
    db = get_couchdb_client()
    cutoff_ms = int(time.time() * 1000) - (STATUS_HISTORY_RETENTION_DAYS * 24 * 60 * 60 * 1000)
    end_key = _status_doc_id(cutoff_ms - 1)
    docs = await asyncio.to_thread(db.get_documents_by_range, "status:", "0000000000000", end_key)
    if not docs:
        return
    for doc_id in docs.keys():
        await asyncio.to_thread(db.delete_document, db.db, doc_id)


async def _sync_maintenance() -> List[Dict[str, Any]]:
    db = get_couchdb_client()
    active_items = await _fetch_maintenance()
    existing = await asyncio.to_thread(db.load_all_maintenance)

    active_ids = set()
    for item in active_items:
        maintenance_id = str(item.get("id"))
        if not maintenance_id:
            continue
        active_ids.add(maintenance_id)
        previous = existing.get(maintenance_id, {})
        started_at = previous.get("started_at") or datetime.utcnow().isoformat()
        payload = {
            "id": item.get("id"),
            "title": item.get("title"),
            "description": item.get("description"),
            "status": item.get("status") or "under-maintenance",
            "active": True,
            "timezone": item.get("timezone") or item.get("timezoneOption"),
            "started_at": started_at,
            "ended_at": previous.get("ended_at"),
            "date_range": item.get("dateRange"),
            "time_range": item.get("timeRange"),
        }
        await asyncio.to_thread(db.save_maintenance, maintenance_id, payload)

    # Mark previously active items as completed if they're no longer active
    for maintenance_id, doc in existing.items():
        if doc.get("active") and maintenance_id not in active_ids:
            payload = doc.copy()
            payload["active"] = False
            payload["status"] = "completed"
            payload["ended_at"] = payload.get("ended_at") or datetime.utcnow().isoformat()
            await asyncio.to_thread(db.save_maintenance, maintenance_id, payload)

    # Return full history for API consumption
    history = await asyncio.to_thread(db.load_all_maintenance)
    return [{"id": k, **v} for k, v in history.items()]


async def status_history_loop() -> None:
    if not STATUS_HISTORY_ENABLED:
        logging.info("🔥 Status history disabled (STATUS_HISTORY_ENABLED=0)")
        return

    logging.info("🔥 Status history loop started")
    iteration = 0
    while True:
        try:
            timestamp_ms = int(time.time() * 1000)
            checks = await _collect_status_point()
            await _save_status_point(timestamp_ms, checks)
            iteration += 1

            if iteration % 60 == 0:
                await _prune_old_points()

            if iteration % 5 == 0:
                await _sync_maintenance()
        except Exception as exc:
            logging.error(f"❌ Status history loop error: {exc}")

        await asyncio.sleep(STATUS_HISTORY_INTERVAL)


@router.get("/status/monitors")
async def get_status_monitors():
    return {"monitors": [{"id": m["id"], "name": m["name"]} for m in _MONITOR_CONFIG]}


@router.get("/status/history")
async def get_status_history(
    window: str = Query("90d", description="Window: 1h, 24h, 7d, 30d, 90d")
):
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
    start_key = _status_doc_id(start_ms)
    end_key = _status_doc_id(now_ms)

    db = get_couchdb_client()
    docs = db.get_documents_by_range("status:", start_key, end_key)
    points = []
    for doc_id, doc in docs.items():
        points.append({
            "timestamp_ms": doc.get("timestamp_ms"),
            "checks": doc.get("checks", []),
        })

    points.sort(key=lambda p: p.get("timestamp_ms", 0))
    return {"points": points}


@router.get("/status/maintenance")
async def get_status_maintenance():
    history = await _sync_maintenance()
    active = [item for item in history if item.get("active")]
    inactive = [item for item in history if not item.get("active")]
    inactive.sort(key=lambda item: item.get("id", 0), reverse=True)
    return {"active": active, "history": inactive}
