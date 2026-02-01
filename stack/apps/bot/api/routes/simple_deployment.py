from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import json
import os
from datetime import datetime

# Initialize FastAPI router for deployment endpoints
router = APIRouter()

# Request model for deployment notification
# Public API only exposes deployment status; live notify moved to Live API

# Check if deployment notification has been sent
@router.get("/deployment/check-status")
async def check_deployment_status():
    notification_file = 'data/deployment_notification.json'
    
    if not os.path.exists(notification_file):
        return {
            "status": "no_notification",
            "message": "No deployment notification pending"
        }
    
    try:
        with open(notification_file, 'r') as f:
            data = json.load(f)
        
        return {
            "status": data.get("status", "pending"),
            "version": data.get("version"),
            "users_notified": data.get("total_users", 0),
            "timestamp": data.get("timestamp")
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error reading notification file: {e}"
        }
