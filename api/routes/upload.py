"""
Video upload endpoints.
"""

import os
import uuid
import shutil
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from pydantic import BaseModel

from api.database import db

router = APIRouter()

# Upload directory - configurable via environment
UPLOAD_DIR = os.getenv("VIDEO_UPLOAD_DIR", "/tmp/video-clipper/uploads")


class UploadResponse(BaseModel):
    id: str
    filename: str
    file_size_bytes: int
    status: str
    message: str


def ensure_upload_dir():
    """Ensure upload directory exists."""
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


@router.post("/upload", response_model=UploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
):
    """
    Upload a video file for processing.

    Accepts video files (mp4, mov, webm, avi, mkv) up to 5GB.
    Returns the video ID for tracking processing status.
    """
    # Validate file type
    allowed_types = {
        "video/mp4",
        "video/quicktime",
        "video/webm",
        "video/x-msvideo",
        "video/x-matroska",
    }
    allowed_extensions = {".mp4", ".mov", ".webm", ".avi", ".mkv"}

    if file.content_type not in allowed_types:
        ext = Path(file.filename).suffix.lower()
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}",
            )

    # Generate unique filename
    ext = Path(file.filename).suffix.lower()
    unique_id = str(uuid.uuid4())
    safe_filename = f"{unique_id}{ext}"

    # Ensure upload directory exists
    ensure_upload_dir()
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save file: {str(e)}",
        )

    # Get file size
    file_size = os.path.getsize(file_path)

    # Create database record
    try:
        video = db.create_video(
            filename=file.filename,
            original_path=file_path,
            user_id=user_id,
            file_size_bytes=file_size,
        )
    except Exception as e:
        # Clean up file if database insert fails
        os.remove(file_path)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create database record: {str(e)}",
        )

    return UploadResponse(
        id=video["id"],
        filename=file.filename,
        file_size_bytes=file_size,
        status="uploaded",
        message="Video uploaded successfully. Use POST /api/videos/{id}/process to start processing.",
    )
