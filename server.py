import asyncio
import threading
import uvicorn
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Start FastAPI server in background thread
def start_api():
    ssl_keyfile = "/etc/letsencrypt/live/cozybotapi.kitsuiwebster.com/privkey.pem"
    ssl_certfile = "/etc/letsencrypt/live/cozybotapi.kitsuiwebster.com/fullchain.pem"

    if os.path.exists(ssl_keyfile) and os.path.exists(ssl_certfile):
        logging.info("🔒 Starting API with HTTPS...")
        uvicorn.run(
            "api.app:app",
            host="0.0.0.0",
            port=8000,
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

# Start Discord bot in main thread
async def start_bot():
    from main import run_bot
    await run_bot()

# Main entry point - start API in background thread and bot in main thread
if __name__ == "__main__":
    logging.info("✨✨✨ Starting both Discord bot and API in same container...")

    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()

    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logging.info("🛑 Bot and API stopped by user.")

