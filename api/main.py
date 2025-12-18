"""
FastAPI application for Video Clipper.

Provides endpoints for video upload, transcription, clip suggestions, and rendering.

Usage:
    uvicorn api.main:app --reload --port 8000
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from api.models.schemas import HealthResponse

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    print("Starting Video Clipper API...")
    yield
    # Shutdown
    print("Shutting down Video Clipper API...")


app = FastAPI(
    title="Video Clipper API",
    description="Video transcription and clip suggestion service",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3010",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3010",
    "https://posts.ab-civil.com",
    "https://video-clipper.ab-civil.com",
    # Vercel preview/production domains
    "https://social-media-posts.vercel.app",
    "https://*.vercel.app",
]

# Add any additional origins from environment
extra_origins = os.getenv("CORS_ORIGINS", "").split(",")
allowed_origins.extend([o.strip() for o in extra_origins if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint - returns service health."""
    return HealthResponse()


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for monitoring."""
    return HealthResponse()


@app.get("/api/health", response_model=HealthResponse)
async def api_health_check():
    """API health check endpoint."""
    return HealthResponse()


# Include routers
from api.routes import upload, videos, transcripts, clips

app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(videos.router, prefix="/api", tags=["videos"])
app.include_router(transcripts.router, prefix="/api", tags=["transcripts"])
app.include_router(clips.router, prefix="/api", tags=["clips"])


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
    )
