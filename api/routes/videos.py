"""
Video management endpoints.
"""

import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from api.database import db
from api.models.schemas import VideoResponse, VideoStatusResponse

router = APIRouter()


class ProcessingResponse(BaseModel):
    id: str
    status: str
    message: str


@router.get("/videos", response_model=List[VideoResponse])
async def list_videos(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
):
    """List videos with optional filters."""
    videos = db.list_videos(user_id=user_id, status=status, limit=limit)
    return videos


@router.get("/videos/{video_id}", response_model=VideoResponse)
async def get_video(video_id: str):
    """Get video details by ID."""
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.get("/videos/{video_id}/status", response_model=VideoStatusResponse)
async def get_video_status(video_id: str):
    """Get video processing status."""
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return VideoStatusResponse(
        id=video["id"],
        status=video["status"],
        error_message=video.get("error_message"),
    )


def process_video_pipeline(video_id: str):
    """
    Background task to process video through the full pipeline.

    Stages:
    1. Extract audio
    2. Transcribe with faster-whisper
    3. Generate clip suggestions with Sonnet 4.5 (AB Civil context)
    """
    from src.video.audio_extractor import extract_audio, get_video_info
    from src.video.transcriber import transcribe_audio
    from src.video.clip_composer_v2 import compose_clips

    try:
        # Get video record
        video = db.get_video(video_id)
        if not video:
            return

        video_path = video["original_path"]

        # Stage 1: Get video info and extract audio
        db.update_video_status(video_id, "extracting_audio")

        video_info = get_video_info(video_path)
        db.update_video(
            video_id,
            duration_seconds=video_info["duration"],
            resolution=video_info.get("resolution"),
        )

        audio_path = extract_audio(video_path)

        # Stage 2: Transcribe
        db.update_video_status(video_id, "transcribing")

        # Use Deepgram by default for best filler word detection (um, uh, like, you know)
        # Falls back to OpenAI API or local model if Deepgram key not available
        transcript = transcribe_audio(audio_path)

        # Save transcript to database
        db.create_transcript(
            video_id=video_id,
            full_text=transcript["text"],
            segments=transcript["segments"],
            language=transcript["language"],
            language_probability=transcript.get("language_probability"),
            model_used=transcript["model"],
            processing_time_seconds=transcript["processing_time"],
        )

        # Stage 3: Generate clip suggestions with Sonnet 4.5
        db.update_video_status(video_id, "analyzing")

        # Use the v2 composer with AB Civil context
        clips = compose_clips(
            segments=transcript["segments"],
            duration=video_info["duration"],
            platform="linkedin",  # Default to LinkedIn, generates for multiple platforms
            num_clips=5,
            audio_path=audio_path,
        )

        # Save suggestions to database
        for clip in clips:
            segments_list = clip.get("segments", [])
            if not segments_list:
                continue

            start_time = segments_list[0]["start_time"]
            end_time = segments_list[-1]["end_time"]

            db.create_clip_suggestion(
                video_id=video_id,
                start_time=start_time,
                end_time=end_time,
                transcript_excerpt=clip.get("title", ""),
                platform=clip.get("platform", "linkedin"),
                hook_reason=clip.get("hook", ""),
                confidence_score=clip.get("confidence", 0.8),
                is_composed=len(segments_list) > 1,
                composition_segments=segments_list if len(segments_list) > 1 else None,
            )

        # Mark as ready
        db.update_video_status(video_id, "ready")

        # Keep the audio file for preview - store the path
        # Move to a persistent location
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "audio")
        os.makedirs(data_dir, exist_ok=True)

        persistent_audio_path = os.path.join(data_dir, f"{video_id}.wav")
        if audio_path != persistent_audio_path:
            import shutil
            shutil.move(audio_path, persistent_audio_path)

        # Update video record with audio path
        db.update_video(video_id, audio_path=persistent_audio_path)

    except Exception as e:
        db.update_video_status(video_id, "error", error_message=str(e))
        raise


