#!/usr/bin/env python3
"""
Démarre le bot Discord ET l'API FastAPI dans le même processus
pour accéder directement aux données en temps réel
"""

import asyncio
import threading
import uvicorn
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def start_api():
    """Start FastAPI in a separate thread"""
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

async def start_bot():
    """Start the Discord bot"""
    # Import and run the bot
    from main import run_bot
    await run_bot()

if __name__ == "__main__":
    print("🚀 Starting both Discord bot and API in same container...")
    
    # Start API in background thread
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()
    
    # Start bot in main thread
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        print("---> Bot and API stopped by user.")