from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .routes import top_users, top_servers, admin
from .routes.stats import router as stats_router
import logging

# Initialize FastAPI application
app = FastAPI(
    title="CozyBot API",
    description="REST API for CozyBot Discord bot statistics",
    version="1.0.14"
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

@app.get("/")
async def root():
    return {"message": "CozyBot API with LIVE Bot Access", "version": "1.0.14"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "mode": "live_bot_access"}