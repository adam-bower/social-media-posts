"""
Frame sampling from video files using FFmpeg.

Extracts frames at specific timestamps for vision AI analysis.
Supports sparse mode (5 key frames) and dense mode (1fps).

Usage:
    from src.video.frame_sampler import sample_frames, SamplingMode

    # Sparse sampling (5 frames for quick analysis)
    frames = sample_frames("video.mp4", mode=SamplingMode.SPARSE)

    # Dense sampling (1 frame per second)
    frames = sample_frames("video.mp4", mode=SamplingMode.DENSE)
"""

import os
import subprocess
import tempfile
import base64
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path


class SamplingMode(Enum):
    """Frame sampling modes."""
    SPARSE = "sparse"    # 5 frames: start, 25%, 50%, 75%, end
    DENSE = "dense"      # 1 frame per second
    CUSTOM = "custom"    # User-specified timestamps


@dataclass
class SampledFrame:
    """A single sampled frame from video."""
    timestamp: float       # Timestamp in seconds
    index: int            # Frame index in sequence
    width: int            # Frame width in pixels
    height: int           # Frame height in pixels
    jpeg_bytes: bytes     # JPEG-encoded frame data
    file_path: Optional[str] = None  # Path if saved to disk

    @property
    def base64(self) -> str:
        """Return frame as base64-encoded string for API calls."""
        return base64.b64encode(self.jpeg_bytes).decode('utf-8')

    @property
    def data_url(self) -> str:
        """Return frame as data URL for embedding in HTML/JSON."""
        return f"data:image/jpeg;base64,{self.base64}"

    @property
    def size_kb(self) -> float:
        """Return frame size in KB."""
        return len(self.jpeg_bytes) / 1024


@dataclass
class SamplingResult:
    """Result of frame sampling operation."""
    video_path: str
    duration: float
    width: int
    height: int
    fps: float
    mode: SamplingMode
    frames: List[SampledFrame]

    @property
    def total_size_kb(self) -> float:
        """Total size of all frames in KB."""
        return sum(f.size_kb for f in self.frames)

    def get_frame_at(self, timestamp: float, tolerance: float = 0.5) -> Optional[SampledFrame]:
        """Get frame closest to given timestamp within tolerance."""
        for frame in self.frames:
            if abs(frame.timestamp - timestamp) <= tolerance:
                return frame
        return None


