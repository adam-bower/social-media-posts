"""
Export endpoints for video clip rendering.

Handles creating export jobs and processing them via background tasks.
"""

import os
import asyncio
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from api.database import db
from api.models.schemas import (
    ExportRequest,
    ExportResponse,
    ExportCreateResponse,
    ExportListResponse,
    ExportStatus,
    Platform,
)

router = APIRouter()


def export_to_response(export: dict) -> ExportResponse:
    """Convert database export record to response model."""
    return ExportResponse(
        id=export["id"],
        clip_id=export["clip_id"],
        video_id=export["video_id"],
        platform=export["platform"],
        preset=export.get("format_preset", "linkedin"),
        status=export["status"],
        progress=export.get("progress", 0),
        include_captions=export.get("include_captions", True),
        output_path=export.get("output_path"),
        output_url=export.get("output_url"),
        original_duration=export.get("original_duration"),
        edited_duration=export.get("edited_duration"),
        time_saved=export.get("time_saved"),
        file_size_bytes=export.get("file_size_bytes"),
        error_message=export.get("error_message"),
        created_at=export["created_at"],
        started_at=export.get("started_at"),
        completed_at=export.get("completed_at"),
    )


async def process_export(export_id: str):
    """
    Background task to process a single export.

    This runs the clip_exporter pipeline and updates the database.
    """
    from src.video.clip_exporter import export_clip

    export = db.get_export(export_id)
    if not export:
        return

    clip_id = export["clip_id"]
    video_id = export["video_id"]
    platform = export["platform"]
    preset = export.get("format_preset", "linkedin")
    include_captions = export.get("include_captions", True)
    adjustments = export.get("adjustments")

    # Get clip and video info
    clip = db.get_clip_suggestion(clip_id)
    video = db.get_video(video_id)

    if not clip or not video:
        db.update_export(
            export_id,
            status="failed",
            error_message="Clip or video not found",
        )
        return

    # Update status to processing
    db.update_export(
        export_id,
        status="processing",
        started_at=datetime.utcnow().isoformat(),
        progress=10,
    )

    # Get transcript for captions (if enabled)
    transcript = None
    if include_captions:
        transcript_data = db.get_transcript(video_id)
        if transcript_data:
            transcript = {
                "segments": transcript_data.get("segments", [])
            }

    # Generate output path
    output_dir = os.path.join("data", "output", video_id)
    os.makedirs(output_dir, exist_ok=True)

    output_filename = f"{clip_id}_{platform}.mp4"
    output_path = os.path.join(output_dir, output_filename)

    # Get video path
    video_path = video.get("original_path")
    if not video_path or not os.path.exists(video_path):
        db.update_export(
            export_id,
            status="failed",
            error_message=f"Video file not found: {video_path}",
        )
        return

    # Apply adjustments to clip boundaries if provided
    clip_start = clip["start_time"]
    clip_end = clip["end_time"]

    # Build silence config from adjustments
    silence_config = None

    if adjustments:
        # Apply boundary adjustments
        boundaries = adjustments.get("boundaries")
        if boundaries:
            clip_start += boundaries.get("start_offset", 0.0)
            clip_end += boundaries.get("end_offset", 0.0)

        # Build silence config
        silence_overrides = adjustments.get("silence_overrides")
        max_kept_silence_ms = adjustments.get("max_kept_silence_ms")

        if silence_overrides or max_kept_silence_ms:
            silence_config = {}
            if max_kept_silence_ms is not None:
                silence_config["max_kept_silence_ms"] = max_kept_silence_ms
            if silence_overrides:
                silence_config["silence_overrides"] = silence_overrides

    try:
        db.update_export(export_id, progress=20)

        # Build ExportConfig if we have adjustments
        export_config = None
        if silence_config:
            from src.video.clip_exporter import ExportConfig
            export_config = ExportConfig(
                silence_preset=preset,
                silence_config=silence_config,
                include_captions=include_captions,
            )

        # Run the export with adjustments
        result = export_clip(
            video_path=video_path,
            clip_start=clip_start,
            clip_end=clip_end,
            output_path=output_path,
            format_type=platform,
            preset=preset,
            transcript=transcript,
            config=export_config,
        )

        db.update_export(export_id, progress=90)

        if result.success:
            # Get file size
            file_size = None
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)

            db.update_export(
                export_id,
                status="completed",
                progress=100,
                output_path=output_path,
                original_duration=result.original_duration,
                edited_duration=result.edited_duration,
                time_saved=result.time_saved,
                file_size_bytes=file_size,
                completed_at=datetime.utcnow().isoformat(),
            )

            # Update clip status to rendered
            db.update_clip_suggestion(clip_id, status="rendered")
        else:
            db.update_export(
                export_id,
                status="failed",
                error_message=result.error or "Export failed",
                completed_at=datetime.utcnow().isoformat(),
            )

    except Exception as e:
        import traceback
        db.update_export(
            export_id,
            status="failed",
            error_message=f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()[:500]}",
            completed_at=datetime.utcnow().isoformat(),
        )


