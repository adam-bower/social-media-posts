"""
AI-powered clip suggestion using Claude Haiku via OpenRouter.

Analyzes transcript and silence data to suggest optimal clips for
LinkedIn (professional, 30-120s) and TikTok (high-energy, 15-60s).

Usage:
    from src.video.clip_suggester import suggest_clips
    suggestions = suggest_clips(transcript, silences, duration)
"""

import os
import json
import re
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import requests

load_dotenv()


def get_openrouter_key() -> str:
    """Get OpenRouter API key from environment or Windmill."""
    key = os.getenv("OPENROUTER_API_KEY")
    if key:
        return key

    try:
        import wmill
        resource = wmill.get_resource("f/ai/openrouter")
        return resource.get("api_key") or resource.get("token")
    except Exception:
        raise ValueError("OPENROUTER_API_KEY not found in environment or Windmill")


def call_claude_haiku(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4096,
) -> str:
    """
    Call Claude Haiku via OpenRouter API.

    Args:
        system_prompt: System message for context
        user_prompt: User message with the request
        max_tokens: Maximum tokens in response

    Returns:
        Model response text
    """
    api_key = get_openrouter_key()

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "anthropic/claude-3-haiku",
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=60,
    )

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def build_system_prompt() -> str:
    """Build the system prompt for clip suggestion."""
    return """You are an expert video editor specializing in creating engaging social media clips from longer video content. Your focus is on civil engineering, construction, and professional business content.

Your task is to analyze video transcripts and suggest optimal clip boundaries for two platforms:

## LinkedIn Clips (Professional)
- Duration: 30-120 seconds (ideal: 45-90 seconds)
- Focus: Educational insights, industry expertise, professional tips
- Hook: Should open with a compelling statement or question
- Structure: Clear beginning, middle, end within the clip
- Avoid: Cut-off sentences, incomplete thoughts

## TikTok Clips (Engaging)
- Duration: 15-60 seconds (ideal: 20-45 seconds)
- Focus: High-energy moments, surprising facts, quick tips
- Hook: Must grab attention in first 3 seconds
- Structure: Punchy, fast-paced, one key takeaway
- Avoid: Slow buildup, complex explanations

## Selection Criteria
1. Strong opening hook (question, bold statement, surprising fact)
2. Self-contained topic (doesn't require outside context)
3. Clear value delivery (teaches something or entertains)
4. Natural ending (ends at a pause or conclusion, not mid-sentence)
5. Good audio quality (avoid segments with noted silence issues)

## Output Format
Return a JSON array of suggested clips. Each clip should have:
- start_time: Start timestamp in seconds
- end_time: End timestamp in seconds
- platform: "linkedin", "tiktok", or "both"
- hook_reason: Why this clip has a strong opening hook
- confidence_score: 0.0-1.0 confidence this will perform well
- transcript_excerpt: First 100 chars of the clip transcript

IMPORTANT: Return ONLY valid JSON, no markdown formatting or explanation."""


def build_user_prompt(
    transcript_text: str,
    segments: List[Dict],
    silences: List[Dict],
    duration: float,
    context: Optional[str] = None,
) -> str:
    """Build the user prompt with transcript and silence data."""
    # Format segments with timestamps
    formatted_segments = []
    for seg in segments[:100]:  # Limit to prevent token overflow
        formatted_segments.append(
            f"[{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text']}"
        )

    # Format silences
    formatted_silences = []
    for silence in silences:
        if silence['duration'] >= 1.0:  # Only show significant silences
            formatted_silences.append(
                f"[{silence['start']:.1f}s - {silence['end']:.1f}s] ({silence['duration']:.1f}s pause)"
            )

    prompt = f"""## Video Details
- Total Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)
- Number of speech segments: {len(segments)}
- Number of significant pauses: {len(formatted_silences)}

## Context
{context or "Professional video content, likely related to civil engineering, construction, or business."}

## Transcript with Timestamps
{chr(10).join(formatted_segments)}

## Natural Pauses (potential clip boundaries)
{chr(10).join(formatted_silences) if formatted_silences else "No significant pauses detected"}

## Instructions
Analyze this transcript and suggest 3-6 clips optimized for social media. For each clip:
1. Identify strong opening hooks
2. Find natural ending points (at pauses or thought completions)
3. Ensure clips are self-contained
4. Prioritize educational or engaging content

Return your suggestions as a JSON array."""

    return prompt


