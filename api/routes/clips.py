"""
Clip suggestion and management endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.database import db
from api.models.schemas import ClipStatus, Platform

router = APIRouter()


class ClipSuggestionResponse(BaseModel):
    id: str
    video_id: str
    start_time: float
    end_time: float
    duration: Optional[float] = None
    transcript_excerpt: Optional[str]
    platform: str
    hook_reason: Optional[str]
    confidence_score: Optional[float]
    status: str
    created_at: str


class ClipUpdateRequest(BaseModel):
    status: Optional[ClipStatus] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class ClipUpdateResponse(BaseModel):
    id: str
    status: str
    message: str


@router.get("/videos/{video_id}/suggestions", response_model=List[ClipSuggestionResponse])
async def get_clip_suggestions(video_id: str):
    """
    Get all clip suggestions for a video.

    Returns suggestions sorted by start time.
    Each suggestion includes platform target (linkedin/tiktok/both),
    hook reason, and confidence score.
    """
    # Verify video exists
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Get suggestions
    suggestions = db.get_clip_suggestions(video_id)

    # Add duration to each suggestion
    for s in suggestions:
        s["duration"] = s["end_time"] - s["start_time"]

    return suggestions


@router.get("/clips/{clip_id}", response_model=ClipSuggestionResponse)
async def get_clip(clip_id: str):
    """Get a single clip suggestion by ID."""
    clip = db.get_clip_suggestion(clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    clip["duration"] = clip["end_time"] - clip["start_time"]
    return clip


@router.patch("/clips/{clip_id}", response_model=ClipUpdateResponse)
async def update_clip(clip_id: str, update: ClipUpdateRequest):
    """
    Update a clip suggestion.

    Can update:
    - status: pending, approved, rejected, rendered
    - start_time: Adjust clip start boundary
    - end_time: Adjust clip end boundary
    """
    clip = db.get_clip_suggestion(clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    update_data = {}

    if update.status is not None:
        update_data["status"] = update.status.value

    if update.start_time is not None:
        if update.start_time < 0:
            raise HTTPException(status_code=400, detail="start_time must be >= 0")
        update_data["start_time"] = update.start_time

    if update.end_time is not None:
        start = update.start_time if update.start_time is not None else clip["start_time"]
        if update.end_time <= start:
            raise HTTPException(status_code=400, detail="end_time must be > start_time")
        update_data["end_time"] = update.end_time

    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    db.update_clip_suggestion(clip_id, **update_data)

    return ClipUpdateResponse(
        id=clip_id,
        status=update_data.get("status", clip["status"]),
        message="Clip updated successfully",
    )


@router.post("/clips/{clip_id}/approve", response_model=ClipUpdateResponse)
async def approve_clip(clip_id: str):
    """Approve a clip suggestion for rendering."""
    clip = db.get_clip_suggestion(clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    db.update_clip_suggestion(clip_id, status="approved")

    return ClipUpdateResponse(
        id=clip_id,
        status="approved",
        message="Clip approved for rendering",
    )


@router.post("/clips/{clip_id}/reject", response_model=ClipUpdateResponse)
async def reject_clip(clip_id: str):
    """Reject a clip suggestion."""
    clip = db.get_clip_suggestion(clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    db.update_clip_suggestion(clip_id, status="rejected")

    return ClipUpdateResponse(
        id=clip_id,
        status="rejected",
        message="Clip rejected",
    )
