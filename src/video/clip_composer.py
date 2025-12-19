"""
AI-powered clip composer using Claude Sonnet.

Instead of just suggesting linear segments, this uses AI to:
1. Analyze the full transcript for key insights
2. Identify the best segments (even non-adjacent ones)
3. Compose clips by combining segments from different parts
4. Ensure narrative flow when stitching segments together

Usage:
    from src.video.clip_composer import compose_clips
    composed = compose_clips(transcript_segments, platform='tiktok')
"""

import os
import json
import re
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import requests

load_dotenv()


def get_anthropic_key() -> str:
    """Get Anthropic API key from environment or Windmill."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if key:
        return key

    try:
        import wmill
        return wmill.get_variable("f/ai/anthropic_api_key")
    except Exception:
        raise ValueError("ANTHROPIC_API_KEY not found")


def call_sonnet(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4096,
) -> str:
    """
    Call Claude Sonnet 4 directly via Anthropic API.

    Using Sonnet for cost efficiency - low input tokens for transcript analysis.
    """
    api_key = get_anthropic_key()

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=120,
    )

    response.raise_for_status()
    return response.json()["content"][0]["text"]


def build_system_prompt(platform: str) -> str:
    """Build system prompt for clip composition."""

    platform_guidance = {
        "tiktok": """
TARGET: TikTok / YouTube Shorts (15-60 seconds)
- High energy, punchy delivery
- Hook MUST grab attention in first 2-3 seconds
- One clear takeaway per clip
- Can use jump cuts between non-adjacent segments
- Controversy or surprising statements work well
- End with impact or cliffhanger""",

        "linkedin": """
TARGET: LinkedIn (30-90 seconds)
- Professional, insightful tone
- Hook should pose a problem or insight
- Build to a clear professional takeaway
- Smoother transitions preferred
- Educational value is key
- End with actionable insight""",

        "youtube_shorts": """
TARGET: YouTube Shorts (15-60 seconds)
- Similar to TikTok but slightly more polished
- Strong hook essential
- Fast pacing, minimal dead air
- Can combine multiple related points
- End memorably""",
    }

    guidance = platform_guidance.get(platform, platform_guidance["linkedin"])

    return f"""You are an expert video editor specializing in creating viral social media clips from longer video content.

Your task is to COMPOSE clips by selecting and combining the best segments from a transcript. You can:
1. Select non-adjacent segments and combine them
2. Reorder content for better narrative flow
3. Cut out tangents and keep only the strongest points
4. Create multiple variations from the same source material

{guidance}

RULES FOR COMPOSITION:
1. Each segment you select must make sense when combined with others
2. Transitions should feel natural (avoid cutting mid-thought)
3. Prefer complete sentences/thoughts
4. The combined clip must tell a coherent mini-story or make a clear point
5. Timestamps must be exact - use the provided word-level timestamps

OUTPUT FORMAT:
Return a JSON array of composed clips. Each clip has:
- "title": Short title for the clip (5-10 words)
- "hook": Why this will grab attention (1 sentence)
- "segments": Array of segments to combine, in order:
  - "start_time": Start timestamp in seconds
  - "end_time": End timestamp in seconds
  - "text": The transcript text for this segment
- "platform": Target platform
- "estimated_duration": Total duration after combining segments
- "composition_notes": Brief explanation of why these segments work together

IMPORTANT: Return ONLY valid JSON, no markdown or explanation."""


def build_user_prompt(
    segments: List[Dict],
    duration: float,
    context: Optional[str] = None,
    num_clips: int = 3,
) -> str:
    """Build user prompt with transcript data."""

    # Format segments with timestamps
    formatted = []
    for seg in segments:
        words = seg.get('words', [])
        if words:
            # Include word-level timestamps for precision
            word_times = []
            for w in words[:20]:  # Limit words shown per segment
                word_times.append(f"{w.get('word', '')}[{w.get('start', 0):.1f}s]")
            word_str = " ".join(word_times)
            if len(words) > 20:
                word_str += "..."
        else:
            word_str = ""

        formatted.append(
            f"[{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text']}\n"
            f"  Words: {word_str}"
        )

    return f"""## Video Information
- Total Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)
- Total Segments: {len(segments)}
- Context: {context or "Professional/educational content"}

## Full Transcript with Timestamps

{chr(10).join(formatted)}

## Task
Compose {num_clips} clips for social media. You can:
1. Combine non-adjacent segments if they create a better narrative
2. Skip tangents or weaker content
3. Reorder for impact (but note: audio must still make sense when combined)

