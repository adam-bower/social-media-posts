"""
Pydantic models for API request/response schemas.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class VideoStatus(str, Enum):
    UPLOADED = "uploaded"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    READY = "ready"
    ERROR = "error"


class ClipStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RENDERED = "rendered"


class Platform(str, Enum):
    LINKEDIN = "linkedin"
    TIKTOK = "tiktok"
    YOUTUBE_SHORTS = "youtube_shorts"
    INSTAGRAM_REELS = "instagram_reels"
    BOTH = "both"


class ExportStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SilencePreset(str, Enum):
    LINKEDIN = "linkedin"  # Conservative editing
    TIKTOK = "tiktok"  # Aggressive editing
    YOUTUBE_SHORTS = "youtube_shorts"  # Medium editing
    PODCAST = "podcast"  # Very light editing


# Word-level timestamp
class WordTimestamp(BaseModel):
    word: str
    start: float
    end: float
    confidence: float


# Transcript segment
class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    confidence: float
    words: Optional[List[WordTimestamp]] = None


# Video schemas
class VideoCreate(BaseModel):
    filename: str
    user_id: Optional[str] = None


class VideoResponse(BaseModel):
    id: str
    filename: str
    user_id: Optional[str]
    original_path: str
    duration_seconds: Optional[float]
    resolution: Optional[str]
    file_size_bytes: Optional[int]
    status: VideoStatus
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime


class VideoStatusResponse(BaseModel):
    id: str
    status: VideoStatus
    error_message: Optional[str]


# Transcript schemas
class TranscriptResponse(BaseModel):
    id: str
    video_id: str
    full_text: str
    segments: List[TranscriptSegment]
    language: str
    language_probability: Optional[float]
    model_used: str
    processing_time_seconds: float
    created_at: datetime


# Clip suggestion schemas
class ClipSuggestionResponse(BaseModel):
    id: str
    video_id: str
    start_time: float
    end_time: float
    transcript_excerpt: str
    platform: Platform
    hook_reason: str
    confidence_score: float
    status: ClipStatus
    created_at: datetime


class ClipSuggestionUpdate(BaseModel):
    status: Optional[ClipStatus] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


# Rendered clip schemas
class RenderedClipResponse(BaseModel):
    id: str
    suggestion_id: str
    video_id: str
    platform: Platform
    output_path: Optional[str]
    storage_url: Optional[str]
    duration_seconds: float
    file_size_bytes: Optional[int]
    render_time_seconds: Optional[float]
    created_at: datetime


# Export schemas
class ExportRequest(BaseModel):
    """Request to export a clip to one or more platforms."""
    platforms: List[Platform] = Field(..., min_length=1)
    preset: SilencePreset = SilencePreset.LINKEDIN
    include_captions: bool = True


class ExportResponse(BaseModel):
    """Response for a single export job."""
    id: str
    clip_id: str
    video_id: str
    platform: str
    preset: str
    status: str
    progress: float
    include_captions: bool
    output_path: Optional[str] = None
    output_url: Optional[str] = None
    original_duration: Optional[float] = None
    edited_duration: Optional[float] = None
    time_saved: Optional[float] = None
    file_size_bytes: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ExportCreateResponse(BaseModel):
    """Response when creating export jobs."""
    message: str
    exports: List[ExportResponse]


class ExportListResponse(BaseModel):
    """Response for listing exports."""
    exports: List[ExportResponse]
    total: int


# Health check
class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    service: str = "video-clipper"