@router.post("/videos/{video_id}/retranscribe")
async def retranscribe_video(video_id: str):
    """
    Re-transcribe a video using Deepgram.

    Deepgram provides the best filler word detection (um, uh, like, you know).
    """
    from src.video.transcriber import transcribe_audio

    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Get audio path
    audio_path = video.get("audio_path")
    if not audio_path:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "audio")
        audio_path = os.path.join(data_dir, f"{video_id}.wav")

    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(
            status_code=404,
            detail="Audio file not found. Run /extract-audio first.",
        )

    try:
        transcript = transcribe_audio(audio_path)

        # Delete old transcript and create new one
        # (Supabase doesn't have update, so we'd need to delete/insert)
        # For now, just update by video_id
        db.client.table("transcripts").delete().eq("video_id", video_id).execute()

        db.create_transcript(
            video_id=video_id,
            full_text=transcript["text"],
            segments=transcript["segments"],
            language=transcript["language"],
            language_probability=transcript.get("language_probability"),
            model_used=transcript["model"],
            processing_time_seconds=transcript["processing_time"],
        )

        # Count fillers in new transcript
        filler_words = ["um", "uh", "er", "ah", "eh", "like", "you know"]
        filler_count = 0
        for seg in transcript["segments"]:
            text_lower = seg.get("text", "").lower()
            for filler in filler_words:
                filler_count += text_lower.count(filler)

        return {
            "id": video_id,
            "model_used": transcript["model"],
            "processing_time": transcript["processing_time"],
            "segments_count": len(transcript["segments"]),
            "fillers_detected": filler_count,
            "message": f"Re-transcribed with Deepgram. Found {filler_count} filler words.",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


@router.post("/videos/{video_id}/extract-audio")
async def extract_audio_from_video(video_id: str):
    """
    Extract/re-extract audio from video file.

    Useful for:
    - Videos processed before audio storage was added
    - Re-generating audio if the file was deleted
    """
    from src.video.audio_extractor import extract_audio

    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    video_path = video.get("original_path")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(
            status_code=404,
            detail="Original video file not found. Video may need to be re-uploaded.",
        )

    # Extract audio to persistent location
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "audio")
    os.makedirs(data_dir, exist_ok=True)

    audio_path = os.path.join(data_dir, f"{video_id}.wav")

    try:
        extract_audio(video_path, audio_path)

        # Update database with audio path
        db.update_video(video_id, audio_path=audio_path)

        return {
            "id": video_id,
            "audio_path": audio_path,
            "message": "Audio extracted successfully",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract audio: {str(e)}")


@router.get("/videos/{video_id}/audio")
async def get_video_audio(video_id: str):
    """
    Get the extracted audio file for a video.

    Returns the WAV audio file for playback/preview.
    """
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Check for audio path in database
    audio_path = video.get("audio_path")

    # Fallback to default location if not in DB
    if not audio_path:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "audio")
        audio_path = os.path.join(data_dir, f"{video_id}.wav")

    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(
            status_code=404,
            detail="Audio file not found. Video may not have been processed yet.",
        )

    return FileResponse(
        audio_path,
        media_type="audio/wav",
        filename=f"{video_id}.wav",
    )


