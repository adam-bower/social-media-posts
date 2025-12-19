"""
AI-powered clip composer with AB Civil context.

Uses Claude Sonnet with:
1. Your actual LinkedIn posts as examples
2. Deep understanding of AB Civil's voice and topics
3. Knowledge of what content performs well
4. Industry-specific terminology and insights

This is the upgrade from generic clip extraction to AB Civil-aware extraction.
"""

import os
import json
import re
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import requests

load_dotenv()




def get_supabase_client():
    """Get Supabase client for fetching LinkedIn posts."""
    from supabase import create_client
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def fetch_high_performing_posts(limit: int = 15) -> List[Dict]:
    """Fetch top-performing LinkedIn posts for context."""
    client = get_supabase_client()
    if not client:
        return []

    try:
        # Get posts with 20+ likes, sorted by engagement
        result = client.table("linkedin_posts").select(
            "content, likes, comments, estimated_date"
        ).gte("likes", 20).order("likes", desc=True).limit(limit).execute()
        return result.data or []
    except Exception as e:
        print(f"Error fetching LinkedIn posts: {e}")
        return []


def fetch_posts_by_topic(topics: List[str], limit: int = 5) -> List[Dict]:
    """Fetch posts matching specific topics."""
    client = get_supabase_client()
    if not client:
        return []

    # Search for posts containing topic keywords
    all_posts = []
    try:
        for topic in topics[:3]:  # Limit topic searches
            result = client.table("linkedin_posts").select(
                "content, likes, comments"
            ).ilike("content", f"%{topic}%").order("likes", desc=True).limit(limit).execute()
            all_posts.extend(result.data or [])
    except Exception:
        pass

    # Deduplicate by content
    seen = set()
    unique = []
    for post in all_posts:
        content_key = post["content"][:100]
        if content_key not in seen:
            seen.add(content_key)
            unique.append(post)

    return unique[:limit]


def get_openrouter_key() -> str:
    """Get OpenRouter API key."""
    key = os.getenv("OPENROUTER_API_KEY")
    if key:
        return key
    try:
        import wmill
        resource = wmill.get_resource("f/ai/openrouter")
        return resource.get("api_key") or resource.get("token")
    except Exception:
        raise ValueError("OPENROUTER_API_KEY not found")


def call_sonnet(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4096,
) -> str:
    """Call Claude Sonnet 4.5 via OpenRouter API."""
    api_key = get_openrouter_key()

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "anthropic/claude-sonnet-4.5",
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=120,
    )

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


AB_CIVIL_CONTEXT = """
## About AB Civil Consulting

AB Civil is a 3D machine control modeling company for excavation contractors. They convert 2D construction plans into 3D digital terrain models for GPS-guided equipment (bulldozers, excavators, graders).

### What makes AB Civil different:
1. **Responsiveness** - Fast communication, quick turnaround. Multiple people available at all times.
2. **Quality** - Double-check process ensures accuracy. They catch plan errors before they become field problems.
3. **Full support** - Remote support for equipment issues, file uploads, troubleshooting.
4. **Guarantee** - Fix issues fast, no extra charge.

### Tone & Voice:
- Direct, practical, no-BS
- Sharing real experiences and lessons learned
- Educational but conversational
- Sometimes critical of industry problems
- Willing to be vulnerable (sharing mistakes, challenges)
- Passionate about helping contractors succeed

### Topics that resonate with their audience:
- Construction technology and innovation
- Team management and communication
- Responsiveness and customer service
- Skills gap in construction industry
- Mental health in construction
- Training and professional development
- Business operations and systems
- Real stories from the field
"""


