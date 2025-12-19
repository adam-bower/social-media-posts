"""
ASS subtitle generator for video captions with karaoke effect.

Generates Advanced SubStation Alpha (ASS) subtitles from word-level
timestamps, with word highlighting (karaoke) effect.

Usage:
    from src.video.caption_generator import generate_captions

    ass_content = generate_captions(
        words=transcript_words,
        style=get_caption_style(ExportFormat.TIKTOK),
        format_spec=get_format(ExportFormat.TIKTOK),
    )
"""

import os
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from datetime import timedelta

from src.video.export_formats import ExportFormat, FormatSpec, get_format
from src.video.caption_styles import (
    CaptionStyle,
    get_caption_style,
    HighlightStyle,
)


@dataclass
class Word:
    """A single word with timing information."""
    text: str
    start: float  # Start time in seconds
    end: float    # End time in seconds

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def duration_cs(self) -> int:
        """Duration in centiseconds (for ASS \k tag)."""
        return int(self.duration * 100)


@dataclass
class CaptionChunk:
    """A group of words displayed together."""
    words: List[Word]
    start: float
    end: float

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def duration(self) -> float:
        return self.end - self.start


def format_time(seconds: float) -> str:
    """
    Format time for ASS subtitle format.

    Format: h:mm:ss.cc (centiseconds)
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60

    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def words_to_chunks(
    words: List[Word],
    max_words: int = 5,
    max_duration: float = 3.0,
    min_gap: float = 0.3,
) -> List[CaptionChunk]:
    """
    Group words into caption chunks.

    Args:
        words: List of Word objects with timing
        max_words: Maximum words per chunk
        max_duration: Maximum duration per chunk
        min_gap: Minimum gap between words to force new chunk

    Returns:
        List of CaptionChunk objects
    """
    if not words:
        return []

    chunks = []
    current_words = []

    for word in words:
        # Check if we should start a new chunk
        should_break = False

        if current_words:
            # Check word count
            if len(current_words) >= max_words:
                should_break = True
            # Check duration
            elif word.end - current_words[0].start > max_duration:
                should_break = True
            # Check gap from previous word
            elif word.start - current_words[-1].end > min_gap:
                should_break = True

        if should_break and current_words:
            # Save current chunk
            chunks.append(CaptionChunk(
                words=current_words,
                start=current_words[0].start,
                end=current_words[-1].end,
            ))
            current_words = []

        current_words.append(word)

    # Don't forget the last chunk
    if current_words:
        chunks.append(CaptionChunk(
            words=current_words,
            start=current_words[0].start,
            end=current_words[-1].end,
        ))

    return chunks


def generate_karaoke_text(
    chunk: CaptionChunk,
    style: CaptionStyle,
) -> str:
    """
    Generate ASS text with karaoke effect.

    Uses \k tags to highlight words as they're spoken.
    The \k tag specifies duration in centiseconds before
    the word changes to the secondary color.

    Args:
        chunk: CaptionChunk with words
        style: CaptionStyle for formatting

    Returns:
        ASS-formatted text with karaoke tags
    """
    if style.highlight_style == HighlightStyle.NONE:
        # No karaoke effect, just plain text
        return chunk.text

    parts = []

    for i, word in enumerate(chunk.words):
        # Calculate duration for this word in centiseconds
        duration_cs = word.duration_cs

        if style.highlight_style == HighlightStyle.COLOR_CHANGE:
            # \kf (fill from left) gives smoother effect than \k
            parts.append(f"{{\\kf{duration_cs}}}{word.text}")
        elif style.highlight_style == HighlightStyle.BACKGROUND:
            # Add background box for current word
            parts.append(f"{{\\k{duration_cs}\\bord4}}{word.text}")
        elif style.highlight_style == HighlightStyle.SCALE:
            # Scale up current word
            parts.append(f"{{\\k{duration_cs}\\fscx120\\fscy120}}{word.text}")
        elif style.highlight_style == HighlightStyle.GLOW:
            # Add blur/glow effect
            parts.append(f"{{\\k{duration_cs}\\blur3}}{word.text}")

    return " ".join(parts)


def generate_ass_header(
    style: CaptionStyle,
    format_spec: FormatSpec,
    title: str = "Captions",
) -> str:
    """
    Generate ASS file header with script info and styles.

    Args:
        style: CaptionStyle for formatting
        format_spec: FormatSpec for resolution
        title: Video title

    Returns:
        ASS header string
    """
    header = f"""[Script Info]
Title: {title}
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {format_spec.width}
PlayResY: {format_spec.height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style.to_ass_style("Default")}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return header


def generate_ass_dialogue(
    chunk: CaptionChunk,
    style: CaptionStyle,
    layer: int = 0,
) -> str:
    """
    Generate ASS dialogue line for a caption chunk.

    Args:
        chunk: CaptionChunk with words
        style: CaptionStyle for formatting
        layer: Layer number (for overlapping subtitles)

    Returns:
        ASS dialogue line
    """
    start_time = format_time(chunk.start)
    end_time = format_time(chunk.end)
    text = generate_karaoke_text(chunk, style)

    # Add fade effect if specified
    if style.fade_in_ms > 0 or style.fade_out_ms > 0:
        text = f"{{\\fad({style.fade_in_ms},{style.fade_out_ms})}}{text}"

    return f"Dialogue: {layer},{start_time},{end_time},Default,,0,0,0,,{text}"


