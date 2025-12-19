"""
Video rendering pipeline for social media export.

Orchestrates the complete video rendering process:
1. Apply edit decisions (trim/remove segments)
2. Crop to target aspect ratio
3. Scale to target resolution
4. Burn in captions with karaoke effect
5. Mux with edited audio

Usage:
    from src.video.video_renderer import render_video, RenderConfig

    config = RenderConfig(
        format_type=ExportFormat.TIKTOK,
        include_captions=True,
    )
    result = render_video(
        video_path="input.mp4",
        audio_path="edited_audio.wav",
        output_path="output.mp4",
        config=config,
    )
"""

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from src.video.export_formats import ExportFormat, FormatSpec, get_format
from src.video.crop_calculator import CropResult, CropRegion
from src.video.edit_sync import VideoEditPlan, VideoEditSegment
from src.video.caption_styles import CaptionStyle, get_caption_style
from src.video.caption_generator import generate_captions, save_captions


@dataclass
class RenderConfig:
    """Configuration for video rendering."""
    format_type: ExportFormat = ExportFormat.TIKTOK
    include_captions: bool = True
    caption_style: Optional[CaptionStyle] = None
    bitrate_mbps: Optional[float] = None  # None = use format default
    fps: Optional[int] = None  # None = use format default
    codec: str = "libx264"
    preset: str = "medium"  # FFmpeg encoding preset
    crf: int = 23  # Constant rate factor (18-28, lower = better)

    def get_format_spec(self) -> FormatSpec:
        return get_format(self.format_type)

    def get_caption_style(self) -> CaptionStyle:
        return self.caption_style or get_caption_style(self.format_type)


@dataclass
class RenderResult:
    """Result of video rendering."""
    success: bool
    output_path: str
    format_type: ExportFormat
    duration: float
    file_size_mb: float
    error: Optional[str] = None
    ffmpeg_command: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output_path": self.output_path,
            "format": self.format_type.value,
            "duration": round(self.duration, 2),
            "file_size_mb": round(self.file_size_mb, 2),
            "error": self.error,
        }


def build_ffmpeg_filter(
    crop: CropRegion,
    format_spec: FormatSpec,
    edit_plan: Optional[VideoEditPlan] = None,
    caption_path: Optional[str] = None,
) -> str:
    """
    Build FFmpeg filter_complex string.

    Applies: [trim segments →] scale → crop → [subtitles]

    Args:
        crop: CropRegion for cropping
        format_spec: Target format spec
        edit_plan: Optional edit plan for trimming
        caption_path: Optional path to ASS subtitles

    Returns:
        FFmpeg filter_complex string
    """
    filters = []
    input_label = "0:v"
    current_label = "v0"

    # Step 1: Handle edit segments (if any)
    if edit_plan and edit_plan.segments:
        if len(edit_plan.segments) == 1:
            # Single segment - just trim
            seg = edit_plan.segments[0]
            filters.append(
                f"[{input_label}]trim={seg.start:.6f}:{seg.end:.6f},setpts=PTS-STARTPTS[{current_label}]"
            )
        else:
            # Multiple segments - split, trim, concat
            segment_labels = []
            split_outputs = "".join(f"[s{i}]" for i in range(len(edit_plan.segments)))
            filters.append(f"[{input_label}]split={len(edit_plan.segments)}{split_outputs}")

            for i, seg in enumerate(edit_plan.segments):
                label = f"t{i}"
                filters.append(
                    f"[s{i}]trim={seg.start:.6f}:{seg.end:.6f},setpts=PTS-STARTPTS[{label}]"
                )
                segment_labels.append(f"[{label}]")

            concat_inputs = "".join(segment_labels)
            filters.append(f"{concat_inputs}concat=n={len(edit_plan.segments)}:v=1:a=0[{current_label}]")
    else:
        # No trimming, just pass through
        filters.append(f"[{input_label}]null[{current_label}]")

    # Step 2: Scale
    next_label = "v1"
    filters.append(
        f"[{current_label}]scale={crop.scaled_width}:{crop.scaled_height}[{next_label}]"
    )
    current_label = next_label

    # Step 3: Crop
    next_label = "v2"
    filters.append(
        f"[{current_label}]crop={crop.width}:{crop.height}:{crop.x}:{crop.y}[{next_label}]"
    )
    current_label = next_label

    # Step 4: Subtitles (if provided)
    if caption_path:
        # Escape special characters in path for FFmpeg
        escaped_path = caption_path.replace("\\", "\\\\").replace(":", "\\:")
        next_label = "v3"
        filters.append(
            f"[{current_label}]subtitles='{escaped_path}'[{next_label}]"
        )
        current_label = next_label

    # Rename final output to 'outv'
    if current_label != "outv":
        # Replace last label with outv
        filters[-1] = filters[-1].rsplit("[", 1)[0] + "[outv]"

    return ";".join(filters)


