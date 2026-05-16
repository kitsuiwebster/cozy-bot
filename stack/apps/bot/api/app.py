from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .routes import top_users, top_servers, admin
from .routes.stats import router as stats_router
from .routes.simple_deployment import router as simple_deployment_router
from .routes.audio_restore import router as audio_restore_router
from .routes.health import router as health_router
import logging
import os
import sys

# Default CORS origins for the official prod + local dev frontends.
# Override with CORS_ALLOWED_ORIGINS env var (comma-separated) for staging or
# alternate deployments. Wildcard "*" is intentionally disallowed alongside
# allow_credentials=True (browsers reject that combination anyway).
DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:4200",
    "https://kitsuiwebster.com",
    "https://cozybot.online",
    "https://www.cozybot.online",
    "https://api.cozybot.online",
]

def _load_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    if not raw:
        return DEFAULT_CORS_ORIGINS
    return [o.strip() for o in raw.split(",") if o.strip()]

# Configure logging similar to bot, but with 🔥 for INFO
class FancyFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',
        'INFO': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[35m',
        'RESET': '\033[0m'
    }

    EMOJIS = {
        'DEBUG': '⚙️',
        'INFO': '🔥',
        'WARNING': '⚡',
        'ERROR': '❌',
        'CRITICAL': '💥'
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        emoji = self.EMOJIS.get(record.levelname, '📝')
        reset = self.COLORS['RESET']
        timestamp = self.formatTime(record, '%H:%M:%S')

        if len(emoji) == 1:
            emoji_padded = f"{emoji}  "
        else:
            emoji_padded = f"{emoji} "
        return f"{color}{emoji_padded}[{timestamp}] {record.levelname:<8} {reset}{record.getMessage()}"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

for handler in logger.handlers[:]:
    logger.removeHandler(handler)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(FancyFormatter())
logger.addHandler(handler)

for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    uv_logger = logging.getLogger(name)
    for h in uv_logger.handlers[:]:
        uv_logger.removeHandler(h)
    uv_logger.propagate = False
    uv_logger.addHandler(handler)

# API prefix constant
API_PREFIX = "/api/public"

# Initialize FastAPI application
app = FastAPI(
    title="CozyBot API",
    description="REST API for CozyBot Discord bot statistics",
    version="2.0.5"
)

# Configure CORS for web access
app.add_middleware(
    CORSMiddleware,
    allow_origins=_load_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers (Public API)
app.include_router(health_router, prefix=API_PREFIX, tags=["health"])
app.include_router(top_users.router, prefix=API_PREFIX, tags=["users"])
app.include_router(top_servers.router, prefix=API_PREFIX, tags=["servers"])
app.include_router(stats_router, prefix=API_PREFIX, tags=["stats"])
app.include_router(admin.router, prefix=f"{API_PREFIX}/admin", tags=["admin"])
app.include_router(simple_deployment_router, prefix=API_PREFIX, tags=["simple-deployment"])
app.include_router(audio_restore_router, prefix=API_PREFIX, tags=["audio"])

@app.get("/")
async def root():
    return {"message": "CozyBot Public API", "version": "2.0.5"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "mode": "public_api"}