def get_video_info(video_path: str) -> Dict[str, Any]:
    """
    Get video metadata using ffprobe.

    Args:
        video_path: Path to video file

    Returns:
        Dictionary with duration, resolution, fps
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

    format_info = data.get("format", {})
    streams = data.get("streams", [])

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)

    if not video_stream:
        raise ValueError(f"No video stream found in: {video_path}")

    # Parse frame rate
    fps_str = video_stream.get("r_frame_rate", "30/1")
    try:
        if "/" in fps_str:
            num, den = fps_str.split("/")
            fps = float(num) / float(den) if float(den) != 0 else 30.0
        else:
            fps = float(fps_str)
    except:
        fps = 30.0

    return {
        "duration": float(format_info.get("duration", 0)),
        "width": video_stream.get("width"),
        "height": video_stream.get("height"),
        "fps": fps,
        "codec": video_stream.get("codec_name"),
    }


def _extract_frame_at_timestamp(
    video_path: str,
    timestamp: float,
    output_path: str,
    quality: int = 2,  # 2-31, lower is better
) -> bool:
    """
    Extract a single frame at specific timestamp.

    Args:
        video_path: Path to video file
        timestamp: Time in seconds
        output_path: Output JPEG path
        quality: JPEG quality (2-31, lower is better)

    Returns:
        True if successful
    """
    cmd = [
        "ffmpeg",
        "-y",                    # Overwrite output
        "-ss", str(timestamp),   # Seek to timestamp
        "-i", video_path,        # Input file
        "-vframes", "1",         # Extract 1 frame
        "-q:v", str(quality),    # JPEG quality
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0 and os.path.exists(output_path)


def _calculate_sparse_timestamps(duration: float) -> List[float]:
    """
    Calculate 5 timestamps for sparse sampling.

    Returns timestamps at: start, 25%, 50%, 75%, end
    Start is offset slightly to avoid black frames.
    """
    if duration <= 0:
        return []

    # Offset start by 0.5s or 2% of duration, whichever is smaller
    start_offset = min(0.5, duration * 0.02)
    # End offset to avoid potential black frames at end
    end_offset = min(0.5, duration * 0.02)

    timestamps = [
        start_offset,                    # Start (with offset)
        duration * 0.25,                 # 25%
        duration * 0.50,                 # 50%
        duration * 0.75,                 # 75%
        duration - end_offset,           # End (with offset)
    ]

    # Ensure all timestamps are valid
    return [max(0, min(t, duration)) for t in timestamps]


def _calculate_dense_timestamps(duration: float, fps: float = 1.0) -> List[float]:
    """
    Calculate timestamps for dense sampling (1 frame per second by default).

    Args:
        duration: Video duration in seconds
        fps: Frames per second to sample (default 1.0)

    Returns:
        List of timestamps
    """
    if duration <= 0:
        return []

    interval = 1.0 / fps
    timestamps = []
    t = 0.5  # Start slightly offset

    while t < duration - 0.5:
        timestamps.append(t)
        t += interval

    return timestamps


def sample_frames(
    video_path: str,
    mode: SamplingMode = SamplingMode.SPARSE,
    timestamps: Optional[List[float]] = None,
    clip_start: Optional[float] = None,
    clip_end: Optional[float] = None,
    max_dimension: int = 1280,
    quality: int = 2,
    keep_files: bool = False,
    output_dir: Optional[str] = None,
) -> SamplingResult:
    """
    Sample frames from a video file.

    Args:
        video_path: Path to video file
        mode: Sampling mode (SPARSE, DENSE, or CUSTOM)
        timestamps: Custom timestamps (required if mode=CUSTOM)
        clip_start: Start of clip to sample (optional)
        clip_end: End of clip to sample (optional)
        max_dimension: Maximum width or height (frames scaled to fit)
        quality: JPEG quality (2-31, lower is better)
        keep_files: Keep extracted frame files (otherwise temp files deleted)
        output_dir: Directory for output files (uses temp if None)

    Returns:
        SamplingResult with extracted frames
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Get video info
    info = get_video_info(video_path)
    duration = info["duration"]
    width = info["width"]
    height = info["height"]
    fps = info["fps"]

    # Apply clip range
    effective_start = clip_start or 0
    effective_end = clip_end or duration
    effective_duration = effective_end - effective_start

    # Calculate timestamps based on mode
    if mode == SamplingMode.SPARSE:
        sample_times = _calculate_sparse_timestamps(effective_duration)
        # Offset timestamps by clip_start
        sample_times = [t + effective_start for t in sample_times]
    elif mode == SamplingMode.DENSE:
        sample_times = _calculate_dense_timestamps(effective_duration)
        sample_times = [t + effective_start for t in sample_times]
    elif mode == SamplingMode.CUSTOM:
        if not timestamps:
            raise ValueError("Custom mode requires timestamps list")
        sample_times = timestamps
    else:
        raise ValueError(f"Unknown sampling mode: {mode}")

    # Calculate scale filter if needed
    scale_filter = None
    if max_dimension and (width > max_dimension or height > max_dimension):
        if width >= height:
            scale_filter = f"scale={max_dimension}:-2"
        else:
            scale_filter = f"scale=-2:{max_dimension}"

    # Create output directory
    if keep_files and output_dir:
        os.makedirs(output_dir, exist_ok=True)
        temp_dir = output_dir
        cleanup_temp = False
    else:
        temp_dir = tempfile.mkdtemp(prefix="frames_")
        cleanup_temp = not keep_files

    frames = []
    try:
        for idx, timestamp in enumerate(sample_times):
            output_path = os.path.join(temp_dir, f"frame_{idx:04d}.jpg")

            # Build FFmpeg command
            cmd = [
                "ffmpeg",
                "-y",
                "-ss", str(timestamp),
                "-i", video_path,
                "-vframes", "1",
                "-q:v", str(quality),
            ]

            if scale_filter:
                cmd.extend(["-vf", scale_filter])

            cmd.append(output_path)

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0 and os.path.exists(output_path):
                # Read frame data
                with open(output_path, "rb") as f:
                    jpeg_bytes = f.read()

                # Get actual frame dimensions (may be scaled)
                probe_cmd = [
                    "ffprobe", "-v", "quiet",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=width,height",
                    "-of", "csv=p=0",
                    output_path,
                ]
                probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
                if probe_result.returncode == 0:
                    dims = probe_result.stdout.strip().split(",")
                    frame_width = int(dims[0])
                    frame_height = int(dims[1])
                else:
                    frame_width = width
                    frame_height = height

                frame = SampledFrame(
                    timestamp=timestamp,
                    index=idx,
                    width=frame_width,
                    height=frame_height,
                    jpeg_bytes=jpeg_bytes,
                    file_path=output_path if keep_files else None,
                )
                frames.append(frame)

                # Clean up if not keeping files
                if not keep_files:
                    os.unlink(output_path)

    finally:
        # Clean up temp directory if not keeping files
        if cleanup_temp and os.path.exists(temp_dir):
            try:
                os.rmdir(temp_dir)
            except:
                pass

    return SamplingResult(
        video_path=video_path,
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        mode=mode,
        frames=frames,
    )