def build_audio_filter(
    edit_plan: Optional[VideoEditPlan] = None,
) -> Optional[str]:
    """
    Build FFmpeg audio filter for trimming.

    If edit_plan is provided, applies same trims to audio.

    Args:
        edit_plan: Optional edit plan

    Returns:
        FFmpeg audio filter string or None
    """
    if not edit_plan or not edit_plan.segments:
        return None

    if len(edit_plan.segments) == 1:
        seg = edit_plan.segments[0]
        return f"atrim={seg.start:.6f}:{seg.end:.6f},asetpts=PTS-STARTPTS"

    # Multiple segments
    filters = []
    segment_labels = []
    split_outputs = "".join(f"[a{i}]" for i in range(len(edit_plan.segments)))
    filters.append(f"[0:a]asplit={len(edit_plan.segments)}{split_outputs}")

    for i, seg in enumerate(edit_plan.segments):
        label = f"at{i}"
        filters.append(
            f"[a{i}]atrim={seg.start:.6f}:{seg.end:.6f},asetpts=PTS-STARTPTS[{label}]"
        )
        segment_labels.append(f"[{label}]")

    concat_inputs = "".join(segment_labels)
    filters.append(f"{concat_inputs}concat=n={len(edit_plan.segments)}:v=0:a=1[outa]")

    return ";".join(filters)


def render_video(
    video_path: str,
    output_path: str,
    crop: CropRegion,
    config: RenderConfig,
    edit_plan: Optional[VideoEditPlan] = None,
    audio_path: Optional[str] = None,
    transcript_words: Optional[List[Dict[str, Any]]] = None,
    overwrite: bool = True,
) -> RenderResult:
    """
    Render video with cropping, edits, and captions.

    Args:
        video_path: Path to source video
        output_path: Path for output video
        crop: CropRegion for cropping
        config: RenderConfig with format and settings
        edit_plan: Optional VideoEditPlan for trimming
        audio_path: Optional path to edited audio (replaces video audio)
        transcript_words: Optional word-level transcript for captions
        overwrite: Whether to overwrite existing output

    Returns:
        RenderResult with status and details
    """
    format_spec = config.get_format_spec()
    temp_files = []

    try:
        # Generate captions if enabled and transcript provided
        caption_path = None
        if config.include_captions and transcript_words:
            caption_path = tempfile.NamedTemporaryFile(
                suffix=".ass",
                delete=False,
                mode="w",
            ).name
            temp_files.append(caption_path)

            ass_content = generate_captions(
                words=transcript_words,
                format_type=config.format_type,
                style=config.get_caption_style(),
                format_spec=format_spec,
            )
            with open(caption_path, "w", encoding="utf-8") as f:
                f.write(ass_content)

        # Build filter complex
        filter_complex = build_ffmpeg_filter(
            crop=crop,
            format_spec=format_spec,
            edit_plan=edit_plan,
            caption_path=caption_path,
        )

        # Build FFmpeg command
        cmd = ["ffmpeg"]

        if overwrite:
            cmd.append("-y")

        # Input video
        cmd.extend(["-i", video_path])

        # Input audio (if separate)
        if audio_path:
            cmd.extend(["-i", audio_path])

        # Video filter
        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[outv]"])

        # Audio handling
        if audio_path:
            # Use separate audio file
            cmd.extend(["-map", "1:a"])
        elif edit_plan and edit_plan.segments:
            # Build audio filter for trimming
            audio_filter = build_audio_filter(edit_plan)
            if audio_filter:
                # We need to include audio in filter_complex
                # Rebuild the entire filter with audio
                full_filter = filter_complex + ";" + audio_filter
                # Re-run with updated filter
                cmd = ["ffmpeg"]
                if overwrite:
                    cmd.append("-y")
                cmd.extend(["-i", video_path])
                cmd.extend(["-filter_complex", full_filter])
                cmd.extend(["-map", "[outv]", "-map", "[outa]"])
        else:
            # Copy audio as-is
            cmd.extend(["-map", "0:a"])

        # Video encoding settings
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
        ])

        # Audio encoding
        cmd.extend([
            "-c:a", "aac",
            "-b:a", f"{format_spec.audio_bitrate_kbps}k",
        ])

        # Output
        cmd.append(output_path)

        # Run FFmpeg
        ffmpeg_cmd = " ".join(cmd)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return RenderResult(
                success=False,
                output_path=output_path,
                format_type=config.format_type,
                duration=0,
                file_size_mb=0,
                error=result.stderr[-2000:] if result.stderr else "Unknown error",
                ffmpeg_command=ffmpeg_cmd,
            )

        # Get output file info
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / (1024 * 1024)

            # Get duration with ffprobe
            probe_cmd = [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                output_path,
            ]
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
            duration = float(probe_result.stdout.strip()) if probe_result.returncode == 0 else 0
        else:
            file_size = 0
            duration = 0

        return RenderResult(
            success=True,
            output_path=output_path,
            format_type=config.format_type,
            duration=duration,
            file_size_mb=file_size,
            ffmpeg_command=ffmpeg_cmd,
        )

    finally:
        # Clean up temp files
        for f in temp_files:
            try:
                os.unlink(f)
            except:
                pass


