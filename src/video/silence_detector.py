"""
Detect silence periods in audio using FFmpeg silencedetect filter.

Identifies natural pauses in speech for potential clip boundaries.

Usage:
    from src.video.silence_detector import detect_silences
    silences = detect_silences("/path/to/audio.wav")
"""

import subprocess
import re
from typing import List, Dict, Optional


def detect_silences(
    audio_path: str,
    noise_threshold: str = "-30dB",
    min_duration: float = 0.8,
) -> List[Dict[str, float]]:
    """
    Detect silence periods in audio file using FFmpeg.

    Args:
        audio_path: Path to audio file
        noise_threshold: Volume threshold for silence detection (e.g., "-30dB", "-40dB")
        min_duration: Minimum silence duration in seconds to detect

    Returns:
        List of silence periods: [{start, end, duration}]
    """
    cmd = [
        "ffmpeg",
        "-i", audio_path,
        "-af", f"silencedetect=noise={noise_threshold}:d={min_duration}",
        "-f", "null",
        "-"
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    # FFmpeg outputs silence info to stderr
    output = result.stderr

    # Parse silence_start and silence_end from output
    # Example output lines:
    # [silencedetect @ 0x...] silence_start: 1.234
    # [silencedetect @ 0x...] silence_end: 2.567 | silence_duration: 1.333

    silences = []
    current_start = None

    # Pattern for silence_start
    start_pattern = re.compile(r'silence_start:\s*([\d.]+)')
    # Pattern for silence_end with duration
    end_pattern = re.compile(r'silence_end:\s*([\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)')

    for line in output.split('\n'):
        start_match = start_pattern.search(line)
        if start_match:
            current_start = float(start_match.group(1))
            continue

        end_match = end_pattern.search(line)
        if end_match and current_start is not None:
            end_time = float(end_match.group(1))
            duration = float(end_match.group(2))

            silences.append({
                "start": current_start,
                "end": end_time,
                "duration": duration,
            })
            current_start = None

    return silences


def find_speech_segments(
    silences: List[Dict[str, float]],
    total_duration: float,
    min_speech_duration: float = 5.0,
) -> List[Dict[str, float]]:
    """
    Find speech segments (inverse of silence periods).

    Args:
        silences: List of silence periods from detect_silences()
        total_duration: Total audio duration in seconds
        min_speech_duration: Minimum speech segment duration to include

    Returns:
        List of speech segments: [{start, end, duration}]
    """
    if not silences:
        return [{
            "start": 0,
            "end": total_duration,
            "duration": total_duration,
        }]

    segments = []
    current_pos = 0.0

    for silence in sorted(silences, key=lambda x: x["start"]):
        if silence["start"] > current_pos:
            duration = silence["start"] - current_pos
            if duration >= min_speech_duration:
                segments.append({
                    "start": current_pos,
                    "end": silence["start"],
                    "duration": duration,
                })
        current_pos = silence["end"]

    # Add final segment after last silence
    if current_pos < total_duration:
        duration = total_duration - current_pos
        if duration >= min_speech_duration:
            segments.append({
                "start": current_pos,
                "end": total_duration,
                "duration": duration,
            })

    return segments


def find_natural_breaks(
    silences: List[Dict[str, float]],
    min_break_duration: float = 1.0,
) -> List[float]:
    """
    Find natural break points (longer silences) for potential clip boundaries.

    Args:
        silences: List of silence periods
        min_break_duration: Minimum silence duration to consider as a natural break

    Returns:
        List of timestamps (midpoints of longer silences)
    """
    breaks = []

    for silence in silences:
        if silence["duration"] >= min_break_duration:
            # Use midpoint of silence as break point
            midpoint = (silence["start"] + silence["end"]) / 2
            breaks.append(midpoint)

    return sorted(breaks)


def main(
    audio_path: str,
    noise_threshold: str = "-30dB",
    min_duration: float = 0.8,
) -> Dict:
    """
    Windmill-compatible entry point for silence detection.

    Args:
        audio_path: Path to audio file
        noise_threshold: Volume threshold for silence
        min_duration: Minimum silence duration

    Returns:
        Dictionary with silences and natural breaks
    """
    silences = detect_silences(audio_path, noise_threshold, min_duration)
    breaks = find_natural_breaks(silences, min_break_duration=1.0)

    return {
        "silences": silences,
        "natural_breaks": breaks,
        "silence_count": len(silences),
        "total_silence_duration": sum(s["duration"] for s in silences),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.video.silence_detector <audio_path>")
        sys.exit(1)

    audio_path = sys.argv[1]

    print(f"Detecting silences in: {audio_path}")
    print("-" * 60)

    result = main(audio_path)

    print(f"Found {result['silence_count']} silence periods")
    print(f"Total silence: {result['total_silence_duration']:.1f}s")
    print(f"Natural breaks: {len(result['natural_breaks'])}")

    print("\nSilence periods:")
    for i, silence in enumerate(result['silences'][:10]):
        print(f"  {i+1}. {silence['start']:.2f}s - {silence['end']:.2f}s ({silence['duration']:.2f}s)")

    if len(result['silences']) > 10:
        print(f"  ... and {len(result['silences']) - 10} more")

    print("\nNatural break points:")
    for i, bp in enumerate(result['natural_breaks'][:10]):
        print(f"  {i+1}. {bp:.2f}s")