def build_system_prompt_v2(
    platform: str,
    high_performing_posts: List[Dict],
) -> str:
    """Build system prompt with AB Civil context and example posts."""

    platform_guidance = {
        "tiktok": """
TARGET: TikTok / YouTube Shorts (15-60 seconds)
- High energy, punchy delivery
- Hook MUST grab attention in first 2-3 seconds
- One clear takeaway per clip
- Can use jump cuts between non-adjacent segments
- Controversy or surprising statements work well
- End with impact or cliffhanger
- Quick cuts are fine - attention span is short""",

        "linkedin": """
TARGET: LinkedIn (90-180 seconds MINIMUM, can go to 3 min)
- Professional but authentic - Adam's real voice
- Hook should pose a problem, share a lesson, or make a bold statement
- Build to a clear professional takeaway
- Educational value is key
- Stories and real experiences perform best
- End with actionable insight or thought-provoking question

CRITICAL: LinkedIn audience WATCHES longer videos. They've given feedback they watch full videos.
- MOST clips should be 90-180 seconds (1.5 to 3 minutes)
- A few punchy 30-60 second clips are OK if the content is self-contained and powerful
- MAXIMUM 4 minutes - beyond this, split into separate clips
- Let stories and explanations breathe - don't rush to cut
- A 3-minute clip with full context beats chopping it into fragments
- If a topic takes 2-3 minutes to explain properly, INCLUDE ALL OF IT
- But if it takes 5+ minutes, find a natural break point and make two clips

BALANCE: Out of 5 clips, aim for ~3-4 longer ones (90-180s) and ~1-2 shorter punchy ones (30-60s)""",

        "youtube_shorts": """
TARGET: YouTube Shorts (15-60 seconds)
- Similar to TikTok but slightly more polished
- Strong hook essential
- Fast pacing, minimal dead air
- Can combine multiple related points
- End memorably""",
    }

    guidance = platform_guidance.get(platform, platform_guidance["linkedin"])

    # Format example posts
    examples_text = ""
    if high_performing_posts:
        examples_text = "\n\n## EXAMPLES OF HIGH-PERFORMING AB CIVIL CONTENT\n\nThese posts performed well on LinkedIn. Use them to understand the voice, topics, and style that resonates:\n\n"
        for i, post in enumerate(high_performing_posts[:8], 1):
            content = post.get("content", "")[:600]
            likes = post.get("likes", 0)
            comments = post.get("comments", 0)
            examples_text += f"### Example {i} ({likes} likes, {comments} comments)\n{content}\n\n"

    return f"""You are helping Adam Bower from AB Civil Consulting extract the best clips from his video content for social media.

{AB_CIVIL_CONTEXT}

{examples_text}

{guidance}

## YOUR TASK

Analyze the transcript and identify clip-worthy segments. Look for:

1. **Strong hooks** - Bold statements, surprising facts, problems posed
   - "The construction industry has a massive problem with..."
   - "One of the biggest frustrations we hear..."
   - "Here's what nobody talks about..."
   - "That's completely irresponsible..."
   - "It kills me when I see..."

2. **Controversial or bold claims** - Statements that will make people stop scrolling
   - Criticizing common industry practices
   - Calling something "the worst" or "completely wrong"
   - Going against conventional wisdom
   - Specific numbers that shock (costs, percentages, years)

3. **Real stories and experiences** - Not generic advice, actual situations
   - Projects where things went wrong or right
   - Lessons learned from specific experiences
   - Client interactions that illustrate a point
   - "We had one job where..." or "I saw this happen..."

4. **Problem → Solution arcs** - Clear value delivery
   - Identifies a specific pain point
   - Provides actionable insight or solution
   - Shows concrete results or benefits

5. **Emotional moments** - Passion, frustration, excitement
   - Strong opinions on industry problems
   - Excitement about solutions
   - Frustration with how things are done

## CLIP SELECTION RULES

1. NEVER cut mid-sentence or mid-thought - wait for natural pauses
2. START clips at the beginning of a strong statement, not mid-context
3. END clips with impact - a conclusion, punchline, or powerful statement
4. Each clip must be self-contained (listener shouldn't feel they missed something)
5. For multi-segment clips: segments must flow naturally when combined
   - Don't combine segments that reference different topics
   - Jump cuts are OK if the topic continues
6. Better to have 2 great clips than 5 mediocre ones
7. If nothing clip-worthy exists, return empty array - don't force it

## FALSE START DETECTION - CRITICAL

Watch for these patterns and SKIP the first instance, START from the retry:

1. **Repeated phrases with gaps** - Speaker says something, pauses 2-5 seconds, then says the SAME thing again
   - Example: "if we can't get jobs out on time... [pause] ...if we can't get jobs out on time"
   - START the clip from the SECOND instance (the confident delivery)

2. **Self-corrections** - "I mean", "what I'm trying to say is", "let me rephrase"
   - Skip to the corrected version

3. **Abandoned sentences** - Speaker starts a thought, trails off, starts fresh
   - Look for incomplete sentences followed by a new start

4. **Filler-heavy openings** - "So, um, uh, like, you know..."
   - Skip past the filler to where the real content begins

5. **Warm-up statements** - "Okay so", "Alright so", "So basically"
   - These are fine mid-clip but weak as openers - find a stronger start

When you see these patterns, adjust your start_time to AFTER the false start.
The goal is clips that sound confident and polished from the first word.

## SEGMENT COMBINATION GUIDELINES

When combining non-adjacent segments:
- Ensure the second segment doesn't start with "so" or "and" that references skipped content
- Both segments should be about the same core topic
- The transition should feel intentional, not jarring
- Skip filler content between strong points - that's good editing

## OUTPUT FORMAT

Return a JSON array of clips. Each clip has:
- "title": Descriptive title (what's this clip about)
- "hook": Why this opening will grab attention
- "segments": Array of segments to include:
  - "start_time": Start timestamp in seconds
  - "end_time": End timestamp in seconds
  - "text": The transcript text
- "platform": Target platform
- "estimated_duration": Total seconds
- "why_it_works": Brief explanation of why this clip will perform well
- "confidence": 0.0-1.0 (be honest - only high confidence for genuinely good clips)

IMPORTANT: Return ONLY valid JSON, no markdown or explanation.
If the content isn't suitable for clips, return an empty array []."""


