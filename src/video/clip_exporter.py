"""
Unified clip export pipeline for social media videos.

Orchestrates the complete export process:
1. Extract audio from clip range
2. Run waveform silence removal → get EditDecisions
3. Apply same edits to audio AND video
4. Detect subject position with Gemini Flash 2.5
5. Calculate crop centered on subject
6. Generate ASS captions if transcript provided
7. Render final video with FFmpeg

This ensures audio and video edits are perfectly synced by using
the same EditDecisions for both.

Usage:
    from src.video.clip_exporter import export_clip, ExportConfig

    result = export_clip(
        video_path="data/video/C0044.MP4",
        clip_start=90.0,
        clip_end=123.0,
        output_path="output/clip.mp4",
        format_type="tiktok",
        preset="linkedin",  # Silence removal preset
    )
"""

import os
import tempfile
import subprocess
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from pathlib import Path

from src.video.export_formats import ExportFormat, FormatSpec, get_format
from src.video.waveform_silence_remover import (
    process_clip_waveform_only,
    PlatformPreset,
    PRESETS,
)
from src.video.edit_sync import (
    VideoEditPlan,
    VideoEditSegment,
    audio_edits_to_video_segments,
)
from src.video.frame_sampler import sample_frames, SamplingMode, get_video_info
from src.video.vision_detector import GeminiVisionDetector, SubjectPosition
from src.video.crop_calculator import CropCalculator, CropResult, CropRegion
from src.video.caption_generator import generate_captions
from src.video.caption_styles import get_caption_style


@dataclass
class ExportConfig:
    """Configuration for clip export."""
    # Output format
    format_type: ExportFormat = ExportFormat.TIKTOK

    # Silence removal preset
    silence_preset: str = "linkedin"

    # Custom silence removal config (overrides preset)
    silence_config: Optional[Dict[str, Any]] = None

    # Captions
    include_captions: bool = True

    # Encoding settings
    codec: str = "libx264"
    preset: str = "medium"  # FFmpeg encoding preset (not silence preset)
    crf: int = 23
    bitrate_mbps: Optional[float] = None  # None = use format default
    fps: Optional[int] = None  # None = use format default

    # Subject detection
    detect_subject: bool = True
    subject_position: Optional[SubjectPosition] = None  # Override detection

    def get_format_spec(self) -> FormatSpec:
        return get_format(self.format_type)


@dataclass
class ExportResult:
    """Result of clip export."""
    success: bool
    output_path: str

    # Timing info
    original_duration: float
    edited_duration: float
    time_saved: float

    # Edit info
    segments_count: int
    silences_removed: int

    # Crop info
    crop: Optional[CropRegion] = None
    subject_position: Optional[SubjectPosition] = None

    # Errors
    error: Optional[str] = None

    # Debug info
    ffmpeg_command: Optional[str] = None
    temp_files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output_path": self.output_path,
            "original_duration": round(self.original_duration, 2),
            "edited_duration": round(self.edited_duration, 2),
            "time_saved": round(self.time_saved, 2),
            "percent_reduction": round(
                (self.time_saved / self.original_duration * 100)
                if self.original_duration > 0 else 0, 1
            ),
            "segments_count": self.segments_count,
            "silences_removed": self.silences_removed,
            "error": self.error,
        }


def extract_audio_clip(
    video_path: str,
    output_path: str,
    clip_start: float,
    clip_end: float,
) -> str:
    """
    Extract audio from a video clip range.

    Args:
        video_path: Path to source video
        output_path: Path for output WAV
        clip_start: Start time in seconds
        clip_end: End time in seconds

    Returns:
        Path to extracted audio file
    """
    duration = clip_end - clip_start

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(clip_start),
        "-i", video_path,
        "-t", str(duration),
        "-vn",  # No video
        "-acodec", "pcm_s16le",
        "-ar", "16000",  # 16kHz for Silero VAD
        "-ac", "1",  # Mono
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Audio extraction failed: {result.stderr}")

    return output_path