def generate_captions(
    words: List[Dict[str, Any]],
    format_type: ExportFormat = ExportFormat.TIKTOK,
    style: Optional[CaptionStyle] = None,
    format_spec: Optional[FormatSpec] = None,
    title: str = "Captions",
    time_offset: float = 0.0,
) -> str:
    """
    Generate complete ASS subtitle file from word-level timestamps.

    Args:
        words: List of word dicts with 'word', 'start', 'end' keys
        format_type: Export format (determines default style)
        style: Optional custom CaptionStyle
        format_spec: Optional custom FormatSpec
        title: Video title for ASS header
        time_offset: Offset to add to all timestamps

    Returns:
        Complete ASS subtitle file content
    """
    # Get defaults if not provided
    if style is None:
        style = get_caption_style(format_type)
    if format_spec is None:
        format_spec = get_format(format_type)

    # Convert word dicts to Word objects
    word_objects = []
    for w in words:
        text = w.get("word", w.get("text", "")).strip()
        if not text:
            continue

        start = w.get("start", 0) + time_offset
        end = w.get("end", start + 0.1) + time_offset

        word_objects.append(Word(text=text, start=start, end=end))

    # Group into chunks
    chunks = words_to_chunks(
        word_objects,
        max_words=style.words_per_line,
        max_duration=3.0,
    )

    # Generate ASS content
    lines = [generate_ass_header(style, format_spec, title)]

    for chunk in chunks:
        lines.append(generate_ass_dialogue(chunk, style))

    return "\n".join(lines)


def generate_captions_from_transcript(
    transcript: Dict[str, Any],
    format_type: ExportFormat = ExportFormat.TIKTOK,
    clip_start: Optional[float] = None,
    clip_end: Optional[float] = None,
) -> str:
    """
    Generate captions from a full transcript dict.

    Handles the transcript format from Whisper/Deepgram.

    Args:
        transcript: Transcript dict with 'segments' containing 'words'
        format_type: Export format
        clip_start: Optional clip start time
        clip_end: Optional clip end time

    Returns:
        ASS subtitle content
    """
    all_words = []

    for segment in transcript.get("segments", []):
        for word in segment.get("words", []):
            word_start = word.get("start", 0)
            word_end = word.get("end", word_start + 0.1)

            # Filter by clip range if specified
            if clip_start is not None and word_end < clip_start:
                continue
            if clip_end is not None and word_start > clip_end:
                continue

            all_words.append(word)

    # Adjust times relative to clip start
    time_offset = -(clip_start or 0)

    return generate_captions(
        words=all_words,
        format_type=format_type,
        time_offset=time_offset,
    )


def save_captions(
    content: str,
    output_path: str,
) -> str:
    """
    Save ASS captions to file.

    Args:
        content: ASS file content
        output_path: Output file path

    Returns:
        Path to saved file
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    return output_path


if __name__ == "__main__":
    print("Caption Generator - Test Mode")
    print("=" * 60)

    # Simulate word-level transcript
    test_words = [
        {"word": "Hello", "start": 0.0, "end": 0.3},
        {"word": "everyone,", "start": 0.35, "end": 0.6},
        {"word": "welcome", "start": 0.65, "end": 0.9},
        {"word": "to", "start": 0.92, "end": 1.0},
        {"word": "this", "start": 1.05, "end": 1.2},
        {"word": "video.", "start": 1.25, "end": 1.6},
        {"word": "Today", "start": 2.0, "end": 2.3},
        {"word": "we're", "start": 2.35, "end": 2.5},
        {"word": "going", "start": 2.55, "end": 2.7},
        {"word": "to", "start": 2.72, "end": 2.8},
        {"word": "talk", "start": 2.85, "end": 3.0},
        {"word": "about", "start": 3.05, "end": 3.25},
        {"word": "something", "start": 3.3, "end": 3.6},
        {"word": "really", "start": 3.65, "end": 3.85},
        {"word": "important.", "start": 3.9, "end": 4.4},
    ]

    print(f"\nTest words: {len(test_words)}")
    for w in test_words[:5]:
        print(f"  {w['start']:.2f}s - {w['end']:.2f}s: {w['word']}")
    print("  ...")

    # Generate for TikTok
    print("\n" + "=" * 60)
    print("TikTok Captions (ASS format):")
    print("=" * 60)

    ass_content = generate_captions(
        words=test_words,
        format_type=ExportFormat.TIKTOK,
        title="Test Video",
    )

    print(ass_content)

    # Show word chunking
    print("\n" + "=" * 60)
    print("Caption chunks:")
    word_objects = [Word(text=w["word"], start=w["start"], end=w["end"]) for w in test_words]
    chunks = words_to_chunks(word_objects, max_words=5)

    for i, chunk in enumerate(chunks):
        print(f"\n  Chunk {i+1}: {chunk.start:.2f}s - {chunk.end:.2f}s")
        print(f"    Text: {chunk.text}")
        print(f"    Words: {len(chunk.words)}")
