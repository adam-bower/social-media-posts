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


# Clip adjustment schemas
class SilenceOverride(BaseModel):
    """Override for a specific silence segment's trim amount."""
    start: float  # Silence start time (relative to clip start)
    end: float  # Silence end time (relative to clip start)
    keep_ms: int  # How many milliseconds to keep (instead of preset default)


class ClipBoundaryAdjustment(BaseModel):
    """Adjustment to clip start/end boundaries."""
    start_offset: float = 0.0  # Seconds to add/subtract from start
    end_offset: float = 0.0  # Seconds to add/subtract from end


class ClipAdjustments(BaseModel):
    """Adjustments to apply when exporting a clip."""
    boundaries: Optional[ClipBoundaryAdjustment] = None
    silence_overrides: Optional[List[SilenceOverride]] = None
    max_kept_silence_ms: Optional[int] = None  # Override preset default


class PlatformAdjustments(BaseModel):
    """
    Adjustments for export with base + per-platform overrides.

    The base adjustments apply to all platforms.
    Per-platform overrides can customize specific platforms.
    """
    base: Optional[ClipAdjustments] = None
    # Platform-specific overrides (e.g., {"linkedin": {...}, "tiktok": {...}})
    overrides: Optional[dict] = None  # Dict[str, ClipAdjustments]


# Export schemas
class ExportRequest(BaseModel):
    """Request to export a clip to one or more platforms."""
    platforms: List[Platform] = Field(..., min_length=1)
    preset: SilencePreset = SilencePreset.LINKEDIN
    include_captions: bool = True
    adjustments: Optional[PlatformAdjustments] = None


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


# VAD Analysis schemas
class SpeechSegment(BaseModel):
    """A detected speech segment."""
    start: float
    end: float


class SilenceSegment(BaseModel):
    """A detected silence segment."""
    start: float
    end: float


class EditDecision(BaseModel):
    """Decision about what to do with a segment."""
    start: float
    end: float
    action: str  # "keep", "remove", "trim"
    reason: str
    original_duration: float
    new_duration: float


class PresetConfigResponse(BaseModel):
    """Configuration for a platform preset."""
    vad_threshold: float
    min_silence_ms: int
    max_kept_silence_ms: int
    speech_padding_ms: int
    crossfade_ms: int


class VADAnalysisResponse(BaseModel):
    """Voice Activity Detection analysis for waveform visualization."""
    speech_segments: List[SpeechSegment]
    silence_segments: List[SilenceSegment]
    duration: float
    preset: str
    config: PresetConfigResponse


class ClipPreviewMetadata(BaseModel):
    """Metadata about a clip preview with editing applied."""
    original_duration: float
    edited_duration: float
    time_saved: float
    percent_reduction: float
    speech_segments: List[SpeechSegment]
    silence_segments: List[SilenceSegment]
    edit_decisions: List[EditDecision]
    preset: str
    config: PresetConfigResponse


# Health check
class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    service: str = "video-clipper"
