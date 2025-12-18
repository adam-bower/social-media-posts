"""
Transcript endpoints.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from api.database import db

router = APIRouter()


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    confidence: Optional[float] = None
    words: Optional[List[dict]] = None


class TranscriptResponse(BaseModel):
    id: str
    video_id: str
    full_text: str
    segments: List[TranscriptSegment]
    language: str
    language_probability: Optional[float]
    model_used: str
    processing_time_seconds: Optional[float]
    created_at: str


@router.get("/videos/{video_id}/transcript", response_model=TranscriptResponse)
async def get_transcript(video_id: str):
    """
    Get the transcript for a video.

    Returns the full text and segment-level timestamps.
    Each segment includes word-level timestamps if available.
    """
    # Verify video exists
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Check if video is processed
    if video["status"] not in ["ready", "transcribed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Transcript not available. Video status: {video['status']}",
        )

    # Get transcript
    transcript = db.get_transcript(video_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    return transcript