For each clip, select the exact segments (using timestamps) that should be combined.
Return as JSON array."""


def parse_composed_clips(response: str) -> List[Dict[str, Any]]:
    """Parse the JSON response from Sonnet."""
    # Try to extract JSON from response
    json_match = re.search(r'\[[\s\S]*\]', response)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Try parsing entire response
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        raise ValueError(f"Failed to parse composed clips: {response[:500]}")


def compose_clips(
    segments: List[Dict],
    duration: float,
    platform: str = "linkedin",
    context: Optional[str] = None,
    num_clips: int = 3,
) -> List[Dict[str, Any]]:
    """
    Use Claude Sonnet to compose intelligent clips from transcript.

    Args:
        segments: Transcript segments with word-level timestamps
        duration: Total video duration
        platform: Target platform (tiktok, linkedin, youtube_shorts)
        context: Optional context about the content
        num_clips: Number of clips to generate

    Returns:
        List of composed clips with segments to combine
    """
    system_prompt = build_system_prompt(platform)
    user_prompt = build_user_prompt(segments, duration, context, num_clips)

    response = call_sonnet(system_prompt, user_prompt)
    clips = parse_composed_clips(response)

    # Validate and enhance clips
    valid_clips = []
    for clip in clips:
        if not clip.get("segments"):
            continue

        # Validate timestamps
        total_duration = 0
        valid_segments = []
        for seg in clip["segments"]:
            start = float(seg.get("start_time", 0))
            end = float(seg.get("end_time", start))
            if start < end and start >= 0 and end <= duration:
                valid_segments.append({
                    "start_time": start,
                    "end_time": end,
                    "text": seg.get("text", ""),
                })
                total_duration += (end - start)

        if valid_segments:
            clip["segments"] = valid_segments
            clip["estimated_duration"] = total_duration
            clip["is_composed"] = len(valid_segments) > 1  # Multiple segments combined
            valid_clips.append(clip)

    return valid_clips


def compose_clips_with_duration_estimates(
    audio_path: str,
    segments: List[Dict],
    duration: float,
    platform: str = "linkedin",
    context: Optional[str] = None,
    num_clips: int = 3,
) -> List[Dict[str, Any]]:
    """
    Compose clips with accurate post-silence-removal duration estimates.

    This enhanced version estimates the actual duration after silence removal
    for each segment in a composed clip.

    Args:
        audio_path: Path to audio file (for VAD analysis)
        segments: Transcript segments with word-level timestamps
        duration: Total video duration
        platform: Target platform
        context: Optional context
        num_clips: Number of clips to generate

    Returns:
        List of composed clips with estimated_duration after silence removal
    """
    from src.video.waveform_silence_remover import estimate_edited_duration

    # Get base composed clips
    clips = compose_clips(segments, duration, platform, context, num_clips)

    # Enhance with accurate duration estimates
    for clip in clips:
        if not clip.get("segments"):
            continue

        # Map platform to preset
        preset_map = {
            "tiktok": "tiktok",
            "linkedin": "linkedin",
            "youtube_shorts": "youtube_shorts",
        }
        preset = preset_map.get(platform, "linkedin")

        # Calculate estimated duration for each segment
        total_estimated = 0.0
        for seg in clip["segments"]:
            start = seg["start_time"]
            end = seg["end_time"]
            estimate = estimate_edited_duration(audio_path, start, end, preset)
            seg["estimated_duration"] = estimate["estimated_duration"]
            total_estimated += estimate["estimated_duration"]

        clip["raw_duration"] = clip["estimated_duration"]  # This was the sum of raw segments
        clip["estimated_duration"] = round(total_estimated, 2)
        clip["percent_reduction"] = round(
            (clip["raw_duration"] - total_estimated) / clip["raw_duration"] * 100
            if clip["raw_duration"] > 0 else 0,
            1
        )

    return clips


def compose_clips_for_all_platforms(
    segments: List[Dict],
    duration: float,
    context: Optional[str] = None,
) -> Dict[str, List[Dict]]:
    """
    Generate composed clips for all platforms.

    Returns dict keyed by platform.
    """
    results = {}

    for platform in ["tiktok", "linkedin"]:
        try:
            clips = compose_clips(
                segments,
                duration,
                platform=platform,
                context=context,
                num_clips=2,  # 2 per platform
            )
            results[platform] = clips
        except Exception as e:
            print(f"Error composing clips for {platform}: {e}")
            results[platform] = []

    return results


if __name__ == "__main__":
    print("Clip Composer - Test Mode")
    print("=" * 60)

    # Test with sample transcript
    sample_segments = [
        {
            "start": 0.0, "end": 8.0,
            "text": "The construction industry has a massive problem with change orders.",
            "words": [
                {"word": "The", "start": 0.0, "end": 0.2},
                {"word": "construction", "start": 0.3, "end": 0.8},
                {"word": "industry", "start": 0.9, "end": 1.3},
                {"word": "has", "start": 1.4, "end": 1.5},
                {"word": "a", "start": 1.6, "end": 1.7},
                {"word": "massive", "start": 1.8, "end": 2.2},
                {"word": "problem", "start": 2.3, "end": 2.7},
            ],
        },
        {
            "start": 10.0, "end": 20.0,
            "text": "I've seen projects go 50% over budget just from earthwork discrepancies.",
            "words": [
                {"word": "I've", "start": 10.0, "end": 10.2},
                {"word": "seen", "start": 10.3, "end": 10.5},
                {"word": "projects", "start": 10.6, "end": 11.0},
            ],
        },
        {
            "start": 25.0, "end": 35.0,
            "text": "But here's the thing nobody talks about - the engineer often has incomplete data.",
            "words": [
                {"word": "But", "start": 25.0, "end": 25.2},
                {"word": "here's", "start": 25.3, "end": 25.6},
            ],
        },
        {
            "start": 40.0, "end": 55.0,
            "text": "When I started using drone surveys, everything changed. We caught issues before they became expensive.",
            "words": [
                {"word": "When", "start": 40.0, "end": 40.2},
                {"word": "I", "start": 40.3, "end": 40.4},
            ],
        },
    ]

    print("Testing with sample civil engineering transcript...")
    print(f"Duration: 60s, Segments: {len(sample_segments)}")

    try:
        clips = compose_clips(
            sample_segments,
            duration=60.0,
            platform="tiktok",
            context="Civil engineering construction best practices",
            num_clips=2,
        )

        print(f"\nComposed {len(clips)} clips:")
        for i, clip in enumerate(clips):
            print(f"\n{i+1}. {clip.get('title', 'Untitled')}")
            print(f"   Hook: {clip.get('hook', 'N/A')}")
            print(f"   Duration: {clip.get('estimated_duration', 0):.1f}s")
            print(f"   Segments: {len(clip.get('segments', []))}")
            print(f"   Composed from multiple parts: {clip.get('is_composed', False)}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
