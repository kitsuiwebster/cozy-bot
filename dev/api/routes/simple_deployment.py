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
class DeploymentRequest(BaseModel):
    version: str
    delay_seconds: Optional[int] = 30

# Create a deployment notification file that the bot will check
@router.post("/deployment/simple-notify")
async def simple_deployment_notify(request: DeploymentRequest):
    try:
        from api.routes.stats import bot_instance
        
        if bot_instance is None:
            raise HTTPException(status_code=503, detail="Bot not available")
        
        # Count active users
        total_users = 0
        active_guilds = []
        
        for guild in bot_instance.guilds:
            voice_client = guild.voice_client
            if voice_client and voice_client.channel:
                human_users = [member for member in voice_client.channel.members if not member.bot]
                if human_users:
                    total_users += len(human_users)
                    active_guilds.append({
                        'guild_id': str(guild.id),
                        'guild_name': guild.name,
                        'channel_id': str(voice_client.channel.id),
                        'channel_name': voice_client.channel.name,
                        'user_count': len(human_users),
                        'user_ids': [str(user.id) for user in human_users]
                    })
        
        if total_users == 0:
            return {
                "message": "No active users found",
                "users_notified": 0,
                "proceed_immediately": True
            }
        
        # Create deployment notification file
        notification_data = {
            "version": request.version,
            "delay_seconds": request.delay_seconds,
            "timestamp": datetime.now().isoformat(),
            "total_users": total_users,
            "active_guilds": active_guilds,
            "status": "pending"
        }
        
        os.makedirs('data', exist_ok=True)
        with open('data/deployment_notification.json', 'w') as f:
            json.dump(notification_data, f, indent=2)
        
        logging.info(f"📢 Deployment notification file created for {total_users} users")
        
        return {
            "message": "Deployment notification file created",
            "users_found": total_users,
            "active_guilds": len(active_guilds),
            "proceed_immediately": False
        }
        
    except Exception as e:
        logging.error(f"❌ Error creating deployment notification: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create notification: {str(e)}")

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