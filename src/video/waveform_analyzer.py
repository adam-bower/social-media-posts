"""
Audio waveform analysis for precise clip boundaries.

Uses the actual audio amplitude to:
1. Find true silence points (low amplitude)
2. Verify word boundaries match audio
3. Snap clip boundaries to natural pauses
4. Avoid cutting mid-word based on actual sound
"""

import numpy as np
import subprocess
import tempfile
import os
from typing import List, Dict, Tuple, Optional


def get_audio_samples(audio_path: str, sample_rate: int = 16000) -> Tuple[np.ndarray, int]:
    """
    Load audio file and get raw samples.

    Returns:
        Tuple of (samples array, sample rate)
    """
    try:
        import soundfile as sf
        samples, sr = sf.read(audio_path)
        if len(samples.shape) > 1:
            samples = samples.mean(axis=1)  # Convert stereo to mono
        return samples, sr
    except ImportError:
        # Fallback: use ffmpeg to extract raw samples
        with tempfile.NamedTemporaryFile(suffix='.raw', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            subprocess.run([
                'ffmpeg', '-y', '-i', audio_path,
                '-f', 's16le', '-acodec', 'pcm_s16le',
                '-ar', str(sample_rate), '-ac', '1',
                tmp_path
            ], capture_output=True, check=True)

            samples = np.fromfile(tmp_path, dtype=np.int16).astype(np.float32) / 32768.0
            return samples, sample_rate
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


def compute_rms_envelope(
    samples: np.ndarray,
    sample_rate: int,
    window_ms: int = 25,
    hop_ms: int = 10,
) -> Tuple[np.ndarray, float]:
    """
    Compute RMS (root mean square) envelope of audio.

    This gives us the "loudness" at each point in time.

    Returns:
        Tuple of (RMS values array, time step between values in seconds)
    """
    window_size = int(sample_rate * window_ms / 1000)
    hop_size = int(sample_rate * hop_ms / 1000)

    num_frames = (len(samples) - window_size) // hop_size + 1
    rms = np.zeros(num_frames)

    for i in range(num_frames):
        start = i * hop_size
        end = start + window_size
        frame = samples[start:end]
        rms[i] = np.sqrt(np.mean(frame ** 2))

    time_step = hop_ms / 1000  # Convert to seconds
    return rms, time_step


def find_silence_points(
    rms: np.ndarray,
    time_step: float,
    threshold_db: float = -25,
    min_duration_ms: int = 80,
) -> List[Dict]:
    """
    Find points in audio that are relatively quiet (natural pauses).

    Args:
        rms: RMS envelope values
        time_step: Time step between RMS values
        threshold_db: Quiet threshold in dB (relative to max). -25dB catches natural pauses, -40dB only catches true silence
        min_duration_ms: Minimum pause duration in milliseconds

    Returns:
        List of quiet regions with start, end, duration
    """
    # Convert threshold to linear scale
    # -25dB means ~5.6% of max amplitude - catches natural speech pauses
    max_rms = np.max(rms) if np.max(rms) > 0 else 1e-10
    threshold = max_rms * (10 ** (threshold_db / 20))

    # Find silent frames
    is_silent = rms < threshold

    # Find contiguous silent regions
    silences = []
    in_silence = False
    silence_start = 0

    min_frames = int(min_duration_ms / (time_step * 1000))

    for i, silent in enumerate(is_silent):
        if silent and not in_silence:
            in_silence = True
            silence_start = i
        elif not silent and in_silence:
            in_silence = False
            duration_frames = i - silence_start
            if duration_frames >= min_frames:
                silences.append({
                    'start': silence_start * time_step,
                    'end': i * time_step,
                    'duration': duration_frames * time_step,
                    'midpoint': (silence_start + i) / 2 * time_step,
                })

    # Handle silence at end
    if in_silence:
        duration_frames = len(is_silent) - silence_start
        if duration_frames >= min_frames:
            silences.append({
                'start': silence_start * time_step,
                'end': len(is_silent) * time_step,
                'duration': duration_frames * time_step,
                'midpoint': (silence_start + len(is_silent)) / 2 * time_step,
            })

    return silences


def find_nearest_silence(
    target_time: float,
    silences: List[Dict],
    search_window: float = 1.0,
    prefer_before: bool = True,
) -> Optional[float]:
    """
    Find the nearest silence point to a target time.

    Args:
        target_time: Time we want to cut at
        silences: List of silence regions
        search_window: How far to search (seconds)
        prefer_before: If true, prefer silence points before target

    Returns:
        Optimal cut point (silence midpoint), or None if no silence nearby
    """
    candidates = []

    for silence in silences:
        # Check if silence is within search window of target
        if abs(silence['midpoint'] - target_time) <= search_window:
            distance = silence['midpoint'] - target_time
            candidates.append({
                'time': silence['midpoint'],
                'distance': abs(distance),
                'before': distance < 0,
                'duration': silence['duration'],
            })

    if not candidates:
        return None

    # Sort by preference: longer silences and correct direction
    def score(c):
        direction_bonus = 0.1 if (c['before'] == prefer_before) else 0
        duration_bonus = min(c['duration'] / 2, 0.2)  # Cap at 0.2
        return c['distance'] - direction_bonus - duration_bonus

    candidates.sort(key=score)
    return candidates[0]['time']


def snap_to_silence(
    start_time: float,
    end_time: float,
    audio_path: str,
    search_window: float = 0.5,
) -> Tuple[float, float]:
    """
    Snap clip boundaries to nearest silence points.

    Args:
        start_time: Requested start time
        end_time: Requested end time
        audio_path: Path to audio file
        search_window: How far to search for silence (seconds)

    Returns:
        Tuple of (snapped_start, snapped_end)
    """
    # Load audio and compute envelope
    samples, sr = get_audio_samples(audio_path)
    rms, time_step = compute_rms_envelope(samples, sr)
    silences = find_silence_points(rms, time_step)

    # Find best silence for start (prefer before)
    snapped_start = find_nearest_silence(
        start_time, silences, search_window, prefer_before=True
    )
    if snapped_start is None:
        snapped_start = start_time

    # Find best silence for end (prefer after)
    snapped_end = find_nearest_silence(
        end_time, silences, search_window, prefer_before=False
    )
    if snapped_end is None:
        snapped_end = end_time

    # Ensure we didn't flip start/end
    if snapped_start >= snapped_end:
        return start_time, end_time

    return snapped_start, snapped_end


def analyze_clip_boundaries(
    clip_segments: List[Dict],
    audio_path: str,
    search_window: float = 0.5,
) -> List[Dict]:
    """
    Analyze and adjust clip segment boundaries using waveform.

    Args:
        clip_segments: List of segments with start_time, end_time
        audio_path: Path to audio file
        search_window: How far to search for silence

    Returns:
        List of segments with snapped boundaries
    """
    # Load audio once
    samples, sr = get_audio_samples(audio_path)
    rms, time_step = compute_rms_envelope(samples, sr)
    silences = find_silence_points(rms, time_step)

    adjusted = []
    for seg in clip_segments:
        start = seg.get('start_time', 0)
        end = seg.get('end_time', start)

        # Snap to silence
        snapped_start = find_nearest_silence(start, silences, search_window, True)
        snapped_end = find_nearest_silence(end, silences, search_window, False)

        adjusted.append({
            **seg,
            'start_time': snapped_start or start,
            'end_time': snapped_end or end,
            'original_start': start,
            'original_end': end,
            'was_adjusted': (snapped_start != start) or (snapped_end != end),
        })

    return adjusted


def get_amplitude_at_time(
    audio_path: str,
    time_seconds: float,
    window_ms: int = 50,
) -> float:
    """
    Get the amplitude level at a specific time point.

    Useful for verifying if a cut point is in silence.

    Returns:
        RMS amplitude (0.0 = silence, higher = louder)
    """
    samples, sr = get_audio_samples(audio_path)

    center_sample = int(time_seconds * sr)
    window_samples = int(window_ms * sr / 1000)

    start = max(0, center_sample - window_samples // 2)
    end = min(len(samples), center_sample + window_samples // 2)

    if start >= end:
        return 0.0

    frame = samples[start:end]
    return float(np.sqrt(np.mean(frame ** 2)))


if __name__ == "__main__":
    print("Waveform Analyzer - Test Mode")
    print("=" * 60)

    # Test with sample audio if available
    test_path = "data/audio"
    import glob
    wav_files = glob.glob(f"{test_path}/*.wav")

    if wav_files:
        audio_path = wav_files[0]
        print(f"Testing with: {audio_path}")

        samples, sr = get_audio_samples(audio_path)
        print(f"Loaded {len(samples)} samples at {sr}Hz")
        print(f"Duration: {len(samples)/sr:.1f}s")

        rms, time_step = compute_rms_envelope(samples, sr)
        print(f"Computed {len(rms)} RMS frames")

        silences = find_silence_points(rms, time_step)
        print(f"Found {len(silences)} silence regions")

        for s in silences[:5]:
            print(f"  {s['start']:.1f}s - {s['end']:.1f}s ({s['duration']:.2f}s)")

        # Test snapping
        test_start = 10.0
        test_end = 20.0
        snapped_start, snapped_end = snap_to_silence(test_start, test_end, audio_path)
        print(f"\nSnapping test:")
        print(f"  Original: {test_start}s - {test_end}s")
        print(f"  Snapped: {snapped_start:.2f}s - {snapped_end:.2f}s")
    else:
        print("No WAV files found in data/audio/")