def render_all_formats(
    video_path: str,
    output_dir: str,
    crops: Dict[ExportFormat, CropRegion],
    edit_plan: Optional[VideoEditPlan] = None,
    audio_path: Optional[str] = None,
    transcript_words: Optional[List[Dict[str, Any]]] = None,
    formats: Optional[List[ExportFormat]] = None,
    include_captions: bool = True,
) -> Dict[ExportFormat, RenderResult]:
    """
    Render video to multiple formats.

    Args:
        video_path: Path to source video
        output_dir: Directory for output files
        crops: Dict of CropRegion per format
        edit_plan: Optional edit plan for trimming
        audio_path: Optional edited audio path
        transcript_words: Optional word transcript
        formats: Specific formats to render (None = all)
        include_captions: Whether to include captions

    Returns:
        Dict of RenderResult per format
    """
    os.makedirs(output_dir, exist_ok=True)
    results = {}

    target_formats = formats or list(crops.keys())

    for fmt in target_formats:
        if fmt not in crops:
            continue

        output_path = os.path.join(
            output_dir,
            f"{Path(video_path).stem}_{fmt.value}.mp4"
        )

        config = RenderConfig(
            format_type=fmt,
            include_captions=include_captions,
        )

        result = render_video(
            video_path=video_path,
            output_path=output_path,
            crop=crops[fmt],
            config=config,
            edit_plan=edit_plan,
            audio_path=audio_path,
            transcript_words=transcript_words,
        )

        results[fmt] = result

    return results


if __name__ == "__main__":
    print("Video Renderer - Test Mode")
    print("=" * 60)

    # Check for test video
    test_video = "data/video/test.mp4"
    if not os.path.exists(test_video):
        print(f"Test video not found: {test_video}")
        print("Create one with: ffmpeg -f lavfi -i testsrc2=duration=5 -c:v libx264 test.mp4")
    else:
        from src.video.crop_calculator import CropCalculator
        from src.video.vision_detector import SubjectPosition

        print(f"\nSource: {test_video}")

        # Get video info
        from src.video.frame_sampler import get_video_info
        info = get_video_info(test_video)
        print(f"Resolution: {info['width']}x{info['height']}")
        print(f"Duration: {info['duration']:.1f}s")

        # Calculate crop for TikTok
        calculator = CropCalculator()
        subject = SubjectPosition(
            x=0.5, y=0.45, head_y=0.30,
            confidence=0.92,
            description="Test subject",
        )

        crop_result = calculator.calculate_crop(
            source_width=info["width"],
            source_height=info["height"],
            target_format=ExportFormat.TIKTOK,
            subject_position=subject,
        )

        print(f"\nCrop for TikTok:")
        print(f"  Scale: {crop_result.crop.scale:.2f}x")
        print(f"  Crop: {crop_result.crop.width}x{crop_result.crop.height} at ({crop_result.crop.x}, {crop_result.crop.y})")

        # Build filter preview
        filter_str = build_ffmpeg_filter(
            crop=crop_result.crop,
            format_spec=get_format(ExportFormat.TIKTOK),
        )

        print(f"\nFFmpeg filter_complex:")
        print(f"  {filter_str}")

        # Test render (to temp file)
        output_path = "/tmp/test_render.mp4"
        print(f"\nRendering to: {output_path}")

        config = RenderConfig(
            format_type=ExportFormat.TIKTOK,
            include_captions=False,  # No transcript for test
        )

        result = render_video(
            video_path=test_video,
            output_path=output_path,
            crop=crop_result.crop,
            config=config,
        )

        if result.success:
            print(f"  Success!")
            print(f"  Duration: {result.duration:.1f}s")
            print(f"  Size: {result.file_size_mb:.2f} MB")
        else:
            print(f"  Failed: {result.error}")
