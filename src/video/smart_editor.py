"""
Smart audio/video editor that removes:
1. Long pauses (adjustable threshold)
2. Filler words (uh, um, like, you know)
3. Stumbles/restarts (when speaker re-says something)

Platform presets:
- youtube_shorts: Aggressive - tight cuts, minimal pauses (0.15s max)
- tiktok: Aggressive - fast paced, punchy (0.2s max pause)
- linkedin: Moderate - professional but not rushed (0.4s max pause)
- podcast: Light - natural speech preserved (0.6s max pause)

Usage:
    from src.video.smart_editor import SmartEditor
    editor = SmartEditor(preset='tiktok')
    cuts = editor.analyze(words, segments)
    # cuts = list of segments to KEEP
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class EditPreset(Enum):
    YOUTUBE_SHORTS = "youtube_shorts"
    TIKTOK = "tiktok"
    LINKEDIN = "linkedin"
    PODCAST = "podcast"
    CUSTOM = "custom"


@dataclass
class EditConfig:
    """Configuration for smart editing."""
    # Pause handling
    max_pause_duration: float = 0.3  # Max pause to keep (seconds)
    min_pause_to_trim: float = 0.15  # Don't trim pauses shorter than this
    pause_replacement: float = 0.1   # Replace long pauses with this duration

    # Sentence boundary handling
    sentence_end_pause: float = 0.35  # Pause to keep after sentence ends (. ! ?)
    sentence_end_chars: str = ".!?"   # Characters that indicate sentence end

    # Filler word handling
    remove_fillers: bool = True
    filler_words: List[str] = field(default_factory=lambda: [
        "uh", "um", "er", "ah", "eh",
        "like",  # when used as filler, not comparison
        "you know", "i mean", "sort of", "kind of",
        "basically", "actually", "literally",  # when overused
    ])

    # Stumble/restart handling
    detect_restarts: bool = True
    restart_window: float = 5.0  # Look for restarts within this window
    min_restart_words: int = 2   # Minimum words to consider a restart

    # Word-gap handling (micro-pauses between words)
    max_word_gap: float = 0.5    # Max gap between words before it's a "pause"


# Platform presets
PRESETS: Dict[EditPreset, EditConfig] = {
    EditPreset.YOUTUBE_SHORTS: EditConfig(
        max_pause_duration=0.15,
        min_pause_to_trim=0.1,
        pause_replacement=0.08,
        sentence_end_pause=0.25,  # Still keep some pause at sentence end
        remove_fillers=True,
        detect_restarts=True,
        max_word_gap=0.3,
    ),
    EditPreset.TIKTOK: EditConfig(
        max_pause_duration=0.2,
        min_pause_to_trim=0.1,
        pause_replacement=0.1,
        sentence_end_pause=0.3,
        remove_fillers=True,
        detect_restarts=True,
        max_word_gap=0.35,
    ),
    EditPreset.LINKEDIN: EditConfig(
        max_pause_duration=0.7,      # More natural pacing - was 0.4
        min_pause_to_trim=0.5,       # Only trim pauses > 0.5s - was 0.2
        pause_replacement=0.35,      # Keep reasonable pause - was 0.15
        sentence_end_pause=0.6,      # Natural breath at sentence end - was 0.4
        remove_fillers=True,
        detect_restarts=True,
        max_word_gap=0.6,            # Allow natural word spacing - was 0.5
    ),
    EditPreset.PODCAST: EditConfig(
        max_pause_duration=0.6,
        min_pause_to_trim=0.3,
        pause_replacement=0.25,
        sentence_end_pause=0.5,
        remove_fillers=False,  # Keep natural speech
        detect_restarts=True,
        max_word_gap=0.7,
    ),
}


@dataclass
class EditSegment:
    """A segment to keep or cut."""
    start: float
    end: float
    keep: bool
    reason: str  # Why we're cutting/keeping this
    text: Optional[str] = None


@dataclass
class WordInfo:
    """Word with timing and metadata."""
    word: str
    start: float
    end: float
    clean_word: str = ""  # Lowercase, no punctuation
    is_filler: bool = False

    def __post_init__(self):
        self.clean_word = re.sub(r'[^\w\s]', '', self.word.lower())


class SmartEditor:
    """Smart editor that analyzes transcripts and generates edit points."""

    def __init__(
        self,
        preset: EditPreset = EditPreset.LINKEDIN,
        config: Optional[EditConfig] = None,
    ):
        if config:
            self.config = config
        else:
            self.config = PRESETS.get(preset, PRESETS[EditPreset.LINKEDIN])

        self.preset = preset

    def analyze(
        self,
        segments: List[Dict[str, Any]],
        clip_start: Optional[float] = None,
        clip_end: Optional[float] = None,
    ) -> List[EditSegment]:
        """
        Analyze transcript segments and return edit decisions.

        Args:
            segments: Transcript segments with word-level timestamps
            clip_start: Optional start time to filter to
            clip_end: Optional end time to filter to

        Returns:
            List of EditSegments indicating what to keep/cut
        """
        # Extract all words with timing
        all_words = self._extract_words(segments, clip_start, clip_end)

        if not all_words:
            return []

        # Mark filler words
        if self.config.remove_fillers:
            self._mark_fillers(all_words)

        # Detect restarts/stumbles
        restarts = []
        if self.config.detect_restarts:
            restarts = self._detect_restarts(all_words)

        # Generate edit segments
        edits = self._generate_edits(all_words, restarts)

        return edits

    def _extract_words(
        self,
        segments: List[Dict],
        clip_start: Optional[float],
        clip_end: Optional[float],
    ) -> List[WordInfo]:
        """Extract all words from segments."""
        words = []

        for seg in segments:
            seg_words = seg.get('words', [])

            for w in seg_words:
                word_start = w.get('start', 0)
                word_end = w.get('end', word_start)

                # Filter to clip range if specified
                if clip_start is not None and word_end < clip_start:
                    continue
                if clip_end is not None and word_start > clip_end:
                    continue

                words.append(WordInfo(
                    word=w.get('word', ''),
                    start=word_start,
                    end=word_end,
                ))

        return words

    def _mark_fillers(self, words: List[WordInfo]) -> None:
        """Mark filler words in the word list."""
        single_fillers = set()
        multi_fillers = []

        for filler in self.config.filler_words:
            if ' ' in filler:
                multi_fillers.append(filler.split())
            else:
                single_fillers.add(filler)

        # Mark single-word fillers
        for word in words:
            if word.clean_word in single_fillers:
                word.is_filler = True

        # Mark multi-word fillers (e.g., "you know")
        for i, word in enumerate(words):
            for filler_parts in multi_fillers:
                if i + len(filler_parts) > len(words):
                    continue

                match = True
                for j, part in enumerate(filler_parts):
                    if words[i + j].clean_word != part:
                        match = False
                        break

                if match:
                    for j in range(len(filler_parts)):
                        words[i + j].is_filler = True

    def _detect_restarts(self, words: List[WordInfo]) -> List[Tuple[int, int]]:
        """
        Detect restarts/stumbles where speaker re-says something.

        Returns list of (start_idx, end_idx) of words to CUT (the fumbled part).
        """
        restarts = []

        # First, detect sentence-level repeats (e.g., "It's so simple. It's so simple.")
        sentence_restarts = self._detect_sentence_repeats(words)
        restarts.extend(sentence_restarts)

        # Create set of already-cut indices to avoid double-cutting
        cut_indices = set()
        for cut_start, cut_end in restarts:
            for i in range(cut_start, cut_end + 1):
                cut_indices.add(i)

        # Then look for word-level patterns like:
        # "The construction... the construction industry" -> cut first "the construction"
        # "We need to... we need to focus" -> cut first "we need to"

        i = 0
        while i < len(words) - self.config.min_restart_words:
            # Skip if this word is already being cut
            if i in cut_indices:
                i += 1
                continue

            # Get a window of upcoming words
            window_end = i
            for j in range(i, len(words)):
                if words[j].start - words[i].start > self.config.restart_window:
                    break
                window_end = j

            # Look for repeated sequences starting at position i
            restart_found = self._find_restart_in_window(words, i, window_end)

            if restart_found:
                cut_start, cut_end = restart_found
                # Check we're not overlapping with sentence restarts
                overlap = any(idx in cut_indices for idx in range(cut_start, cut_end + 1))
                if not overlap:
                    restarts.append((cut_start, cut_end))
                    # Skip past the cut section
                    i = cut_end + 1
                else:
                    i += 1
            else:
                i += 1

        return restarts

    def _detect_sentence_repeats(self, words: List[WordInfo]) -> List[Tuple[int, int]]:
        """
        Detect when a phrase is repeated regardless of sentence boundaries.

        CONSERVATIVE approach: Only cut the EXACT repeated phrase, not content in between.
        This prevents cutting meaningful content that happens to be near a restart.

        Examples:
        - "It's so simple. It's so simple but..." -> cut just first "It's so simple"
        - "survey quality is... if it's a GIS aerial... If it's a GIS aerial survey"
          -> cut "if it's a GIS aerial" (first occurrence only)

        Returns list of (start_idx, end_idx) of words to CUT.
        """
        restarts = []
        already_cut = set()  # Avoid overlapping cuts

        # Look for repeated phrases of length 3-6 words (not too long)
        for phrase_len in range(3, 7):
            i = 0
            while i < len(words) - phrase_len:
                if i in already_cut:
                    i += 1
                    continue

                # Get phrase starting at i
                phrase = [words[i + k].clean_word for k in range(phrase_len)]

                # Skip phrases that start with very common words unless longer
                skip_starts = ['i', 'you', 'and', 'the', 'a', 'um', 'uh', 'so', 'but', 'or']
                if phrase[0] in skip_starts and phrase_len < 4:
                    i += 1
                    continue

                # Look for this phrase later (within 10 second window - tighter)
                for j in range(i + phrase_len, len(words) - phrase_len + 1):
                    # Time window check - only look within 10 seconds
                    time_gap = words[j].start - words[i + phrase_len - 1].end
                    if time_gap > 10.0:
                        break

                    # Check if phrase matches
                    match = True
                    for k in range(phrase_len):
                        if words[j + k].clean_word != phrase[k]:
                            match = False
                            break

                    if match:
                        # Found a repeat!
                        # CONSERVATIVE: Only cut the first occurrence of the phrase itself
                        # Don't cut anything else, even if there's content between them
                        phrase_end = i + phrase_len - 1

                        # Mark just this phrase as cut
                        for k in range(i, phrase_end + 1):
                            already_cut.add(k)
                        restarts.append((i, phrase_end))
                        break

                i += 1

        return restarts

    def _find_restart_in_window(
        self,
        words: List[WordInfo],
        start: int,
        end: int,
    ) -> Optional[Tuple[int, int]]:
        """
        Look for a restart pattern in a window of words.

        Returns (cut_start, cut_end) indices if restart found, None otherwise.
        """
        # Try different sequence lengths
        for seq_len in range(self.config.min_restart_words, min(6, end - start)):
            # Get the sequence at position start
            seq = [words[start + k].clean_word for k in range(seq_len)]

            # Look for this sequence later in the window
            for j in range(start + seq_len, end - seq_len + 2):
                match = True
                for k in range(seq_len):
                    if j + k >= len(words):
                        match = False
                        break
                    if words[j + k].clean_word != seq[k]:
                        match = False
                        break

                if match:
                    # Found a restart! Cut from start to just before the restart
                    # Keep the second occurrence (usually cleaner)
                    return (start, j - 1)

        return None

    def _generate_edits(
        self,
        words: List[WordInfo],
        restarts: List[Tuple[int, int]],
    ) -> List[EditSegment]:
        """Generate final edit segments."""
        if not words:
            return []

        edits = []

        # Create a set of word indices to cut
        cut_indices = set()

        # Add restart cuts
        for cut_start, cut_end in restarts:
            for i in range(cut_start, cut_end + 1):
                cut_indices.add(i)

        # Add filler word cuts
        if self.config.remove_fillers:
            for i, word in enumerate(words):
                if word.is_filler:
                    cut_indices.add(i)

        # Now generate segments
        current_segment_start = None
        current_segment_text = []

        def is_sentence_end(word_text: str) -> bool:
            """Check if word ends with sentence-ending punctuation."""
            return any(word_text.rstrip().endswith(c) for c in self.config.sentence_end_chars)

        for i, word in enumerate(words):
            # Check for pause before this word
            if i > 0:
                gap = word.start - words[i - 1].end
                prev_word = words[i - 1]

                # Determine max allowed pause based on whether previous word ended a sentence
                if is_sentence_end(prev_word.word):
                    max_pause = self.config.sentence_end_pause
                    replacement_pause = self.config.sentence_end_pause
                else:
                    max_pause = self.config.max_pause_duration
                    replacement_pause = self.config.pause_replacement

                if gap > max_pause:
                    # End current segment, add pause handling
                    if current_segment_start is not None:
                        edits.append(EditSegment(
                            start=current_segment_start,
                            end=words[i - 1].end,
                            keep=True,
                            reason="speech",
                            text=" ".join(current_segment_text),
                        ))
                        current_segment_start = None
                        current_segment_text = []

                    # Add trimmed pause (but respect sentence boundaries)
                    if gap > self.config.min_pause_to_trim:
                        edits.append(EditSegment(
                            start=words[i - 1].end,
                            end=word.start,
                            keep=False,
                            reason=f"long_pause ({gap:.2f}s -> {replacement_pause:.2f}s)",
                        ))

            # Handle this word
            if i in cut_indices:
                # End current segment if any
                if current_segment_start is not None:
                    edits.append(EditSegment(
                        start=current_segment_start,
                        end=words[i - 1].end if i > 0 else word.start,
                        keep=True,
                        reason="speech",
                        text=" ".join(current_segment_text),
                    ))
                    current_segment_start = None
                    current_segment_text = []

                # Add cut segment
                reason = "filler" if word.is_filler else "restart"
                edits.append(EditSegment(
                    start=word.start,
                    end=word.end,
                    keep=False,
                    reason=reason,
                    text=word.word,
                ))
            else:
                # Keep this word
                if current_segment_start is None:
                    current_segment_start = word.start
                current_segment_text.append(word.word)

        # Close final segment
        if current_segment_start is not None:
            edits.append(EditSegment(
                start=current_segment_start,
                end=words[-1].end,
                keep=True,
                reason="speech",
                text=" ".join(current_segment_text),
            ))

        # Merge adjacent keep segments and calculate time savings
        return self._merge_segments(edits)

    def _merge_segments(self, edits: List[EditSegment]) -> List[EditSegment]:
        """Merge adjacent segments of the same type."""
        if not edits:
            return []

        merged = []
        current = edits[0]

        for edit in edits[1:]:
            if edit.keep == current.keep and edit.keep:
                # Merge keep segments
                current = EditSegment(
                    start=current.start,
                    end=edit.end,
                    keep=True,
                    reason="speech",
                    text=f"{current.text or ''} {edit.text or ''}".strip(),
                )
            else:
                merged.append(current)
                current = edit

        merged.append(current)
        return merged

    def get_segments_to_keep(self, edits: List[EditSegment]) -> List[Dict[str, float]]:
        """Get just the segments to keep as simple dicts."""
        return [
            {"start": e.start, "end": e.end, "text": e.text}
            for e in edits
            if e.keep
        ]

    def calculate_time_savings(self, edits: List[EditSegment]) -> Dict[str, float]:
        """Calculate how much time is saved by edits."""
        original_duration = 0
        edited_duration = 0
        pause_savings = 0
        filler_savings = 0
        restart_savings = 0

        for edit in edits:
            duration = edit.end - edit.start
            original_duration += duration

            if edit.keep:
                edited_duration += duration
            else:
                if "pause" in edit.reason:
                    pause_savings += duration - self.config.pause_replacement
                    edited_duration += self.config.pause_replacement
                elif edit.reason == "filler":
                    filler_savings += duration
                elif edit.reason == "restart":
                    restart_savings += duration

        return {
            "original_duration": original_duration,
            "edited_duration": edited_duration,
            "total_savings": original_duration - edited_duration,
            "pause_savings": pause_savings,
            "filler_savings": filler_savings,
            "restart_savings": restart_savings,
            "percent_reduction": ((original_duration - edited_duration) / original_duration * 100) if original_duration > 0 else 0,
        }


def analyze_clip(
    segments: List[Dict],
    start_time: float,
    end_time: float,
    preset: str = "linkedin",
) -> Dict[str, Any]:
    """
    Convenience function to analyze a clip.

    Args:
        segments: Full transcript segments
        start_time: Clip start time
        end_time: Clip end time
        preset: Platform preset name

    Returns:
        Dict with segments_to_keep, time_savings, and edit_details
    """
    preset_enum = EditPreset(preset) if preset in [p.value for p in EditPreset] else EditPreset.LINKEDIN
    editor = SmartEditor(preset=preset_enum)

    edits = editor.analyze(segments, start_time, end_time)
    segments_to_keep = editor.get_segments_to_keep(edits)
    time_savings = editor.calculate_time_savings(edits)

    return {
        "segments_to_keep": segments_to_keep,
        "time_savings": time_savings,
        "edit_details": [
            {
                "start": e.start,
                "end": e.end,
                "keep": e.keep,
                "reason": e.reason,
                "text": e.text,
            }
            for e in edits
        ],
    }


if __name__ == "__main__":
    # Test with sample data
    print("Smart Editor - Test Mode")
    print("=" * 60)

    # Simulate a transcript with some stumbles
    sample_segments = [
        {
            "start": 0.0,
            "end": 5.0,
            "text": "So the construction... the construction industry has changed.",
            "words": [
                {"word": "So", "start": 0.0, "end": 0.2},
                {"word": "the", "start": 0.3, "end": 0.4},
                {"word": "construction...", "start": 0.5, "end": 1.0},
                # Gap here - restart
                {"word": "the", "start": 1.8, "end": 1.9},
                {"word": "construction", "start": 2.0, "end": 2.5},
                {"word": "industry", "start": 2.6, "end": 3.0},
                {"word": "has", "start": 3.1, "end": 3.2},
                {"word": "changed.", "start": 3.3, "end": 3.6},
            ],
        },
        {
            "start": 5.0,
            "end": 10.0,
            "text": "Um, you know, it's basically amazing.",
            "words": [
                {"word": "Um,", "start": 5.0, "end": 5.3},
                {"word": "you", "start": 5.5, "end": 5.6},
                {"word": "know,", "start": 5.7, "end": 5.9},
                {"word": "it's", "start": 6.5, "end": 6.7},  # Long pause before
                {"word": "basically", "start": 6.8, "end": 7.2},
                {"word": "amazing.", "start": 7.3, "end": 7.8},
            ],
        },
    ]

    for preset_name in ["youtube_shorts", "tiktok", "linkedin", "podcast"]:
        print(f"\n{preset_name.upper()} preset:")
        print("-" * 40)

        result = analyze_clip(sample_segments, 0, 10, preset_name)

        print(f"Time savings: {result['time_savings']['percent_reduction']:.1f}%")
        print(f"  Pauses: -{result['time_savings']['pause_savings']:.2f}s")
        print(f"  Fillers: -{result['time_savings']['filler_savings']:.2f}s")
        print(f"  Restarts: -{result['time_savings']['restart_savings']:.2f}s")

        print("\nSegments to keep:")
        for seg in result['segments_to_keep']:
            print(f"  [{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text'][:50]}...")
