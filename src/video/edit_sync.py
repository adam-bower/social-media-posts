"""
Audio-to-video edit synchronization.

Maps audio EditDecisions from waveform_silence_remover to video segments
for FFmpeg rendering. Handles frame boundary snapping and timing.

Usage:
    from src.video.edit_sync import audio_edits_to_video_segments

    video_segments = audio_edits_to_video_segments(
        edit_decisions=decisions,
        video_fps=30.0,
    )
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from math import floor, ceil


@dataclass
class VideoEditSegment:
    """
    A segment of video to include in the final render.

    Coordinates are in video time (before any edits).
    """
    start: float           # Start time in source video (seconds)
    end: float             # End time in source video (seconds)
    start_frame: int       # Start frame number
    end_frame: int         # End frame number (exclusive)
    action: str            # "keep" or "trim"
    reason: str            # Why this segment exists

    @property
    def duration(self) -> float:
        """Duration of this segment in seconds."""
        return self.end - self.start

    @property
    def frame_count(self) -> int:
        """Number of frames in this segment."""
        return self.end_frame - self.start_frame

    def to_ffmpeg_trim(self) -> str:
        """
        Generate FFmpeg trim filter for this segment.

        Returns: "trim=start:end,setpts=PTS-STARTPTS"
        """
        return f"trim={self.start:.6f}:{self.end:.6f},setpts=PTS-STARTPTS"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "start": round(self.start, 6),
            "end": round(self.end, 6),
            "duration": round(self.duration, 6),
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "frame_count": self.frame_count,
            "action": self.action,
            "reason": self.reason,
        }


@dataclass
class VideoEditPlan:
    """
    Complete plan for video editing.

    Contains all segments and metadata for rendering.
    """
    segments: List[VideoEditSegment]
    source_duration: float
    source_fps: float
    edited_duration: float

    @property
    def segment_count(self) -> int:
        """Number of segments."""
        return len(self.segments)

    @property
    def time_saved(self) -> float:
        """Time removed by edits."""
        return self.source_duration - self.edited_duration

    @property
    def reduction_percent(self) -> float:
        """Percentage of time removed."""
        if self.source_duration <= 0:
            return 0.0
        return (self.time_saved / self.source_duration) * 100

    def generate_ffmpeg_filter_complex(
        self,
        input_label: str = "0:v",
        output_label: str = "outv",
    ) -> str:
        """
        Generate FFmpeg filter_complex string for all segments.

        This creates a filter that:
        1. Splits the input video
        2. Trims each segment
        3. Concatenates all segments

        Args:
            input_label: Input stream label
            output_label: Output stream label

        Returns:
            FFmpeg filter_complex string
        """
        if not self.segments:
            return f"[{input_label}]null[{output_label}]"

        if len(self.segments) == 1:
            # Single segment - no need to split/concat
            seg = self.segments[0]
            return f"[{input_label}]{seg.to_ffmpeg_trim()}[{output_label}]"

        # Multiple segments - split, trim each, concat
        filters = []
        segment_labels = []

        # Split input into N streams
        split_outputs = "".join(f"[s{i}]" for i in range(len(self.segments)))
        filters.append(f"[{input_label}]split={len(self.segments)}{split_outputs}")

        # Trim each segment
        for i, seg in enumerate(self.segments):
            label = f"v{i}"
            filters.append(f"[s{i}]{seg.to_ffmpeg_trim()}[{label}]")
            segment_labels.append(f"[{label}]")

        # Concat all segments
        concat_inputs = "".join(segment_labels)
        filters.append(f"{concat_inputs}concat=n={len(self.segments)}:v=1:a=0[{output_label}]")

        return ";".join(filters)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "source_duration": round(self.source_duration, 3),
            "source_fps": self.source_fps,
            "edited_duration": round(self.edited_duration, 3),
            "time_saved": round(self.time_saved, 3),
            "reduction_percent": round(self.reduction_percent, 1),
            "segment_count": self.segment_count,
            "segments": [s.to_dict() for s in self.segments],
        }


def snap_to_frame(
    time_seconds: float,
    fps: float,
    direction: str = "nearest",
) -> Tuple[float, int]:
    """
    Snap a time to the nearest frame boundary.

    Args:
        time_seconds: Time in seconds
        fps: Video frame rate
        direction: "nearest", "floor", or "ceil"

    Returns:
        (snapped_time, frame_number)
    """
    frame_duration = 1.0 / fps

    if direction == "floor":
        frame_num = floor(time_seconds * fps)
    elif direction == "ceil":
        frame_num = ceil(time_seconds * fps)
    else:  # nearest
        frame_num = round(time_seconds * fps)

    snapped_time = frame_num / fps
    return (snapped_time, frame_num)


def audio_edits_to_video_segments(
    edit_decisions: List[Dict[str, Any]],
    video_fps: float = 30.0,
    video_duration: Optional[float] = None,
    snap_to_frames: bool = True,
) -> VideoEditPlan:
    """
    Convert audio EditDecisions to video segments.

    Takes the edit decisions from waveform_silence_remover and maps them
    to video time, snapping to frame boundaries.

    Args:
        edit_decisions: List of edit decision dicts from waveform_silence_remover
            Each dict has: start, end, action, reason
        video_fps: Video frame rate for frame snapping
        video_duration: Optional source video duration
        snap_to_frames: Whether to snap times to frame boundaries

    Returns:
        VideoEditPlan with video segments
    """
    # Filter to only keep/trim actions (exclude remove)
    keep_decisions = [
        d for d in edit_decisions
        if d.get("action") in ("keep", "trim")
    ]

    # Sort by start time
    keep_decisions.sort(key=lambda d: d.get("start", 0))

    segments = []
    edited_duration = 0.0

    for decision in keep_decisions:
        start = decision.get("start", 0)
        end = decision.get("end", 0)
        action = decision.get("action", "keep")
        reason = decision.get("reason", "")

        if snap_to_frames:
            # Snap start to nearest frame (prefer including more)
            snapped_start, start_frame = snap_to_frame(start, video_fps, "floor")
            # Snap end to nearest frame (prefer including more)
            snapped_end, end_frame = snap_to_frame(end, video_fps, "ceil")
        else:
            snapped_start = start
            snapped_end = end
            start_frame = int(start * video_fps)
            end_frame = int(end * video_fps)

        # Skip zero-duration segments
        if snapped_end <= snapped_start:
            continue

        segment = VideoEditSegment(
            start=snapped_start,
            end=snapped_end,
            start_frame=start_frame,
            end_frame=end_frame,
            action=action,
            reason=reason,
        )
        segments.append(segment)
        edited_duration += segment.duration

    # Merge overlapping/adjacent segments
    segments = _merge_adjacent_segments(segments, video_fps)

    # Recalculate edited duration after merge
    edited_duration = sum(s.duration for s in segments)

    # Determine source duration
    if video_duration is None and segments:
        # Use the last segment's end time
        video_duration = max(s.end for s in segments)
    elif video_duration is None:
        video_duration = 0.0

    return VideoEditPlan(
        segments=segments,
        source_duration=video_duration,
        source_fps=video_fps,
        edited_duration=edited_duration,
    )


def _merge_adjacent_segments(
    segments: List[VideoEditSegment],
    fps: float,
    max_gap_frames: int = 2,
) -> List[VideoEditSegment]:
    """
    Merge segments that are adjacent or slightly overlapping.

    Args:
        segments: List of VideoEditSegment
        fps: Video frame rate
        max_gap_frames: Maximum gap (in frames) to merge

    Returns:
        Merged list of segments
    """
    if not segments:
        return []

    max_gap = max_gap_frames / fps
    merged = []
    current = segments[0]

    for next_seg in segments[1:]:
        # Check if segments should be merged
        gap = next_seg.start - current.end

        if gap <= max_gap:
            # Merge: extend current to include next
            current = VideoEditSegment(
                start=current.start,
                end=max(current.end, next_seg.end),
                start_frame=current.start_frame,
                end_frame=max(current.end_frame, next_seg.end_frame),
                action="keep",
                reason=f"merged: {current.reason} + {next_seg.reason}",
            )
        else:
            # No merge: save current and start new
            merged.append(current)
            current = next_seg

    merged.append(current)
    return merged


def create_edit_plan_from_silence_result(
    silence_result: Dict[str, Any],
    video_fps: float = 30.0,
) -> VideoEditPlan:
    """
    Create a VideoEditPlan from waveform_silence_remover result.

    Args:
        silence_result: Result dict from process_clip_waveform_only()
        video_fps: Video frame rate

    Returns:
        VideoEditPlan ready for video rendering
    """
    decisions = silence_result.get("decisions", [])
    duration = silence_result.get("original_duration", 0)

    return audio_edits_to_video_segments(
        edit_decisions=decisions,
        video_fps=video_fps,
        video_duration=duration,
    )


def apply_clip_range(
    edit_plan: VideoEditPlan,
    clip_start: float,
    clip_end: float,
) -> VideoEditPlan:
    """
    Apply a clip range to an edit plan.

    Adjusts all segment times relative to clip_start and filters
    segments to only include those within the range.

    Args:
        edit_plan: Original edit plan
        clip_start: Start of clip in source video
        clip_end: End of clip in source video

    Returns:
        New VideoEditPlan with adjusted segments
    """
    new_segments = []
    clip_duration = clip_end - clip_start

    for seg in edit_plan.segments:
        # Skip segments entirely outside clip range
        if seg.end <= clip_start or seg.start >= clip_end:
            continue

        # Clamp segment to clip range
        new_start = max(seg.start, clip_start) - clip_start  # Relative to clip start
        new_end = min(seg.end, clip_end) - clip_start

        if new_end > new_start:
            new_segments.append(VideoEditSegment(
                start=new_start,
                end=new_end,
                start_frame=int(new_start * edit_plan.source_fps),
                end_frame=int(new_end * edit_plan.source_fps),
                action=seg.action,
                reason=seg.reason,
            ))

    edited_duration = sum(s.duration for s in new_segments)

    return VideoEditPlan(
        segments=new_segments,
        source_duration=clip_duration,
        source_fps=edit_plan.source_fps,
        edited_duration=edited_duration,
    )


if __name__ == "__main__":
    print("Edit Sync - Test Mode")
    print("=" * 60)

    # Simulate edit decisions from waveform_silence_remover
    test_decisions = [
        {"start": 0.0, "end": 2.5, "action": "keep", "reason": "speech"},
        {"start": 2.5, "end": 3.0, "action": "trim", "reason": "silence trimmed"},
        {"start": 3.0, "end": 5.5, "action": "keep", "reason": "speech"},
        {"start": 5.5, "end": 7.0, "action": "remove", "reason": "long silence"},
        {"start": 7.0, "end": 10.0, "action": "keep", "reason": "speech"},
    ]

    print("\nInput edit decisions:")
    for d in test_decisions:
        print(f"  {d['start']:.1f}s - {d['end']:.1f}s: {d['action']} ({d['reason']})")

    # Convert to video segments
    plan = audio_edits_to_video_segments(
        edit_decisions=test_decisions,
        video_fps=30.0,
        video_duration=12.0,
    )

    print(f"\nVideo Edit Plan:")
    print(f"  Source duration: {plan.source_duration:.1f}s")
    print(f"  Edited duration: {plan.edited_duration:.1f}s")
    print(f"  Time saved: {plan.time_saved:.1f}s ({plan.reduction_percent:.1f}%)")
    print(f"  Segments: {plan.segment_count}")

    print(f"\nVideo segments:")
    for seg in plan.segments:
        print(f"  {seg.start:.3f}s - {seg.end:.3f}s ({seg.frame_count} frames)")
        print(f"    FFmpeg: {seg.to_ffmpeg_trim()}")

    print(f"\nFFmpeg filter_complex:")
    print(f"  {plan.generate_ffmpeg_filter_complex()}")

    # Test clip range
    print("\n" + "=" * 60)
    print("Testing clip range (3s - 9s):")
    clipped = apply_clip_range(plan, 3.0, 9.0)
    print(f"  Clip duration: {clipped.source_duration:.1f}s")
    print(f"  Edited duration: {clipped.edited_duration:.1f}s")
    print(f"  Segments: {clipped.segment_count}")
    for seg in clipped.segments:
        print(f"    {seg.start:.3f}s - {seg.end:.3f}s: {seg.reason}")
