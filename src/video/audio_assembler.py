"""
Assemble audio clips from edit segments.

Takes the smart editor output and creates a new audio file
with only the "keep" segments, properly joined.

Usage:
    from src.video.audio_assembler import assemble_audio
    output = assemble_audio(audio_path, segments_to_keep, output_path)
"""

import os
import subprocess
import tempfile
from typing import List, Dict, Optional


def assemble_audio(
    audio_path: str,
    segments: List[Dict[str, float]],
    output_path: Optional[str] = None,
    crossfade_ms: int = 10,
) -> str:
    """
    Assemble audio from multiple segments.

    Args:
        audio_path: Source audio file
        segments: List of {"start": float, "end": float} dicts for segments to keep
        output_path: Output file path (auto-generated if None)
        crossfade_ms: Crossfade duration between segments in milliseconds

    Returns:
        Path to assembled audio file
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if not segments:
        raise ValueError("No segments to assemble")

    if not output_path:
        base, ext = os.path.splitext(audio_path)
        output_path = f"{base}_edited{ext}"

    # If only one segment, just extract it directly
    if len(segments) == 1:
        seg = segments[0]
        cmd = [
            "ffmpeg", "-y",
            "-i", audio_path,
            "-ss", str(seg["start"]),
            "-t", str(seg["end"] - seg["start"]),
            "-c", "copy",
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    # Multiple segments - need to extract and concatenate
    temp_dir = tempfile.mkdtemp(prefix="audio_assemble_")
    temp_files = []

    try:
        # Extract each segment
        for i, seg in enumerate(segments):
            temp_file = os.path.join(temp_dir, f"seg_{i:04d}.wav")
            temp_files.append(temp_file)

            duration = seg["end"] - seg["start"]
            if duration <= 0:
                continue

            cmd = [
                "ffmpeg", "-y",
                "-i", audio_path,
                "-ss", str(seg["start"]),
                "-t", str(duration),
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                temp_file
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Warning: Failed to extract segment {i}: {result.stderr}")

        # Filter out failed/empty files
        temp_files = [f for f in temp_files if os.path.exists(f) and os.path.getsize(f) > 44]  # 44 = WAV header size

        if not temp_files:
            raise ValueError("No valid segments extracted")

        # Create concat list file
        concat_list = os.path.join(temp_dir, "concat.txt")
        with open(concat_list, "w") as f:
            for temp_file in temp_files:
                f.write(f"file '{temp_file}'\n")

        # Concatenate all segments
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list,
            "-c", "copy",
            output_path
        ]
        result = subprocess.run(concat_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to concatenate: {result.stderr}")

    finally:
        # Cleanup temp files
        for f in temp_files:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists(concat_list):
            os.remove(concat_list)
        if os.path.exists(temp_dir):
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass  # Directory not empty, ignore

    return output_path


def create_edited_clip(
    audio_path: str,
    transcript_segments: List[Dict],
    clip_start: float,
    clip_end: float,
    preset: str = "linkedin",
    output_path: Optional[str] = None,
) -> Dict:
    """
    Create an edited clip with smart editing applied.

    Args:
        audio_path: Source audio file
        transcript_segments: Full transcript with word-level timestamps
        clip_start: Clip start time
        clip_end: Clip end time
        preset: Editing preset (youtube_shorts, tiktok, linkedin, podcast)
        output_path: Output file path

    Returns:
        Dict with output_path, time_savings, and edit_details
    """
    from src.video.smart_editor import analyze_clip

    # Analyze the clip
    analysis = analyze_clip(transcript_segments, clip_start, clip_end, preset)

    segments_to_keep = analysis["segments_to_keep"]

    if not segments_to_keep:
        raise ValueError("No segments to keep after analysis")

    # Assemble the audio
    if not output_path:
        base = os.path.splitext(audio_path)[0]
        output_path = f"{base}_clip_{clip_start:.1f}_{clip_end:.1f}_{preset}.wav"

    assemble_audio(audio_path, segments_to_keep, output_path)

    return {
        "output_path": output_path,
        "time_savings": analysis["time_savings"],
        "edit_details": analysis["edit_details"],
        "segments_kept": len(segments_to_keep),
    }


if __name__ == "__main__":
    print("Audio Assembler - Test Mode")
    print("=" * 60)
    print("Run with actual audio file and segment data to test")
