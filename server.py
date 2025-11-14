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
import logging

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def start_api():
    """Start FastAPI in a separate thread"""
    # Check if SSL certificates exist
    ssl_keyfile = "/etc/letsencrypt/live/cozybotapi.kitsuiwebster.com/privkey.pem"
    ssl_certfile = "/etc/letsencrypt/live/cozybotapi.kitsuiwebster.com/fullchain.pem"
    
    if os.path.exists(ssl_keyfile) and os.path.exists(ssl_certfile):
        logging.info("🔒 Starting API with HTTPS...")
        uvicorn.run(
            "api.app:app",
            host="0.0.0.0",
            port=8000,  # HTTPS port
            ssl_keyfile=ssl_keyfile,
            ssl_certfile=ssl_certfile,
            log_level="error"
        )
    else:
        logging.warning("⚠️  No SSL certificates found, starting with HTTP...")
        uvicorn.run(
            "api.app:app",
            host="0.0.0.0",
            port=8000,
            log_level="error"
        )

async def start_bot():
    """Start the Discord bot"""
    # Import and run the bot
    from main import run_bot
    await run_bot()

if __name__ == "__main__":
    logging.info("✨✨✨ Starting both Discord bot and API in same container...")
    
    # Start API in background thread
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()
    
    # Start bot in main thread
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logging.info("🛑 Bot and API stopped by user.")
