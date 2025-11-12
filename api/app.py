from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .routes import top_users, top_servers
from .routes.stats import router as stats_router
import logging

# Initialize FastAPI application
app = FastAPI(
    title="CozyBot API",
    description="REST API for CozyBot Discord bot statistics - LIVE ACCESS",
    version="1.0.0"
)

# Configure CORS for web access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Développement
        "https://votre-site.com",  # Production
        "*"  # Ou "*" pour tous (moins sécurisé)
    ],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Include routers
app.include_router(top_users.router, prefix="/api", tags=["users"])
app.include_router(top_servers.router, prefix="/api", tags=["servers"])
app.include_router(stats_router, prefix="/api", tags=["stats"])

@app.get("/")
async def root():
    return {"message": "CozyBot API with LIVE Bot Access", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "mode": "live_bot_access"}