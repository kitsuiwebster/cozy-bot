from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .routes import top_users, top_servers, admin
from .routes.stats import router as stats_router
from .routes.simple_deployment import router as simple_deployment_router
from .routes.audio_restore import router as audio_restore_router
import logging

# Initialize FastAPI application
app = FastAPI(
    title="CozyBot API",
    description="REST API for CozyBot Discord bot statistics",
    version="1.0.21"
)

# Configure CORS for web access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://kitsuiwebster.com",
        "http://90.60.191.159:8000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Include routers
app.include_router(top_users.router, prefix="/api", tags=["users"])
app.include_router(top_servers.router, prefix="/api", tags=["servers"])
app.include_router(stats_router, prefix="/api", tags=["stats"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(simple_deployment_router, prefix="/api", tags=["simple-deployment"])
app.include_router(audio_restore_router, prefix="/api", tags=["audio"])

@app.get("/")
async def root():
    return {"message": "CozyBot API with LIVE Bot Access", "version": "1.0.21"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "mode": "live_bot_access"}
