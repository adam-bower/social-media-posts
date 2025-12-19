"""
Transcript-enhanced audio editing.

This module uses transcription data to enhance silence removal by:
1. Detecting filler words (um, uh, er, ah, etc.) for removal
2. Detecting restarts (same word repeated) for removal
3. Providing transcript-aware cut points that align with word boundaries

The key principle is: VAD determines WHERE cuts can happen, transcript determines
WHAT should be cut. This prevents word clipping since we only cut during detected
silence, not based on potentially inaccurate word timestamps.

Usage:
    from src.video.transcript_enhanced_editor import TranscriptEnhancedEditor

    editor = TranscriptEnhancedEditor()

    # Analyze transcript for fillers and restarts
    analysis = editor.analyze_transcript(transcript_data)

    # Get enhanced edit decisions (to pass to waveform_silence_remover)
    enhanced = editor.enhance_edit_decisions(
        vad_decisions=silence_decisions,
        transcript=transcript_data,
    )
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Set
import re


# Common filler words across languages (primarily English)
FILLER_WORDS = {
    # English fillers
    "um", "uh", "er", "ah", "eh", "hmm", "hm", "mm", "mmm",
    "like", "you know", "i mean", "basically", "actually", "literally",
    "so", "well", "right", "okay", "ok",
}

# Fillers that should ONLY be removed if followed by silence or a restart
# (these can be meaningful in context)
CONTEXT_DEPENDENT_FILLERS = {
    "like", "so", "well", "right", "okay", "ok", "actually", "basically", "literally",
    "you know", "i mean",
}

# Pure fillers that can always be removed
PURE_FILLERS = {
    "um", "uh", "er", "ah", "eh", "hmm", "hm", "mm", "mmm",
}


@dataclass
class FillerWord:
    """A detected filler word with timing."""
    word: str
    start: float
    end: float
    confidence: float
    is_pure_filler: bool  # True if um/uh/er, False if context-dependent

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class RestartSequence:
    """A detected restart/repetition sequence."""
    repeated_word: str
    occurrences: List[Dict[str, float]]  # List of {start, end} for each occurrence
    first_start: float
    last_end: float

    @property
    def duration(self) -> float:
        return self.last_end - self.first_start


@dataclass
class OpeningFalseStart:
    """A false start at the beginning of the recording."""
    false_start_end: float  # Where the false start ends
    real_start: float       # Where the real content begins
    words_cut: List[str]    # Words that would be cut


@dataclass
class TranscriptAnalysis:
    """Results of analyzing a transcript."""
    fillers: List[FillerWord]
    restarts: List[RestartSequence]
    opening_false_start: Optional[OpeningFalseStart]
    total_filler_duration: float
    total_restart_duration: float
    words_analyzed: int


class TranscriptEnhancedEditor:
    """
    Enhances edit decisions using transcript analysis.

    This class analyzes transcripts to identify:
    1. Filler words (um, uh, er, etc.) that can be removed
    2. Restarts (where the speaker repeats words) that can be removed

    It then enhances VAD-based edit decisions by marking these sections
    for removal, but ONLY if they fall within detected silence gaps.
    """

    def __init__(
        self,
        filler_words: Optional[Set[str]] = None,
        min_restart_gap_ms: int = 0,
        max_restart_gap_ms: int = 500,
    ):
        """
        Initialize the editor.

        Args:
            filler_words: Set of filler words to detect (defaults to FILLER_WORDS)
            min_restart_gap_ms: Minimum gap between repeated words to count as restart
            max_restart_gap_ms: Maximum gap between repeated words to count as restart
        """
        self.filler_words = filler_words or FILLER_WORDS
        self.min_restart_gap = min_restart_gap_ms / 1000.0
        self.max_restart_gap = max_restart_gap_ms / 1000.0

    def analyze_transcript(
        self,
        transcript: Dict[str, Any],
        detect_restarts: bool = True,
        detect_opening_false_start: bool = True,
    ) -> TranscriptAnalysis:
        """
        Analyze a transcript for fillers and restarts.

        Args:
            transcript: Transcript dict with 'segments' containing word-level timing
            detect_restarts: Whether to detect word restarts
            detect_opening_false_start: Whether to detect false starts at beginning

        Returns:
            TranscriptAnalysis with detected fillers and restarts
        """
        words = self._extract_words(transcript)

        # Detect fillers
        fillers = self._detect_fillers(words)

        # Detect restarts
        restarts = []
        if detect_restarts:
            restarts = self._detect_restarts(words)

        # Detect opening false start
        opening_false_start = None
        if detect_opening_false_start:
            opening_false_start = self._detect_opening_false_start(words)

        # Calculate totals
        total_filler_duration = sum(f.duration for f in fillers)
        total_restart_duration = sum(r.duration for r in restarts)

        return TranscriptAnalysis(
            fillers=fillers,
            restarts=restarts,
            opening_false_start=opening_false_start,
            total_filler_duration=total_filler_duration,
            total_restart_duration=total_restart_duration,
            words_analyzed=len(words),
        )

    def _extract_words(self, transcript: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract word-level data from transcript."""
        words = []

        for segment in transcript.get("segments", []):
            for word in segment.get("words", []):
                words.append({
                    "word": word.get("word", "").strip(),
                    "start": word.get("start", 0),
                    "end": word.get("end", 0),
                    "confidence": word.get("confidence", word.get("probability", 1.0)),
                })

        return words

    def _detect_fillers(self, words: List[Dict[str, Any]]) -> List[FillerWord]:
        """Detect filler words in the word list."""
        fillers = []

        for word_data in words:
            word = word_data["word"].lower().strip(".,!?;:'\"")

            if word in self.filler_words:
                is_pure = word in PURE_FILLERS
                fillers.append(FillerWord(
                    word=word_data["word"],
                    start=word_data["start"],
                    end=word_data["end"],
                    confidence=word_data.get("confidence", 1.0),
                    is_pure_filler=is_pure,
                ))

        return fillers

    def _detect_restarts(self, words: List[Dict[str, Any]]) -> List[RestartSequence]:
        """
        Detect restart sequences (repeated words).

        A restart is when the speaker says the same word multiple times in quick
        succession, typically due to stumbling or false starts.

        Example: "The the the problem is..." -> restart on "the"
        """
        restarts = []
        i = 0

        while i < len(words):
            word = words[i]["word"].lower().strip(".,!?;:'\"")

            # Skip very short words (likely punctuation artifacts)
            if len(word) < 2:
                i += 1
                continue

            # Look for repetitions
            occurrences = [{
                "start": words[i]["start"],
                "end": words[i]["end"],
            }]

            j = i + 1
            while j < len(words):
                next_word = words[j]["word"].lower().strip(".,!?;:'\"")
                gap = words[j]["start"] - words[j-1]["end"]

                # Check if same word and within gap limits
                if next_word == word and self.min_restart_gap <= gap <= self.max_restart_gap:
                    occurrences.append({
                        "start": words[j]["start"],
                        "end": words[j]["end"],
                    })
                    j += 1
                else:
                    break

            # If we found repetitions (2+ occurrences), record it
            if len(occurrences) >= 2:
                # The restart includes all but the last occurrence
                # (we keep the final, successful attempt)
                restart_occurrences = occurrences[:-1]
                restarts.append(RestartSequence(
                    repeated_word=word,
                    occurrences=restart_occurrences,
                    first_start=restart_occurrences[0]["start"],
                    last_end=restart_occurrences[-1]["end"],
                ))
                i = j  # Skip past the restart sequence
            else:
                i += 1

        return restarts

    def _detect_opening_false_start(
        self,
        words: List[Dict[str, Any]],
        max_false_start_duration: float = 15.0,
        min_gap_for_restart: float = 0.5,
    ) -> Optional[OpeningFalseStart]:
        """
        Detect a false start at the beginning of the recording.

        A false start is when the speaker starts, stops, and restarts.
        Pattern: Words -> Gap (0.5s+) -> Same/similar opening words

        Example: "So this" [gap] "so this year at AB Civil..."
                 ^^^^^^^^ false start

        Args:
            words: List of word dicts with timing
            max_false_start_duration: Only look in first N seconds
            min_gap_for_restart: Minimum gap to consider it a restart

        Returns:
            OpeningFalseStart if detected, None otherwise
        """
        if len(words) < 4:
            return None

        # Only look at words in the first portion of the audio
        early_words = [w for w in words if w["start"] < max_false_start_duration]
        if len(early_words) < 4:
            return None

        # Look for a gap that indicates a restart
        for i in range(1, len(early_words) - 2):
            gap = early_words[i]["start"] - early_words[i-1]["end"]

            if gap >= min_gap_for_restart:
                # Found a significant gap - check if words after gap
                # are similar to words before gap (indicating a restart)
                words_before = [w["word"].lower().strip(".,!?;:'\"") for w in early_words[:i]]
                words_after = [w["word"].lower().strip(".,!?;:'\"") for w in early_words[i:i+3]]

                # Check if first word after gap matches first word before gap
                # or if the pattern repeats
                if len(words_before) >= 1 and len(words_after) >= 1:
                    first_before = words_before[0]
                    first_after = words_after[0]

                    # Match if same word or similar start (e.g., "so" matches "so")
                    is_restart = (
                        first_before == first_after or
                        (len(first_before) >= 2 and len(first_after) >= 2 and
                         first_before[:2] == first_after[:2])
                    )

                    if is_restart:
                        # Found a false start!
                        false_start_end = early_words[i-1]["end"]
                        real_start = early_words[i]["start"]
                        words_cut = [w["word"] for w in early_words[:i]]

                        return OpeningFalseStart(
                            false_start_end=false_start_end,
                            real_start=real_start,
                            words_cut=words_cut,
                        )

        return None

    def get_removal_regions(
        self,
        analysis: TranscriptAnalysis,
        include_pure_fillers: bool = True,
        include_context_fillers: bool = False,
        include_restarts: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get time regions that should be considered for removal.

        These regions are suggestions based on transcript analysis. The actual
        removal should only happen if the region falls within a VAD-detected
        silence gap to prevent cutting into speech.

        Args:
            analysis: Result from analyze_transcript()
            include_pure_fillers: Include um/uh/er type fillers
            include_context_fillers: Include context-dependent fillers (like, so, etc.)
            include_restarts: Include restart sequences

        Returns:
            List of {start, end, type, word} dicts for regions to potentially remove
        """
        regions = []

        # Add fillers
        for filler in analysis.fillers:
            if filler.is_pure_filler and include_pure_fillers:
                regions.append({
                    "start": filler.start,
                    "end": filler.end,
                    "type": "filler",
                    "word": filler.word,
                })
            elif not filler.is_pure_filler and include_context_fillers:
                regions.append({
                    "start": filler.start,
                    "end": filler.end,
                    "type": "context_filler",
                    "word": filler.word,
                })

        # Add restarts
        if include_restarts:
            for restart in analysis.restarts:
                regions.append({
                    "start": restart.first_start,
                    "end": restart.last_end,
                    "type": "restart",
                    "word": restart.repeated_word,
                })

        # Sort by start time
        regions.sort(key=lambda r: r["start"])

        return regions

    def enhance_silence_decisions(
        self,
        silences: List[Dict[str, float]],
        removal_regions: List[Dict[str, Any]],
        padding_ms: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Enhance silence removal decisions with transcript-based removal regions.

        This method checks if any removal regions (fillers, restarts) fall
        within detected silence gaps. If they do, those silences should be
        fully removed rather than just trimmed.

        Args:
            silences: List of {start, end} silence segments from VAD
            removal_regions: From get_removal_regions()
            padding_ms: Padding around removal regions

        Returns:
            Enhanced silence decisions with removal_reason field
        """
        padding = padding_ms / 1000.0
        enhanced = []

        for silence in silences:
            silence_start = silence["start"]
            silence_end = silence["end"]

            # Check if any removal region falls within this silence
            removal_reason = None
            for region in removal_regions:
                # Region is within silence (with padding)
                region_start = region["start"] - padding
                region_end = region["end"] + padding

                if region_start >= silence_start and region_end <= silence_end:
                    removal_reason = f"{region['type']}: {region['word']}"
                    break

                # Region overlaps with silence significantly
                overlap_start = max(silence_start, region_start)
                overlap_end = min(silence_end, region_end)
                overlap = overlap_end - overlap_start

                if overlap > 0:
                    region_duration = region["end"] - region["start"]
                    if overlap >= region_duration * 0.5:
                        removal_reason = f"{region['type']}: {region['word']} (partial)"
                        break

            enhanced.append({
                "start": silence_start,
                "end": silence_end,
                "duration": silence_end - silence_start,
                "removal_reason": removal_reason,
                "should_fully_remove": removal_reason is not None,
            })

        return enhanced


def analyze_transcript_for_editing(
    transcript: Dict[str, Any],
    include_restarts: bool = True,
) -> Dict[str, Any]:
    """
    Convenience function to analyze a transcript for editing.

    Args:
        transcript: Transcript dict with word-level timing
        include_restarts: Whether to detect restarts

    Returns:
        Dict with analysis results and removal regions
    """
    editor = TranscriptEnhancedEditor()
    analysis = editor.analyze_transcript(transcript, detect_restarts=include_restarts)
    removal_regions = editor.get_removal_regions(analysis)

    return {
        "fillers": [
            {
                "word": f.word,
                "start": f.start,
                "end": f.end,
                "is_pure": f.is_pure_filler,
            }
            for f in analysis.fillers
        ],
        "restarts": [
            {
                "word": r.repeated_word,
                "start": r.first_start,
                "end": r.last_end,
                "count": len(r.occurrences),
            }
            for r in analysis.restarts
        ],
        "removal_regions": removal_regions,
        "summary": {
            "total_fillers": len(analysis.fillers),
            "pure_fillers": sum(1 for f in analysis.fillers if f.is_pure_filler),
            "context_fillers": sum(1 for f in analysis.fillers if not f.is_pure_filler),
            "total_restarts": len(analysis.restarts),
            "filler_duration_s": analysis.total_filler_duration,
            "restart_duration_s": analysis.total_restart_duration,
            "potential_savings_s": analysis.total_filler_duration + analysis.total_restart_duration,
            "words_analyzed": analysis.words_analyzed,
        },
    }


if __name__ == "__main__":
    # Test with sample transcript
    sample_transcript = {
        "segments": [
            {
                "words": [
                    {"word": "So", "start": 0.0, "end": 0.2},
                    {"word": "um", "start": 0.5, "end": 0.7},
                    {"word": "the", "start": 1.0, "end": 1.1},
                    {"word": "the", "start": 1.3, "end": 1.4},
                    {"word": "the", "start": 1.6, "end": 1.7},
                    {"word": "problem", "start": 1.9, "end": 2.3},
                    {"word": "is", "start": 2.4, "end": 2.5},
                    {"word": "uh", "start": 2.8, "end": 3.0},
                    {"word": "basically", "start": 3.2, "end": 3.6},
                    {"word": "like", "start": 3.8, "end": 4.0},
                    {"word": "this", "start": 4.1, "end": 4.3},
                ]
            }
        ]
    }

    print("Transcript Enhancement Analysis")
    print("=" * 60)

    result = analyze_transcript_for_editing(sample_transcript)

    print(f"\nFillers found: {result['summary']['total_fillers']}")
    print(f"  Pure fillers (um/uh): {result['summary']['pure_fillers']}")
    print(f"  Context fillers: {result['summary']['context_fillers']}")

    for filler in result["fillers"]:
        print(f"    - '{filler['word']}' at {filler['start']:.1f}s")

    print(f"\nRestarts found: {result['summary']['total_restarts']}")
    for restart in result["restarts"]:
        print(f"    - '{restart['word']}' x{restart['count']} at {restart['start']:.1f}s")

    print(f"\nPotential time savings: {result['summary']['potential_savings_s']:.1f}s")

    print(f"\nRemoval regions:")
    for region in result["removal_regions"]:
        print(f"  {region['start']:.1f}s - {region['end']:.1f}s: {region['type']} ({region['word']})")