def build_user_prompt_v2(
    segments: List[Dict],
    duration: float,
    context: Optional[str] = None,
    num_clips: int = 3,
) -> str:
    """Build user prompt with detailed transcript."""

    # Format segments with word-level detail
    formatted = []
    for seg in segments:
        text = seg.get('text', '').strip()
        if not text:
            continue

        start = seg.get('start', 0)
        end = seg.get('end', 0)

        # Include word timing hints for precision
        words = seg.get('words', [])
        word_sample = ""
        if words:
            # Show first and last few words with times
            if len(words) > 6:
                first_words = [f"{w.get('word', '')}[{w.get('start', 0):.1f}]" for w in words[:3]]
                last_words = [f"{w.get('word', '')}[{w.get('end', 0):.1f}]" for w in words[-2:]]
                word_sample = f"\n    Start: {' '.join(first_words)} ... End: {' '.join(last_words)}"

        formatted.append(f"[{start:.1f}s - {end:.1f}s] {text}{word_sample}")

    transcript_text = "\n".join(formatted)

    return f"""## VIDEO TRANSCRIPT

Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)
Segments: {len(segments)}
Context: {context or "AB Civil video content - professional/educational"}

## FULL TRANSCRIPT WITH TIMESTAMPS

{transcript_text}

## TASK

Find the best {num_clips} clips from this content. Remember:
- Quality over quantity - if there aren't {num_clips} good clips, return fewer
- Look for segments that match the AB Civil voice and topics
- Find strong hooks and satisfying endings
- Be honest about confidence levels

FOR LINKEDIN:
- MOST clips: 90-180 seconds (1.5-3 min) - complete stories/lessons
- SOME clips: 30-60 seconds OK if punchy and self-contained
- MAX: 4 minutes (split longer topics)
Aim for a MIX: ~3-4 longer clips + ~1-2 shorter punchy ones.
Adam's audience watches full videos, but a great 30-second clip still works.

Return as JSON array."""


def parse_composed_clips(response: str) -> List[Dict[str, Any]]:
    """Parse the JSON response from Sonnet."""
    json_match = re.search(r'\[[\s\S]*\]', response)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        # Return empty if can't parse
        return []


def compose_clips_v2(
    segments: List[Dict],
    duration: float,
    platform: str = "linkedin",
    context: Optional[str] = None,
    num_clips: int = 3,
    audio_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Compose clips using AB Civil context and example posts.

    This is the upgraded version that understands AB Civil's voice
    and uses waveform analysis to snap boundaries to silence.

    Args:
        segments: Transcript segments with timestamps
        duration: Total video duration
        platform: Target platform
        context: Optional context about content
        num_clips: Number of clips to generate
        audio_path: Path to audio file for waveform analysis
    """
    # Fetch high-performing posts for examples
    high_performing = fetch_high_performing_posts(limit=10)

    # Build prompts with full context
    system_prompt = build_system_prompt_v2(platform, high_performing)
    user_prompt = build_user_prompt_v2(segments, duration, context, num_clips)

    # Call Sonnet
    response = call_sonnet(system_prompt, user_prompt)
    clips = parse_composed_clips(response)

    # Validate clips
    valid_clips = []
    for clip in clips:
        if not clip.get("segments"):
            continue

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
            clip["is_composed"] = len(valid_segments) > 1
            valid_clips.append(clip)

    # If audio path provided, snap boundaries to silence using waveform
    if audio_path and valid_clips:
        try:
            from src.video.waveform_analyzer import analyze_clip_boundaries
            for clip in valid_clips:
                adjusted = analyze_clip_boundaries(
                    clip["segments"],
                    audio_path,
                    search_window=0.5  # Search 500ms for silence
                )
                clip["segments"] = adjusted

                # Recalculate duration
                clip["estimated_duration"] = sum(
                    s["end_time"] - s["start_time"]
                    for s in adjusted
                )
                clip["waveform_snapped"] = True
        except Exception as e:
            # If waveform analysis fails, continue with original timestamps
            print(f"Waveform analysis failed: {e}")

    return valid_clips


# Keep old function name for compatibility but use new implementation
def compose_clips(
    segments: List[Dict],
    duration: float,
    platform: str = "linkedin",
    context: Optional[str] = None,
    num_clips: int = 3,
    audio_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Main entry point - uses the v2 implementation with AB Civil context."""
    return compose_clips_v2(segments, duration, platform, context, num_clips, audio_path)


if __name__ == "__main__":
    print("Clip Composer V2 - AB Civil Context")
    print("=" * 60)

    # Test fetching posts
    posts = fetch_high_performing_posts(5)
    print(f"Fetched {len(posts)} high-performing posts for context")

    if posts:
        print("\nTop post preview:")
        print(f"  Likes: {posts[0].get('likes', 0)}")
        print(f"  Content: {posts[0].get('content', '')[:100]}...")