def parse_suggestions(response: str) -> List[Dict[str, Any]]:
    """Parse the JSON response from Claude."""
    # Try to extract JSON from the response
    # Sometimes the model wraps it in markdown code blocks
    json_match = re.search(r'\[[\s\S]*\]', response)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Try parsing the entire response
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        raise ValueError(f"Failed to parse clip suggestions from response: {response[:500]}")


def suggest_clips(
    transcript_text: str,
    segments: List[Dict],
    silences: List[Dict],
    duration: float,
    context: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Suggest clips from video transcript using Claude Haiku.

    Args:
        transcript_text: Full transcript text
        segments: List of transcript segments with timestamps
        silences: List of silence periods
        duration: Total video duration in seconds
        context: Optional context about the video content

    Returns:
        List of clip suggestions with timestamps and metadata
    """
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(
        transcript_text,
        segments,
        silences,
        duration,
        context,
    )

    response = call_claude_haiku(system_prompt, user_prompt)
    suggestions = parse_suggestions(response)

    # Validate and clean suggestions
    valid_suggestions = []
    for suggestion in suggestions:
        # Ensure required fields
        if not all(k in suggestion for k in ["start_time", "end_time", "platform"]):
            continue

        # Validate time range
        start = float(suggestion["start_time"])
        end = float(suggestion["end_time"])
        if start >= end or start < 0 or end > duration:
            continue

        # Normalize platform
        platform = suggestion.get("platform", "both").lower()
        if platform not in ["linkedin", "tiktok", "both"]:
            platform = "both"

        valid_suggestions.append({
            "start_time": start,
            "end_time": end,
            "duration": end - start,
            "platform": platform,
            "hook_reason": suggestion.get("hook_reason", ""),
            "confidence_score": min(1.0, max(0.0, float(suggestion.get("confidence_score", 0.7)))),
            "transcript_excerpt": suggestion.get("transcript_excerpt", "")[:200],
        })

    return valid_suggestions


def suggest_clips_with_duration_estimates(
    audio_path: str,
    segments: List[Dict],
    silences: List[Dict],
    duration: float,
    context: Optional[str] = None,
    preset: str = "linkedin",
) -> List[Dict[str, Any]]:
    """
    Suggest clips with accurate post-silence-removal duration estimates.

    This enhanced version:
    1. Gets clip suggestions from Claude Haiku
    2. For each suggestion, calculates the actual duration after silence removal
    3. Filters out clips that would be too short/long for their target platform

    Args:
        audio_path: Path to audio file (for VAD analysis)
        segments: List of transcript segments with timestamps
        silences: List of silence periods (from transcript)
        duration: Total video duration in seconds
        context: Optional context about the video content
        preset: Default preset for duration estimation

    Returns:
        List of clip suggestions with estimated_duration fields
    """
    from src.video.waveform_silence_remover import estimate_edited_duration

    # Get transcript text
    transcript_text = " ".join(seg.get("text", "") for seg in segments)

    # Get base suggestions
    suggestions = suggest_clips(transcript_text, segments, silences, duration, context)

    # Enhance with duration estimates
    enhanced = []
    for suggestion in suggestions:
        start = suggestion["start_time"]
        end = suggestion["end_time"]
        platform = suggestion["platform"]

        # Determine preset based on platform
        if platform == "tiktok":
            est_preset = "tiktok"
        elif platform == "linkedin":
            est_preset = "linkedin"
        else:
            est_preset = preset  # Use default for "both"

        # Get duration estimate
        estimate = estimate_edited_duration(audio_path, start, end, est_preset)

        suggestion["raw_duration"] = suggestion["duration"]
        suggestion["estimated_duration"] = estimate["estimated_duration"]
        suggestion["time_saved"] = estimate["time_saved"]
        suggestion["percent_reduction"] = estimate["percent_reduction"]

        # Platform-specific duration validation
        is_valid = True
        if platform == "tiktok":
            # TikTok: 15-180 seconds (relaxed from 60s since TikTok now supports longer)
            if estimate["estimated_duration"] < 15:
                is_valid = False
                suggestion["rejection_reason"] = "too short for TikTok"
        elif platform == "linkedin":
            # LinkedIn: 30-120 seconds
            if estimate["estimated_duration"] < 30:
                is_valid = False
                suggestion["rejection_reason"] = "too short for LinkedIn"
            elif estimate["estimated_duration"] > 120:
                suggestion["warning"] = "may be too long for LinkedIn engagement"

        if is_valid:
            enhanced.append(suggestion)

    return enhanced


def main(
    transcript_text: str,
    segments: List[Dict],
    silences: List[Dict],
    duration: float,
    context: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Windmill-compatible entry point for clip suggestion.

    Args:
        transcript_text: Full transcript
        segments: Transcript segments with timestamps
        silences: Silence periods
        duration: Video duration
        context: Optional content context

    Returns:
        Dictionary with suggestions and metadata
    """
    suggestions = suggest_clips(
        transcript_text,
        segments,
        silences,
        duration,
        context,
    )

    # Separate by platform
    linkedin_clips = [s for s in suggestions if s["platform"] in ["linkedin", "both"]]
    tiktok_clips = [s for s in suggestions if s["platform"] in ["tiktok", "both"]]

    return {
        "suggestions": suggestions,
        "linkedin_clips": linkedin_clips,
        "tiktok_clips": tiktok_clips,
        "total_count": len(suggestions),
    }


if __name__ == "__main__":
    # Test with sample data
    print("Clip Suggester - Test Mode")
    print("=" * 60)

    # Sample transcript for testing
    sample_segments = [
        {"start": 0.0, "end": 5.0, "text": "Welcome to today's video about civil engineering best practices."},
        {"start": 5.5, "end": 12.0, "text": "One of the biggest mistakes I see is not properly compacting the subgrade before laying your base material."},
        {"start": 13.0, "end": 20.0, "text": "This single oversight can lead to millions of dollars in repairs down the road."},
        {"start": 21.0, "end": 28.0, "text": "Let me show you the correct procedure that we use on every project."},
        {"start": 30.0, "end": 45.0, "text": "First, you need to test the moisture content of your soil. Too wet or too dry and your compaction won't hold."},
        {"start": 46.0, "end": 60.0, "text": "We use a nuclear density gauge to verify we're hitting 95 percent standard proctor density."},
    ]

    sample_silences = [
        {"start": 5.0, "end": 5.5, "duration": 0.5},
        {"start": 12.0, "end": 13.0, "duration": 1.0},
        {"start": 20.0, "end": 21.0, "duration": 1.0},
        {"start": 28.0, "end": 30.0, "duration": 2.0},
        {"start": 45.0, "end": 46.0, "duration": 1.0},
    ]

    sample_text = " ".join(seg["text"] for seg in sample_segments)

    print("Testing with sample civil engineering transcript...")
    print(f"Duration: 60s, Segments: {len(sample_segments)}")

    try:
        result = main(
            transcript_text=sample_text,
            segments=sample_segments,
            silences=sample_silences,
            duration=60.0,
            context="Civil engineering construction best practices video",
        )

        print(f"\nFound {result['total_count']} clip suggestions:")
        for i, clip in enumerate(result['suggestions']):
            print(f"\n{i+1}. [{clip['platform'].upper()}] {clip['start_time']:.1f}s - {clip['end_time']:.1f}s")
            print(f"   Duration: {clip['duration']:.1f}s")
            print(f"   Confidence: {clip['confidence_score']:.0%}")
            print(f"   Hook: {clip['hook_reason'][:80]}...")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
