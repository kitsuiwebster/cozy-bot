from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
from datetime import datetime

# Initialize FastAPI router for deployment endpoints
router = APIRouter()

# Request model for deployment notification
# Public API only exposes deployment status; live notify moved to Live API

def _load_notification():
    try:
        from utils.storage.couchdb_client import get_couchdb_client
        db = get_couchdb_client()
        doc = db.get_document(db.db, "deployment_notification")
        if doc and "type" in doc:
            doc = {k: v for k, v in doc.items() if k != "type"}
        return doc
    except Exception:
        return None

# Check if deployment notification has been sent
@router.get("/deployment/check-status")
async def check_deployment_status():
    try:
        data = _load_notification()
        if not data:
            return {
                "status": "no_notification",
                "message": "No deployment notification pending"
            }

        return {
            "status": data.get("status", "pending"),
            "version": data.get("version"),
            "users_notified": data.get("total_users", 0),
            "timestamp": data.get("timestamp")
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error reading deployment status: {e}"
        }