@router.get("/videos/{video_id}/clip-preview")
async def get_clip_preview(
    video_id: str,
    start: float,
    end: float,
    edit: bool = True,
    preset: str = "linkedin",
):
    """
    Get a preview of a clip from the video's audio.

    Args:
        video_id: Video ID
        start: Start time in seconds
        end: End time in seconds
        edit: Whether to apply smart editing (remove pauses, stumbles, fillers)
        preset: Editing preset (youtube_shorts, tiktok, linkedin, podcast)

    Returns:
        WAV audio file of the clip
    """
    import subprocess

    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Get audio path
    audio_path = video.get("audio_path")
    if not audio_path:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "audio")
        audio_path = os.path.join(data_dir, f"{video_id}.wav")

    if not audio_path or not os.path.exists(audio_path):
        raise HTTPException(
            status_code=404,
            detail="Audio file not found. Video may not have been processed yet.",
        )

    # Validate time range
    if start < 0 or end <= start:
        raise HTTPException(status_code=400, detail="Invalid time range")

    # Create temp output file with unique name based on all parameters
    temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "temp")
    os.makedirs(temp_dir, exist_ok=True)
    edit_str = preset if edit else "raw"
    output_path = os.path.join(temp_dir, f"clip_{video_id}_{start:.1f}_{end:.1f}_{edit_str}.wav")

    try:
        if edit:
            # Get transcript for smart editing
            transcript = db.get_transcript(video_id)
            if not transcript or not transcript.get("segments"):
                raise HTTPException(
                    status_code=400,
                    detail="Transcript not available for smart editing. Try with edit=false.",
                )

            # Use smart editor
            from src.video.audio_assembler import create_edited_clip

            result = create_edited_clip(
                audio_path,
                transcript["segments"],
                start,
                end,
                preset,
                output_path,
            )
            # Result contains time_savings info but we just return the file
        else:
            # Just extract the clip without editing
            cmd = [
                "ffmpeg", "-y",
                "-i", audio_path,
                "-ss", str(start),
                "-t", str(end - start),
                "-c", "copy",
                output_path
            ]
            subprocess.run(cmd, capture_output=True, check=True)

        return FileResponse(
            output_path,
            media_type="audio/wav",
            filename=f"clip_{start:.1f}_{end:.1f}.wav",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate clip preview: {str(e)}")


@router.post("/videos/{video_id}/process", response_model=ProcessingResponse)
async def process_video(video_id: str, background_tasks: BackgroundTasks):
    """
    Trigger video processing pipeline.

    Runs in background:
    1. Extract audio from video
    2. Transcribe with faster-whisper
    3. Detect silence periods
    4. Generate clip suggestions with AI

    Poll GET /api/videos/{id}/status to check progress.
    """
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Check if already processing or processed
    if video["status"] in ["extracting_audio", "transcribing", "analyzing"]:
        raise HTTPException(
            status_code=400,
            detail=f"Video is already being processed (status: {video['status']})",
        )

    if video["status"] == "ready":
        raise HTTPException(
            status_code=400,
            detail="Video has already been processed. Delete and re-upload to reprocess.",
        )

    # Start background processing
    background_tasks.add_task(process_video_pipeline, video_id)

    return ProcessingResponse(
        id=video_id,
        status="processing",
        message="Video processing started. Poll GET /api/videos/{id}/status for updates.",
    )


@router.delete("/videos/{video_id}")
async def delete_video(video_id: str):
    """
    Delete a video and all associated data.

    Removes:
    - Video record from database
    - Transcript
    - Clip suggestions
    - Audio file
    - Original video file
    """
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Delete associated files
    audio_path = video.get("audio_path")
    if audio_path and os.path.exists(audio_path):
        os.remove(audio_path)

    original_path = video.get("original_path")
    if original_path and os.path.exists(original_path):
        os.remove(original_path)

    # Delete from database (cascades to transcripts, clip_suggestions)
    db.delete_video(video_id)

    return {"id": video_id, "message": "Video deleted successfully"}


@router.post("/videos/{video_id}/compose-clips")
async def compose_clips_with_ai(
    video_id: str,
    platform: str = "linkedin",
    num_clips: int = 3,
):
    """
    Use AI (Sonnet) to compose intelligent clips from the transcript.

    This uses the v2 composer with AB Civil context:
    - Fetches high-performing LinkedIn posts as examples
    - Understands AB Civil's voice, topics, and what resonates
    - Makes smarter clip selection decisions
    - Only returns clips it's confident about

    Args:
        video_id: Video ID
        platform: Target platform (tiktok, linkedin, youtube_shorts)
        num_clips: Number of clips to generate (1-5)
    """
    from src.video.clip_composer_v2 import compose_clips

    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Get transcript
    transcript = db.get_transcript(video_id)
    if not transcript or not transcript.get("segments"):
        raise HTTPException(
            status_code=400,
            detail="No transcript available. Process the video first.",
        )

    # Validate inputs
    if platform not in ["tiktok", "linkedin", "youtube_shorts"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid platform. Choose: tiktok, linkedin, youtube_shorts",
        )

    if num_clips < 1 or num_clips > 5:
        raise HTTPException(
            status_code=400,
            detail="num_clips must be between 1 and 5",
        )

    # Get audio path for waveform analysis
    audio_path = video.get("audio_path")
    if not audio_path:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "audio")
        audio_path = os.path.join(data_dir, f"{video_id}.wav")

    # Compose clips with AI (includes waveform snapping if audio available)
    clips = compose_clips(
        segments=transcript["segments"],
        duration=video.get("duration_seconds", 0),
        platform=platform,
        num_clips=num_clips,
        audio_path=audio_path if os.path.exists(audio_path) else None,
    )

    # Save to database as clip suggestions with is_composed flag
    saved_clips = []
    for clip in clips:
        # Calculate total duration from segments
        total_duration = sum(
            seg["end_time"] - seg["start_time"]
            for seg in clip.get("segments", [])
        )

        # Use first segment start and last segment end for the clip range
        segments = clip.get("segments", [])
        if segments:
            start_time = segments[0]["start_time"]
            end_time = segments[-1]["end_time"]
        else:
            continue

        saved = db.create_clip_suggestion(
            video_id=video_id,
            start_time=start_time,
            end_time=end_time,
            transcript_excerpt=clip.get("title", ""),
            platform=platform,
            hook_reason=clip.get("hook", ""),
            confidence_score=0.9,  # AI-composed clips get high confidence
            is_composed=True,
            composition_segments=segments,
        )
        saved_clips.append(saved)

    return {
        "video_id": video_id,
        "platform": platform,
        "clips_generated": len(saved_clips),
        "clips": clips,
    }