@router.post("/clips/{clip_id}/export", response_model=ExportCreateResponse)
async def create_export(
    clip_id: str,
    request: ExportRequest,
    background_tasks: BackgroundTasks,
):
    """
    Create export jobs for a clip.

    Creates one export job per platform selected.
    Jobs are processed in the background.
    """
    # Verify clip exists
    clip = db.get_clip_suggestion(clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    video_id = clip["video_id"]

    # Verify video exists
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Filter out "both" - it's not a real platform
    platforms = [p for p in request.platforms if p != Platform.BOTH]
    if not platforms:
        raise HTTPException(
            status_code=400,
            detail="At least one specific platform must be selected",
        )

    # Create export jobs for each platform
    exports = []
    for platform in platforms:
        # Merge base adjustments with platform-specific overrides
        platform_adjustments = None
        if request.adjustments:
            # Start with base adjustments
            base = request.adjustments.base
            if base:
                platform_adjustments = base.model_dump(exclude_none=True)

            # Apply platform-specific overrides if present
            overrides = request.adjustments.overrides
            if overrides and platform.value in overrides:
                platform_override = overrides[platform.value]
                if platform_adjustments:
                    # Merge override into base
                    for key, value in platform_override.items():
                        if value is not None:
                            platform_adjustments[key] = value
                else:
                    platform_adjustments = platform_override

        export = db.create_export(
            clip_id=clip_id,
            video_id=video_id,
            platform=platform.value,
            format_preset=request.preset.value,
            include_captions=request.include_captions,
            adjustments=platform_adjustments,
        )
        if export:
            exports.append(export)
            # Queue background processing
            background_tasks.add_task(process_export, export["id"])

    if not exports:
        raise HTTPException(
            status_code=500,
            detail="Failed to create export jobs",
        )

    return ExportCreateResponse(
        message=f"Created {len(exports)} export job(s)",
        exports=[export_to_response(e) for e in exports],
    )


@router.get("/exports", response_model=ExportListResponse)
async def list_exports(
    video_id: Optional[str] = None,
    clip_id: Optional[str] = None,
    status: Optional[ExportStatus] = None,
    limit: int = 50,
):
    """
    List export jobs with optional filters.

    Can filter by video_id, clip_id, or status.
    """
    exports = db.list_exports(
        video_id=video_id,
        clip_id=clip_id,
        status=status.value if status else None,
        limit=limit,
    )

    return ExportListResponse(
        exports=[export_to_response(e) for e in exports],
        total=len(exports),
    )


@router.get("/exports/{export_id}", response_model=ExportResponse)
async def get_export(export_id: str):
    """Get a single export by ID."""
    export = db.get_export(export_id)
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")

    return export_to_response(export)


@router.delete("/exports/{export_id}")
async def cancel_export(export_id: str):
    """
    Cancel a pending export.

    Only pending exports can be cancelled.
    """
    export = db.get_export(export_id)
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")

    if export["status"] != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel export with status: {export['status']}",
        )

    db.update_export(export_id, status="failed", error_message="Cancelled by user")

    return {"message": "Export cancelled", "id": export_id}


@router.get("/videos/{video_id}/exports", response_model=ExportListResponse)
async def get_video_exports(video_id: str):
    """Get all exports for a video."""
    # Verify video exists
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    exports = db.list_exports(video_id=video_id)

    return ExportListResponse(
        exports=[export_to_response(e) for e in exports],
        total=len(exports),
    )