def sample_single_frame(
    video_path: str,
    timestamp: float,
    max_dimension: int = 1280,
    quality: int = 2,
) -> SampledFrame:
    """
    Sample a single frame at specific timestamp.

    Convenience function for extracting just one frame.

    Args:
        video_path: Path to video file
        timestamp: Time in seconds
        max_dimension: Maximum width or height
        quality: JPEG quality

    Returns:
        SampledFrame object
    """
    result = sample_frames(
        video_path,
        mode=SamplingMode.CUSTOM,
        timestamps=[timestamp],
        max_dimension=max_dimension,
        quality=quality,
    )

    if not result.frames:
        raise RuntimeError(f"Failed to extract frame at {timestamp}s")

    return result.frames[0]


if __name__ == "__main__":
    import sys
    import glob

    print("Frame Sampler - Test Mode")
    print("=" * 60)

    # Look for test video
    video_files = glob.glob("data/video/*.mp4") + glob.glob("data/video/*.MP4")

    if not video_files:
        print("No video files found in data/video/")
        sys.exit(1)

    video_path = video_files[0]
    print(f"Testing with: {video_path}")

    # Get video info
    info = get_video_info(video_path)
    print(f"\nVideo info:")
    print(f"  Duration: {info['duration']:.1f}s")
    print(f"  Resolution: {info['width']}x{info['height']}")
    print(f"  FPS: {info['fps']:.2f}")

    # Test sparse sampling
    print(f"\nSparse sampling (5 frames)...")
    result = sample_frames(video_path, mode=SamplingMode.SPARSE, max_dimension=720)
    print(f"  Extracted {len(result.frames)} frames")
    print(f"  Total size: {result.total_size_kb:.1f} KB")

    for frame in result.frames:
        print(f"    Frame {frame.index}: {frame.timestamp:.1f}s, {frame.width}x{frame.height}, {frame.size_kb:.1f}KB")

    # Show base64 preview length
    if result.frames:
        b64_len = len(result.frames[0].base64)
        print(f"\n  Base64 length per frame: ~{b64_len} chars")
