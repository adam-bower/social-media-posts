"""
Extract audio from video files using FFmpeg.

Converts video files to audio format suitable for Whisper transcription.

Usage:
    from src.video.audio_extractor import extract_audio
    audio_path = extract_audio("/path/to/video.mp4")
"""

import os
import subprocess
import tempfile
from typing import Optional, Tuple
from pathlib import Path


def get_video_info(video_path: str) -> dict:
    """
    Get video metadata using ffprobe.

    Args:
        video_path: Path to video file

    Returns:
        Dictionary with duration, resolution, codec info
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    import json
    data = json.loads(result.stdout)

    # Extract relevant info
    format_info = data.get("format", {})
    streams = data.get("streams", [])

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    info = {
        "duration": float(format_info.get("duration", 0)),
        "size_bytes": int(format_info.get("size", 0)),
        "format": format_info.get("format_name", ""),
    }

    if video_stream:
        info["video"] = {
            "codec": video_stream.get("codec_name"),
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
            "fps": eval(video_stream.get("r_frame_rate", "0/1")),
        }
        info["resolution"] = f"{video_stream.get('width')}x{video_stream.get('height')}"

    if audio_stream:
        info["audio"] = {
            "codec": audio_stream.get("codec_name"),
            "sample_rate": int(audio_stream.get("sample_rate", 0)),
            "channels": audio_stream.get("channels"),
        }

    return info


def extract_audio(
    video_path: str,
    output_path: Optional[str] = None,
    output_format: str = "wav",
    sample_rate: int = 16000,
    mono: bool = True,
) -> str:
    """
    Extract audio track from video file.

    Args:
        video_path: Path to input video file
        output_path: Path for output audio. If None, creates temp file.
        output_format: Audio format (wav, mp3, m4a)
        sample_rate: Audio sample rate in Hz (16000 for Whisper)
        mono: Convert to mono (recommended for Whisper)

    Returns:
        Path to extracted audio file
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Generate output path if not provided
    if output_path is None:
        video_name = Path(video_path).stem
        output_path = os.path.join(
            tempfile.gettempdir(),
            f"{video_name}_audio.{output_format}"
        )

    # Build FFmpeg command
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vn",  # No video
        "-acodec", "pcm_s16le" if output_format == "wav" else "libmp3lame",
        "-ar", str(sample_rate),
    ]

    if mono:
        cmd.extend(["-ac", "1"])

    # Overwrite output if exists
    cmd.extend(["-y", output_path])

    # Run FFmpeg
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr}")

    return output_path


def extract_audio_segment(
    video_path: str,
    start_time: float,
    end_time: float,
    output_path: Optional[str] = None,
    output_format: str = "wav",
) -> str:
    """
    Extract a specific segment of audio from video.

    Args:
        video_path: Path to input video file
        start_time: Start time in seconds
        end_time: End time in seconds
        output_path: Path for output audio
        output_format: Audio format

    Returns:
        Path to extracted audio segment
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    duration = end_time - start_time
    if duration <= 0:
        raise ValueError(f"Invalid time range: {start_time} to {end_time}")

    # Generate output path if not provided
    if output_path is None:
        video_name = Path(video_path).stem
        output_path = os.path.join(
            tempfile.gettempdir(),
            f"{video_name}_{start_time:.1f}_{end_time:.1f}.{output_format}"
        )

    cmd = [
        "ffmpeg",
        "-ss", str(start_time),
        "-i", video_path,
        "-t", str(duration),
        "-vn",
        "-acodec", "pcm_s16le" if output_format == "wav" else "libmp3lame",
        "-ar", "16000",
        "-ac", "1",
        "-y", output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg segment extraction failed: {result.stderr}")

    return output_path


def main(
    video_path: str,
    output_path: Optional[str] = None,
) -> dict:
    """
    Windmill-compatible entry point for audio extraction.

    Args:
        video_path: Path to video file
        output_path: Optional output path

    Returns:
        Dictionary with audio_path and video_info
    """
    info = get_video_info(video_path)
    audio_path = extract_audio(video_path, output_path)

    return {
        "audio_path": audio_path,
        "video_info": info,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.video.audio_extractor <video_path> [output_path]")
        sys.exit(1)

    video_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"Extracting audio from: {video_path}")

    result = main(video_path, output_path)

    print(f"Video duration: {result['video_info']['duration']:.1f}s")
    print(f"Resolution: {result['video_info'].get('resolution', 'N/A')}")
    print(f"Audio extracted to: {result['audio_path']}")
