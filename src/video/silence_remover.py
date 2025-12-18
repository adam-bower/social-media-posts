"""
Remove silence periods from audio using FFmpeg.

Creates a cleaner audio file by removing or shortening long pauses.

Usage:
    from src.video.silence_remover import remove_silences
    output_path = remove_silences(audio_path, silences)
"""

import os
import subprocess
import tempfile
from typing import List, Dict, Optional


def remove_silences(
    audio_path: str,
    silences: List[Dict[str, float]],
    output_path: Optional[str] = None,
    min_silence_to_remove: float = 0.8,
    keep_pause_duration: float = 0.3,
) -> str:
    """
    Remove silence periods from audio file.

    Args:
        audio_path: Path to input audio file
        silences: List of silence dicts with 'start', 'end', 'duration' keys
        output_path: Output file path. If None, generates one
        min_silence_to_remove: Only remove silences longer than this (seconds)
        keep_pause_duration: Keep this much pause at each silence point (seconds)

    Returns:
        Path to the output audio file with silences removed
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    if not output_path:
        base, ext = os.path.splitext(audio_path)
        output_path = f"{base}_no_silence{ext}"

    # Filter to silences worth removing
    removable = [s for s in silences if s['duration'] >= min_silence_to_remove]

    if not removable:
        # No silences to remove, just copy the file
        subprocess.run(
            ["cp", audio_path, output_path],
            check=True,
        )
        return output_path

    # Build filter complex for removing silences
    # We'll use the select/aselect filter to keep non-silent parts
    # Or use concat to join the speaking segments

    # Get audio duration
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        audio_path
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    total_duration = float(result.stdout.strip())

    # Build segments to keep (inverse of silences)
    segments_to_keep = []
    current_pos = 0.0

    for silence in sorted(removable, key=lambda s: s['start']):
        # Keep content before this silence
        if silence['start'] > current_pos:
            segments_to_keep.append({
                'start': current_pos,
                'end': silence['start'] + (keep_pause_duration / 2),
            })
        # Skip past the silence, but keep a small pause
        current_pos = silence['end'] - (keep_pause_duration / 2)

    # Keep content after last silence
    if current_pos < total_duration:
        segments_to_keep.append({
            'start': current_pos,
            'end': total_duration,
        })

    if not segments_to_keep:
        raise ValueError("No audio segments to keep after silence removal")

    # Use FFmpeg concat demuxer approach
    # First, extract each segment to temp files, then concat
    temp_dir = tempfile.mkdtemp(prefix="silence_removal_")
    temp_files = []

    try:
        for i, seg in enumerate(segments_to_keep):
            temp_file = os.path.join(temp_dir, f"segment_{i:04d}.wav")
            temp_files.append(temp_file)

            duration = seg['end'] - seg['start']
            if duration <= 0:
                continue

            cmd = [
                "ffmpeg", "-y",
                "-i", audio_path,
                "-ss", str(seg['start']),
                "-t", str(duration),
                "-c", "copy",
                temp_file
            ]
            subprocess.run(cmd, capture_output=True, check=True)

        # Filter out empty files
        temp_files = [f for f in temp_files if os.path.exists(f) and os.path.getsize(f) > 0]

        if not temp_files:
            raise ValueError("No valid segments after extraction")

        # Create concat list file
        concat_list = os.path.join(temp_dir, "concat.txt")
        with open(concat_list, "w") as f:
            for temp_file in temp_files:
                f.write(f"file '{temp_file}'\n")

        # Concat all segments
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list,
            "-c", "copy",
            output_path
        ]
        subprocess.run(concat_cmd, capture_output=True, check=True)

    finally:
        # Cleanup temp files
        for f in temp_files:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists(concat_list):
            os.remove(concat_list)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)

    return output_path


def extract_clip_with_silence_removed(
    audio_path: str,
    start_time: float,
    end_time: float,
    silences: List[Dict[str, float]],
    output_path: Optional[str] = None,
    min_silence_to_remove: float = 0.8,
    keep_pause_duration: float = 0.3,
) -> str:
    """
    Extract a clip from audio and remove silences within that clip.

    Args:
        audio_path: Path to source audio
        start_time: Clip start time in seconds
        end_time: Clip end time in seconds
        silences: List of all silence periods
        output_path: Output path for the clip
        min_silence_to_remove: Minimum silence duration to remove
        keep_pause_duration: Duration of pause to keep at silence points

    Returns:
        Path to the extracted clip with silences removed
    """
    if not output_path:
        base = os.path.splitext(audio_path)[0]
        output_path = f"{base}_clip_{start_time:.1f}_{end_time:.1f}.wav"

    # Filter silences to those within the clip range
    clip_silences = []
    for s in silences:
        if s['end'] > start_time and s['start'] < end_time:
            clip_silences.append({
                'start': max(0, s['start'] - start_time),
                'end': min(end_time - start_time, s['end'] - start_time),
                'duration': s['duration'],
            })

    # First extract the clip segment
    temp_clip = output_path + ".temp.wav"
    extract_cmd = [
        "ffmpeg", "-y",
        "-i", audio_path,
        "-ss", str(start_time),
        "-t", str(end_time - start_time),
        "-c", "copy",
        temp_clip
    ]
    subprocess.run(extract_cmd, capture_output=True, check=True)

    try:
        # Remove silences from the clip
        if clip_silences:
            remove_silences(
                temp_clip,
                clip_silences,
                output_path,
                min_silence_to_remove,
                keep_pause_duration,
            )
        else:
            # No silences in this clip, just rename
            os.rename(temp_clip, output_path)
            temp_clip = None
    finally:
        if temp_clip and os.path.exists(temp_clip):
            os.remove(temp_clip)

    return output_path


def get_clip_duration_after_silence_removal(
    start_time: float,
    end_time: float,
    silences: List[Dict[str, float]],
    min_silence_to_remove: float = 0.8,
    keep_pause_duration: float = 0.3,
) -> float:
    """
    Calculate what the clip duration will be after silence removal.

    Useful for estimating final clip length before actually rendering.

    Args:
        start_time: Clip start time
        end_time: Clip end time
        silences: List of silence periods
        min_silence_to_remove: Minimum silence to remove
        keep_pause_duration: Pause duration to keep

    Returns:
        Estimated duration after silence removal
    """
    original_duration = end_time - start_time

    # Calculate total silence to be removed
    total_removed = 0.0
    for s in silences:
        if s['end'] > start_time and s['start'] < end_time and s['duration'] >= min_silence_to_remove:
            # Calculate overlap with clip
            silence_start = max(start_time, s['start'])
            silence_end = min(end_time, s['end'])
            silence_duration = silence_end - silence_start

            # We remove the silence minus the pause we keep
            removed = max(0, silence_duration - keep_pause_duration)
            total_removed += removed

    return original_duration - total_removed


if __name__ == "__main__":
    print("Silence Remover - Test Mode")
    print("=" * 60)
    print("Run with actual audio file and silence data to test")