def get_edit_decisions(
    audio_path: str,
    preset: str = "linkedin",
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Get edit decisions from waveform silence remover.

    Args:
        audio_path: Path to audio file
        preset: Silence removal preset
        config: Optional custom config overrides

    Returns:
        Dict with decisions and statistics
    """
    return process_clip_waveform_only(
        audio_path=audio_path,
        preset=preset,
        config=config,
    )


def create_video_edit_plan(
    silence_result: Dict[str, Any],
    video_fps: float,
    clip_start: float,
    clip_end: float,
) -> VideoEditPlan:
    """
    Create VideoEditPlan from silence removal result.

    The edit decisions are already relative to the clip (0 = clip start).
    We use these directly for video trimming.

    Args:
        silence_result: Result from process_clip_waveform_only()
        video_fps: Video frame rate
        clip_start: Original clip start in source video
        clip_end: Original clip end in source video

    Returns:
        VideoEditPlan with segments for video rendering
    """
    decisions = silence_result.get("decisions", [])
    clip_duration = clip_end - clip_start

    # CRITICAL: Disable frame snapping to match audio exactly
    # When we provide pre-edited audio, video must use exact same times
    # Frame snapping expands segments slightly, causing desync
    return audio_edits_to_video_segments(
        edit_decisions=decisions,
        video_fps=video_fps,
        video_duration=clip_duration,
        snap_to_frames=False,  # Use exact times to match audio
    )


def generate_edited_audio(
    audio_path: str,
    silence_result: Dict[str, Any],
    output_path: str,
) -> str:
    """
    Generate edited audio from silence removal result.

    Uses the decisions to extract and concatenate kept segments.

    Args:
        audio_path: Path to source audio
        silence_result: Result from silence removal
        output_path: Path for output audio

    Returns:
        Path to edited audio file
    """
    from src.video.audio_assembler import assemble_audio

    decisions = silence_result.get("decisions", [])

    # Extract segments to keep
    segments = []
    for d in decisions:
        if d.get("action") in ("keep", "trim"):
            segments.append({
                "start": d.get("start", 0),
                "end": d.get("end", 0),
            })

    if not segments:
        raise ValueError("No segments to keep after silence removal")

    return assemble_audio(audio_path, segments, output_path)


def detect_subject_in_clip(
    video_path: str,
    clip_start: float,
    clip_end: float,
) -> SubjectPosition:
    """
    Detect subject position in a video clip.

    Uses sparse sampling (5 frames) and Gemini Flash 2.5.

    Args:
        video_path: Path to video file
        clip_start: Clip start time
        clip_end: Clip end time

    Returns:
        SubjectPosition with averaged position
    """
    # Sample frames from clip range
    sampling_result = sample_frames(
        video_path,
        mode=SamplingMode.SPARSE,
        clip_start=clip_start,
        clip_end=clip_end,
        max_dimension=720,
    )

    if not sampling_result.frames:
        # Return centered default
        return SubjectPosition(
            x=0.5,
            y=0.45,
            head_y=0.30,
            confidence=0.0,
            description="No frames sampled",
        )

    # Analyze with vision detector
    with GeminiVisionDetector() as detector:
        movement = detector.analyze_video_frames(sampling_result)

    if not movement.positions:
        return SubjectPosition(
            x=0.5,
            y=0.45,
            head_y=0.30,
            confidence=0.0,
            description="No subject detected",
        )

    # Return average position
    avg_x, avg_y = movement.average_position

    # Estimate head_y from average head positions
    head_positions = [p.head_y for p in movement.positions if p.confidence > 0.3]
    avg_head_y = sum(head_positions) / len(head_positions) if head_positions else 0.30

    return SubjectPosition(
        x=avg_x,
        y=avg_y,
        head_y=avg_head_y,
        confidence=movement.confidence,
        description=f"Averaged from {len(movement.positions)} frames",
    )


def calculate_crop_for_export(
    video_info: Dict[str, Any],
    format_type: ExportFormat,
    subject_position: SubjectPosition,
) -> CropResult:
    """
    Calculate crop region for export format.

    Args:
        video_info: Video metadata (width, height)
        format_type: Target export format
        subject_position: Detected subject position

    Returns:
        CropResult with crop region
    """
    calculator = CropCalculator()
    return calculator.calculate_crop(
        source_width=video_info["width"],
        source_height=video_info["height"],
        target_format=format_type,
        subject_position=subject_position,
    )


def generate_caption_file(
    transcript: Dict[str, Any],
    clip_start: float,
    clip_end: float,
    edit_plan: VideoEditPlan,
    format_type: ExportFormat,
    output_path: str,
) -> str:
    """
    Generate ASS caption file adjusted for clip and edits.

    Args:
        transcript: Full transcript with word-level timestamps
        clip_start: Clip start time in source video
        clip_end: Clip end time in source video
        edit_plan: VideoEditPlan with segments
        format_type: Export format for styling
        output_path: Path for output ASS file

    Returns:
        Path to ASS file
    """
    # Extract words within clip range
    all_words = []
    for segment in transcript.get("segments", []):
        for word in segment.get("words", []):
            word_start = word.get("start", 0)
            word_end = word.get("end", word_start + 0.1)

            # Filter to clip range
            if word_end < clip_start or word_start > clip_end:
                continue

            all_words.append(word)

    # Adjust timestamps relative to clip start
    adjusted_words = []
    for word in all_words:
        adjusted_words.append({
            "word": word.get("word", word.get("text", "")),
            "start": word.get("start", 0) - clip_start,
            "end": word.get("end", 0) - clip_start,
        })

    # Now adjust for edit plan (map original times to edited times)
    # This is the key sync step - we need to map each word's time
    # through the edit segments to get its position in the edited video
    edited_words = []
    current_output_time = 0.0

    for segment in edit_plan.segments:
        # Find words that fall within this segment (in original time)
        for word in adjusted_words:
            word_start = word["start"]
            word_end = word["end"]

            # Check if word overlaps with this segment
            if word_end <= segment.start or word_start >= segment.end:
                continue

            # Calculate position in output
            # Word's position relative to segment start
            word_offset = max(0, word_start - segment.start)

            edited_words.append({
                "word": word["word"],
                "start": current_output_time + word_offset,
                "end": current_output_time + min(word_end - segment.start, segment.duration),
            })

        current_output_time += segment.duration

    # Generate ASS content
    style = get_caption_style(format_type)
    format_spec = get_format(format_type)

    ass_content = generate_captions(
        words=edited_words,
        format_type=format_type,
        style=style,
        format_spec=format_spec,
        title="Clip Captions",
    )

    # Save to file
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    return output_path


def build_ffmpeg_command(
    video_path: str,
    audio_path: str,
    output_path: str,
    clip_start: float,
    clip_end: float,
    edit_plan: VideoEditPlan,
    crop: CropRegion,
    format_spec: FormatSpec,
    config: ExportConfig,
    caption_path: Optional[str] = None,
) -> List[str]:
    """
    Build FFmpeg command for final render.

    Args:
        video_path: Path to source video
        audio_path: Path to edited audio
        output_path: Path for output video
        clip_start: Clip start time
        clip_end: Clip end time
        edit_plan: VideoEditPlan with segments
        crop: CropRegion for cropping
        format_spec: Target format spec
        config: Export configuration
        caption_path: Optional path to ASS captions

    Returns:
        FFmpeg command as list of strings
    """
    # Build video filter chain
    filters = []

    # Step 1: Apply edit segments (trim + concat)
    if edit_plan.segments:
        if len(edit_plan.segments) == 1:
            # Single segment - simple trim
            # Timestamps are relative to clip, but we need to seek to clip_start first
            seg = edit_plan.segments[0]
            actual_start = clip_start + seg.start
            actual_end = clip_start + seg.end
            filters.append(
                f"trim={actual_start:.6f}:{actual_end:.6f},setpts=PTS-STARTPTS"
            )
        else:
            # Multiple segments - split, trim, concat
            # For this we need filter_complex
            pass  # Handled below

    # For multiple segments, we need a different approach
    if len(edit_plan.segments) > 1:
        return _build_multi_segment_command(
            video_path, audio_path, output_path,
            clip_start, edit_plan, crop, format_spec, config, caption_path
        )

    # Step 2: Scale and crop
    filters.append(f"scale={crop.scaled_width}:{crop.scaled_height}")
    filters.append(f"crop={crop.width}:{crop.height}:{crop.x}:{crop.y}")

    # Step 3: Subtitles (if provided)
    if caption_path:
        escaped_path = caption_path.replace("\\", "\\\\").replace(":", "\\:")
        filters.append(f"subtitles='{escaped_path}'")

    filter_str = ",".join(filters)

    # Build command
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-vf", filter_str,
        "-map", "0:v",
        "-map", "1:a",
    ]

    # Encoding settings
    bitrate = config.bitrate_mbps or format_spec.bitrate_mbps
    fps = config.fps or format_spec.fps

    cmd.extend([
        "-c:v", config.codec,
        "-preset", config.preset,
        "-crf", str(config.crf),
        "-b:v", f"{bitrate}M",
        "-maxrate", f"{bitrate * 1.5}M",
        "-bufsize", f"{bitrate * 2}M",
        "-r", str(fps),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", f"{format_spec.audio_bitrate_kbps}k",
        output_path,
    ])

    return cmd


def _build_multi_segment_command(
    video_path: str,
    audio_path: str,
    output_path: str,
    clip_start: float,
    edit_plan: VideoEditPlan,
    crop: CropRegion,
    format_spec: FormatSpec,
    config: ExportConfig,
    caption_path: Optional[str] = None,
) -> List[str]:
    """
    Build FFmpeg command for multi-segment editing.

    Uses filter_complex to split, trim, and concat video segments.
    """
    # Build filter_complex for video
    filter_parts = []
    segment_labels = []

    # Split input into N streams
    n = len(edit_plan.segments)
    split_outputs = "".join(f"[s{i}]" for i in range(n))
    filter_parts.append(f"[0:v]split={n}{split_outputs}")

    # Trim each segment (timestamps relative to clip_start)
    for i, seg in enumerate(edit_plan.segments):
        actual_start = clip_start + seg.start
        actual_end = clip_start + seg.end
        label = f"t{i}"
        filter_parts.append(
            f"[s{i}]trim={actual_start:.6f}:{actual_end:.6f},setpts=PTS-STARTPTS[{label}]"
        )
        segment_labels.append(f"[{label}]")

    # Concat all segments
    concat_inputs = "".join(segment_labels)
    filter_parts.append(f"{concat_inputs}concat=n={n}:v=1:a=0[concatv]")

    # Scale and crop
    filter_parts.append(
        f"[concatv]scale={crop.scaled_width}:{crop.scaled_height}[scaledv]"
    )
    filter_parts.append(
        f"[scaledv]crop={crop.width}:{crop.height}:{crop.x}:{crop.y}[croppedv]"
    )

    # Subtitles (if provided)
    if caption_path:
        escaped_path = caption_path.replace("\\", "\\\\").replace(":", "\\:")
        filter_parts.append(f"[croppedv]subtitles='{escaped_path}'[outv]")
        final_video = "[outv]"
    else:
        final_video = "[croppedv]"

    filter_complex = ";".join(filter_parts)

    # Build command
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", final_video,
        "-map", "1:a",
    ]

    # Encoding settings
    bitrate = config.bitrate_mbps or format_spec.bitrate_mbps
    fps = config.fps or format_spec.fps

    cmd.extend([
        "-c:v", config.codec,
        "-preset", config.preset,
        "-crf", str(config.crf),
        "-b:v", f"{bitrate}M",
        "-maxrate", f"{bitrate * 1.5}M",
        "-bufsize", f"{bitrate * 2}M",
        "-r", str(fps),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", f"{format_spec.audio_bitrate_kbps}k",
        output_path,
    ])

    return cmd


def export_clip(
    video_path: str,
    clip_start: float,
    clip_end: float,
    output_path: str,
    format_type: str = "tiktok",
    preset: str = "linkedin",
    transcript: Optional[Dict[str, Any]] = None,
    config: Optional[ExportConfig] = None,
    keep_temp_files: bool = False,
) -> ExportResult:
    """
    Export a video clip with silence removal, cropping, and captions.

    This is the main entry point for the unified clip export pipeline.

    Args:
        video_path: Path to source video
        clip_start: Start time in seconds
        clip_end: End time in seconds
        output_path: Path for output video
        format_type: Export format ("tiktok", "youtube_shorts", "linkedin", etc.)
        preset: Silence removal preset ("linkedin", "tiktok", "youtube_shorts", "podcast")
        transcript: Optional transcript with word-level timestamps for captions
        config: Optional ExportConfig for advanced settings
        keep_temp_files: Whether to keep temporary files for debugging

    Returns:
        ExportResult with status and details
    """
    # Validate inputs
    if not os.path.exists(video_path):
        return ExportResult(
            success=False,
            output_path=output_path,
            original_duration=0,
            edited_duration=0,
            time_saved=0,
            segments_count=0,
            silences_removed=0,
            error=f"Video file not found: {video_path}",
        )

    if clip_end <= clip_start:
        return ExportResult(
            success=False,
            output_path=output_path,
            original_duration=0,
            edited_duration=0,
            time_saved=0,
            segments_count=0,
            silences_removed=0,
            error=f"Invalid clip range: {clip_start} to {clip_end}",
        )

    # Set up configuration
    if config is None:
        config = ExportConfig()

    # Parse format type
    try:
        export_format = ExportFormat(format_type.lower())
        config.format_type = export_format
    except ValueError:
        available = [f.value for f in ExportFormat]
        return ExportResult(
            success=False,
            output_path=output_path,
            original_duration=0,
            edited_duration=0,
            time_saved=0,
            segments_count=0,
            silences_removed=0,
            error=f"Unknown format '{format_type}'. Available: {available}",
        )

    config.silence_preset = preset
    format_spec = config.get_format_spec()

    # Get video info
    try:
        video_info = get_video_info(video_path)
    except Exception as e:
        return ExportResult(
            success=False,
            output_path=output_path,
            original_duration=0,
            edited_duration=0,
            time_saved=0,
            segments_count=0,
            silences_removed=0,
            error=f"Failed to get video info: {e}",
        )

    original_duration = clip_end - clip_start
    temp_files = []

    try:
        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix="clip_export_")

        # Step 1: Extract audio from clip range
        audio_clip_path = os.path.join(temp_dir, "clip_audio.wav")
        extract_audio_clip(video_path, audio_clip_path, clip_start, clip_end)
        temp_files.append(audio_clip_path)

        # Step 2: Run silence removal to get edit decisions
        silence_result = get_edit_decisions(
            audio_path=audio_clip_path,
            preset=preset,
            config=config.silence_config,
        )

        # Step 3: Create video edit plan from decisions
        edit_plan = create_video_edit_plan(
            silence_result=silence_result,
            video_fps=video_info["fps"],
            clip_start=clip_start,
            clip_end=clip_end,
        )

        # Step 4: Generate edited audio
        edited_audio_path = os.path.join(temp_dir, "edited_audio.wav")
        generate_edited_audio(audio_clip_path, silence_result, edited_audio_path)
        temp_files.append(edited_audio_path)

        # Step 5: Detect subject position (or use provided)
        if config.subject_position:
            subject_position = config.subject_position
        elif config.detect_subject:
            try:
                subject_position = detect_subject_in_clip(
                    video_path, clip_start, clip_end
                )
            except Exception as e:
                # Fall back to centered position
                print(f"Subject detection failed: {e}, using centered position")
                subject_position = SubjectPosition(
                    x=0.5,
                    y=0.45,
                    head_y=0.30,
                    confidence=0.5,
                    description="Default centered position",
                )
        else:
            subject_position = SubjectPosition(
                x=0.5,
                y=0.45,
                head_y=0.30,
                confidence=0.5,
                description="Default centered position",
            )

        # Step 6: Calculate crop
        crop_result = calculate_crop_for_export(
            video_info=video_info,
            format_type=config.format_type,
            subject_position=subject_position,
        )

        # Step 7: Generate captions if transcript provided
        caption_path = None
        if config.include_captions and transcript:
            caption_path = os.path.join(temp_dir, "captions.ass")
            generate_caption_file(
                transcript=transcript,
                clip_start=clip_start,
                clip_end=clip_end,
                edit_plan=edit_plan,
                format_type=config.format_type,
                output_path=caption_path,
            )
            temp_files.append(caption_path)

        # Step 8: Build and run FFmpeg command
        cmd = build_ffmpeg_command(
            video_path=video_path,
            audio_path=edited_audio_path,
            output_path=output_path,
            clip_start=clip_start,
            clip_end=clip_end,
            edit_plan=edit_plan,
            crop=crop_result.crop,
            format_spec=format_spec,
            config=config,
            caption_path=caption_path,
        )

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        # Run FFmpeg
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return ExportResult(
                success=False,
                output_path=output_path,
                original_duration=original_duration,
                edited_duration=edit_plan.edited_duration,
                time_saved=edit_plan.time_saved,
                segments_count=edit_plan.segment_count,
                silences_removed=silence_result.get("silences_detected", 0),
                crop=crop_result.crop,
                subject_position=subject_position,
                error=f"FFmpeg failed: {result.stderr[-1000:]}",
                ffmpeg_command=" ".join(cmd),
                temp_files=temp_files if keep_temp_files else [],
            )

        # Verify output exists
        if not os.path.exists(output_path):
            return ExportResult(
                success=False,
                output_path=output_path,
                original_duration=original_duration,
                edited_duration=edit_plan.edited_duration,
                time_saved=edit_plan.time_saved,
                segments_count=edit_plan.segment_count,
                silences_removed=silence_result.get("silences_detected", 0),
                error="Output file was not created",
                ffmpeg_command=" ".join(cmd),
            )

        return ExportResult(
            success=True,
            output_path=output_path,
            original_duration=original_duration,
            edited_duration=edit_plan.edited_duration,
            time_saved=edit_plan.time_saved,
            segments_count=edit_plan.segment_count,
            silences_removed=silence_result.get("silences_detected", 0),
            crop=crop_result.crop,
            subject_position=subject_position,
            ffmpeg_command=" ".join(cmd),
            temp_files=temp_files if keep_temp_files else [],
        )

    except Exception as e:
        import traceback
        return ExportResult(
            success=False,
            output_path=output_path,
            original_duration=original_duration,
            edited_duration=0,
            time_saved=0,
            segments_count=0,
            silences_removed=0,
            error=f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
            temp_files=temp_files if keep_temp_files else [],
        )

    finally:
        # Clean up temp files unless keeping them
        if not keep_temp_files:
            for f in temp_files:
                try:
                    if os.path.exists(f):
                        os.unlink(f)
                except:
                    pass
            try:
                if 'temp_dir' in dir() and os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
            except:
                pass


if __name__ == "__main__":
    import sys
    import json

    print("Unified Clip Exporter - Test Mode")
    print("=" * 60)

    # Check for test video
    test_video = "data/video/C0044.MP4"
    if not os.path.exists(test_video):
        print(f"Test video not found: {test_video}")
        sys.exit(1)

    # Test clip range (from dev docs)
    clip_start = 90.0
    clip_end = 123.0

    print(f"\nSource: {test_video}")
    print(f"Clip range: {clip_start}s - {clip_end}s")

    # Check for transcript
    transcript_path = "data/audio/C0044_full_transcript.json"
    transcript = None
    if os.path.exists(transcript_path):
        with open(transcript_path) as f:
            transcript = json.load(f)
        print(f"Transcript: {transcript_path}")
    else:
        print("No transcript found - exporting without captions")

    # Export
    output_path = "data/output/test_unified_export.mp4"
    print(f"\nExporting to: {output_path}")
    print("Format: TikTok (9:16)")
    print("Preset: LinkedIn (conservative silence removal)")

    result = export_clip(
        video_path=test_video,
        clip_start=clip_start,
        clip_end=clip_end,
        output_path=output_path,
        format_type="tiktok",
        preset="linkedin",
        transcript=transcript,
        keep_temp_files=False,
    )

    print("\n" + "=" * 60)
    if result.success:
        print("SUCCESS!")
        print(f"  Output: {result.output_path}")
        print(f"  Original: {result.original_duration:.1f}s")
        print(f"  Edited: {result.edited_duration:.1f}s")
        print(f"  Saved: {result.time_saved:.1f}s ({result.time_saved/result.original_duration*100:.1f}%)")
        print(f"  Segments: {result.segments_count}")
        print(f"  Silences removed: {result.silences_removed}")
        if result.subject_position:
            print(f"  Subject: ({result.subject_position.x:.2f}, {result.subject_position.y:.2f})")
        if result.crop:
            print(f"  Crop: {result.crop.width}x{result.crop.height} at ({result.crop.x}, {result.crop.y})")
    else:
        print("FAILED!")
        print(f"  Error: {result.error}")
        if result.ffmpeg_command:
            print(f"\n  FFmpeg command:\n  {result.ffmpeg_command}")
