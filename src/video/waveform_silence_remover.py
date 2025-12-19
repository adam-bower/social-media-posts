"""
Waveform-first silence removal using Silero VAD.

This module detects silence using Silero VAD (neural network-based voice activity
detection), rather than relying on potentially inaccurate transcription timestamps.
This fixes the "discrepancies" word clipping bug where transcript timestamps can be
off by ~175ms.

Core Principle:
    Waveform determines WHERE to cut, transcript (optionally) determines WHAT to cut.

Why Silero VAD:
    RMS-based detection doesn't work for real-world recordings with background noise.
    Silero VAD is trained to distinguish speech from non-speech regardless of ambient
    noise level, making it reliable for phone-recorded videos.

Usage:
    from src.video.waveform_silence_remover import process_clip_waveform_only

    result = process_clip_waveform_only(
        audio_path="data/audio/video_id.wav",
        output_path="data/output/edited.wav",
        preset="linkedin",
    )
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum


# Global Silero model cache for lazy loading
_silero_model = None
_silero_utils = None

# Global VAD results cache: audio_path -> (speech_segments, silences, duration)
_vad_cache: Dict[str, tuple] = {}


@dataclass
class SpeechSegment:
    """A segment of detected speech."""
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class SilenceSegment:
    """A segment of detected silence."""
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class EditDecision:
    """Decision about what to do with a segment."""
    start: float
    end: float
    action: str  # "keep", "remove", "trim"
    reason: str
    original_duration: float = 0.0
    new_duration: float = 0.0

    def __post_init__(self):
        self.original_duration = self.end - self.start


class PlatformPreset(Enum):
    LINKEDIN = "linkedin"
    YOUTUBE_SHORTS = "youtube_shorts"
    TIKTOK = "tiktok"
    PODCAST = "podcast"


@dataclass
class PresetConfig:
    """Configuration for a platform preset."""
    # Silence detection (Silero VAD)
    vad_threshold: float = 0.5           # Silero VAD threshold (0.0-1.0, higher = stricter)
    min_silence_ms: int = 300            # Minimum silence duration to detect

    # Silence trimming
    max_kept_silence_ms: int = 400       # Maximum silence to keep (trim to this)

    # Padding around speech
    speech_padding_ms: int = 150         # Padding to add around speech segments

    # Crossfade
    crossfade_ms: int = 10               # Crossfade duration at cut points


# Platform presets
PRESETS: Dict[PlatformPreset, PresetConfig] = {
    PlatformPreset.LINKEDIN: PresetConfig(
        vad_threshold=0.5,
        min_silence_ms=500,
        max_kept_silence_ms=700,
        speech_padding_ms=150,
        crossfade_ms=10,
    ),
    PlatformPreset.YOUTUBE_SHORTS: PresetConfig(
        vad_threshold=0.5,
        min_silence_ms=300,
        max_kept_silence_ms=200,
        speech_padding_ms=100,
        crossfade_ms=10,
    ),
    PlatformPreset.TIKTOK: PresetConfig(
        vad_threshold=0.5,
        min_silence_ms=200,
        max_kept_silence_ms=150,
        speech_padding_ms=80,
        crossfade_ms=10,
    ),
    PlatformPreset.PODCAST: PresetConfig(
        vad_threshold=0.5,
        min_silence_ms=800,
        max_kept_silence_ms=1000,
        speech_padding_ms=200,
        crossfade_ms=10,
    ),
}


class SileroVADDetector:
    """
    Voice Activity Detection using Silero VAD model.

    Silero VAD is a neural network-based speech detector that's more accurate
    than RMS-based detection, especially in noisy audio or with background music.

    The model is loaded lazily on first use and cached globally.
    """

    SAMPLE_RATE = 16000  # Silero requires 16kHz audio

    def __init__(self, config: Optional[PresetConfig] = None):
        """
        Initialize the Silero VAD detector.

        Args:
            config: Optional preset config for min_silence_ms threshold
        """
        self.config = config or PresetConfig()
        self.model = None
        self.get_speech_timestamps = None

    def _load_model(self) -> None:
        """Load Silero VAD model (lazy loading with global cache)."""
        global _silero_model, _silero_utils

        if _silero_model is not None:
            self.model = _silero_model
            self.get_speech_timestamps = _silero_utils
            return

        try:
            import torch
        except ImportError:
            raise ImportError(
                "torch is required for Silero VAD: pip install torch torchaudio"
            )

        # Load Silero VAD model from torch hub
        model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False,
            trust_repo=True,
        )

        (get_speech_timestamps, _, _, _, _) = utils

        # Cache globally
        _silero_model = model
        _silero_utils = get_speech_timestamps

        self.model = model
        self.get_speech_timestamps = get_speech_timestamps

    def detect_speech_segments(
        self,
        audio_path: str,
        threshold: float = 0.5,
    ) -> List[SpeechSegment]:
        """
        Detect speech segments using Silero VAD.

        Args:
            audio_path: Path to audio file
            threshold: VAD threshold (0.0-1.0), higher = more strict

        Returns:
            List of SpeechSegment objects
        """
        self._load_model()

        import torch
        import torchaudio

        # Load audio
        wav, sr = torchaudio.load(audio_path)

        # Convert to mono if stereo
        if wav.shape[0] > 1:
            wav = wav.mean(dim=0, keepdim=True)

        # Resample to 16kHz if needed
        if sr != self.SAMPLE_RATE:
            resampler = torchaudio.transforms.Resample(sr, self.SAMPLE_RATE)
            wav = resampler(wav)

        # Get speech timestamps
        speech_timestamps = self.get_speech_timestamps(
            wav.squeeze(),
            self.model,
            threshold=threshold,
            sampling_rate=self.SAMPLE_RATE,
            min_silence_duration_ms=self.config.min_silence_ms,
            min_speech_duration_ms=100,  # Minimum speech segment
        )

        # Convert to SpeechSegment objects
        segments = []
        for ts in speech_timestamps:
            start = ts['start'] / self.SAMPLE_RATE
            end = ts['end'] / self.SAMPLE_RATE
            segments.append(SpeechSegment(start=start, end=end))

        return segments

    def detect_silence_segments(
        self,
        audio_path: str,
        threshold: float = 0.5,
    ) -> List[SilenceSegment]:
        """
        Detect silence segments (inverse of speech detection).

        Args:
            audio_path: Path to audio file
            threshold: VAD threshold (0.0-1.0)

        Returns:
            List of SilenceSegment objects
        """
        import torchaudio

        # Get audio duration
        info = torchaudio.info(audio_path)
        duration = info.num_frames / info.sample_rate

        speech_segments = self.detect_speech_segments(audio_path, threshold)

        if not speech_segments:
            # No speech found - entire audio is silence
            return [SilenceSegment(start=0.0, end=duration)]

        silences = []

        # Silence before first speech
        if speech_segments[0].start > 0:
            silences.append(SilenceSegment(
                start=0.0,
                end=speech_segments[0].start,
            ))

        # Silence between speech segments
        for i in range(len(speech_segments) - 1):
            silence_start = speech_segments[i].end
            silence_end = speech_segments[i + 1].start
            if silence_end > silence_start:
                silences.append(SilenceSegment(
                    start=silence_start,
                    end=silence_end,
                ))

        # Silence after last speech
        if speech_segments[-1].end < duration:
            silences.append(SilenceSegment(
                start=speech_segments[-1].end,
                end=duration,
            ))

        # Filter by minimum silence duration
        min_silence = self.config.min_silence_ms / 1000.0
        silences = [s for s in silences if s.duration >= min_silence]

        return silences


class AudioEditor:
    """
    Applies edit decisions to audio with crossfades.

    This is a utility class used by SileroVADDetector to apply edits.
    """

    def __init__(self, config: PresetConfig):
        self.config = config
        self.samples: Optional[np.ndarray] = None
        self.sample_rate: int = 0

    def load_audio(self, audio_path: str) -> None:
        """Load audio file."""
        try:
            import soundfile as sf
            samples, sr = sf.read(audio_path)
            if len(samples.shape) > 1:
                samples = samples.mean(axis=1)  # Stereo to mono
            self.samples = samples
            self.sample_rate = sr
        except ImportError:
            raise ImportError("soundfile is required: pip install soundfile")

    def apply_edits(
        self,
        decisions: List[EditDecision],
        output_path: Optional[str] = None,
    ) -> np.ndarray:
        """
        Apply edit decisions to create edited audio.

        Args:
            decisions: List of EditDecision objects
            output_path: Optional path to save the edited audio

        Returns:
            Edited audio samples as numpy array
        """
        if self.samples is None:
            raise ValueError("No audio loaded. Call load_audio() first.")

        # Only keep segments marked as "keep" or "trim"
        keep_decisions = [d for d in decisions if d.action in ("keep", "trim")]
        keep_decisions.sort(key=lambda d: d.start)

        if not keep_decisions:
            return np.array([])

        crossfade_samples = int(self.config.crossfade_ms * self.sample_rate / 1000)

        # Extract and concatenate segments
        segments = []
        for decision in keep_decisions:
            start_sample = int(decision.start * self.sample_rate)
            end_sample = int(decision.end * self.sample_rate)

            # Clamp to valid range
            start_sample = max(0, min(start_sample, len(self.samples)))
            end_sample = max(0, min(end_sample, len(self.samples)))

            if end_sample > start_sample:
                segment = self.samples[start_sample:end_sample].copy()
                segments.append(segment)

        if not segments:
            return np.array([])

        # Apply crossfades between segments
        edited = self._apply_crossfades(segments, crossfade_samples)

        # Save if output path provided
        if output_path:
            try:
                import soundfile as sf
                sf.write(output_path, edited, self.sample_rate)
            except ImportError:
                raise ImportError("soundfile is required: pip install soundfile")

        return edited

    def _apply_crossfades(
        self,
        segments: List[np.ndarray],
        crossfade_samples: int,
    ) -> np.ndarray:
        """Apply crossfades between segments to prevent clicks/pops."""
        if not segments:
            return np.array([])

        if len(segments) == 1:
            return segments[0]

        result_parts = []

        for i, segment in enumerate(segments):
            if len(segment) < crossfade_samples * 2:
                # Segment too short for crossfade, just add it
                result_parts.append(segment)
                continue

            # Apply fade in (except first segment)
            if i > 0:
                fade_in = np.linspace(0, 1, crossfade_samples)
                segment[:crossfade_samples] *= fade_in

            # Apply fade out (except last segment)
            if i < len(segments) - 1:
                fade_out = np.linspace(1, 0, crossfade_samples)
                segment[-crossfade_samples:] *= fade_out

            result_parts.append(segment)

        return np.concatenate(result_parts)


def process_clip_waveform_only(
    audio_path: str,
    output_path: Optional[str] = None,
    preset: str = "linkedin",
    clip_start: Optional[float] = None,
    clip_end: Optional[float] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Process an audio clip with Silero VAD-based silence removal.

    Args:
        audio_path: Path to input audio file
        output_path: Optional path to save edited audio
        preset: Platform preset ("linkedin", "youtube_shorts", "tiktok", "podcast")
        clip_start: Optional start time to clip (seconds)
        clip_end: Optional end time to clip (seconds)
        config: Optional custom config overrides

    Returns:
        Dict with edit statistics and decisions
    """
    import tempfile
    import os

    # Map string preset to enum
    preset_map = {
        "linkedin": PlatformPreset.LINKEDIN,
        "youtube_shorts": PlatformPreset.YOUTUBE_SHORTS,
        "tiktok": PlatformPreset.TIKTOK,
        "podcast": PlatformPreset.PODCAST,
    }
    preset_enum = preset_map.get(preset, PlatformPreset.LINKEDIN)

    # Create custom config if overrides provided
    base = PRESETS[preset_enum]
    if config:
        preset_config = PresetConfig(
            vad_threshold=config.get("vad_threshold", base.vad_threshold),
            min_silence_ms=config.get("min_silence_ms", base.min_silence_ms),
            max_kept_silence_ms=config.get("max_kept_silence_ms", base.max_kept_silence_ms),
            speech_padding_ms=config.get("speech_padding_ms", base.speech_padding_ms),
            crossfade_ms=config.get("crossfade_ms", base.crossfade_ms),
        )
    else:
        preset_config = base

    # If clip range specified, extract that portion first
    working_path = audio_path
    temp_clip = None

    if clip_start is not None or clip_end is not None:
        import soundfile as sf
        samples, sr = sf.read(audio_path)
        if len(samples.shape) > 1:
            samples = samples.mean(axis=1)

        start_sample = int((clip_start or 0) * sr)
        end_sample = int((clip_end or len(samples) / sr) * sr)

        start_sample = max(0, min(start_sample, len(samples)))
        end_sample = max(0, min(end_sample, len(samples)))

        clipped = samples[start_sample:end_sample]

        # Save to temp file
        temp_clip = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(temp_clip.name, clipped, sr)
        working_path = temp_clip.name

    try:
        # Use Silero VAD for detection
        result = _process_with_silero(working_path, output_path, preset_config, preset_enum)

        # Add metadata to result
        if clip_start is not None or clip_end is not None:
            result["clip_range"] = {
                "start": clip_start or 0,
                "end": clip_end,
            }

        return result

    finally:
        # Clean up temp file
        if temp_clip:
            try:
                os.unlink(temp_clip.name)
            except:
                pass


def _merge_decisions(decisions: List[EditDecision]) -> List[EditDecision]:
    """Merge overlapping edit decisions."""
    if not decisions:
        return []

    merged = []
    current = decisions[0]

    for decision in decisions[1:]:
        # Check for overlap or adjacency
        if decision.start <= current.end + 0.001:  # Small tolerance
            # Merge: extend current to include this decision
            current = EditDecision(
                start=current.start,
                end=max(current.end, decision.end),
                action="keep",
                reason="merged",
                new_duration=max(current.end, decision.end) - current.start,
            )
        else:
            merged.append(current)
            current = decision

    merged.append(current)
    return merged


def _process_with_silero(
    audio_path: str,
    output_path: Optional[str],
    config: PresetConfig,
    preset: PlatformPreset,
) -> Dict[str, Any]:
    """
    Process audio using Silero VAD for silence detection.

    Uses Silero for speech/silence detection and AudioEditor for applying edits.
    """
    # Detect silences using Silero
    vad = SileroVADDetector(config=config)
    silences = vad.detect_silence_segments(audio_path, threshold=config.vad_threshold)
    speech_segments = vad.detect_speech_segments(audio_path, threshold=config.vad_threshold)

    # Create editor for applying edits
    editor = AudioEditor(config)
    editor.load_audio(audio_path)

    # Build edit decisions from Silero results
    audio_duration = len(editor.samples) / editor.sample_rate
    max_kept_silence = config.max_kept_silence_ms / 1000.0
    padding = config.speech_padding_ms / 1000.0

    decisions = []

    # Add speech segments with padding
    for seg in speech_segments:
        padded_start = max(0.0, seg.start - padding)
        padded_end = min(audio_duration, seg.end + padding)
        decisions.append(EditDecision(
            start=padded_start,
            end=padded_end,
            action="keep",
            reason="speech",
            new_duration=padded_end - padded_start,
        ))

    # Handle silences
    for silence in silences:
        if silence.duration > max_kept_silence:
            decisions.append(EditDecision(
                start=silence.start,
                end=silence.start + max_kept_silence,
                action="trim",
                reason=f"silence trimmed from {silence.duration:.2f}s to {max_kept_silence:.2f}s",
                new_duration=max_kept_silence,
            ))
        else:
            decisions.append(EditDecision(
                start=silence.start,
                end=silence.end,
                action="keep",
                reason="short silence kept",
                new_duration=silence.duration,
            ))

    # Sort and merge decisions
    decisions.sort(key=lambda d: d.start)
    decisions = _merge_decisions(decisions)

    # Apply edits
    edited_samples = editor.apply_edits(decisions, output_path)

    # Calculate statistics
    original_duration = len(editor.samples) / editor.sample_rate
    edited_duration = len(edited_samples) / editor.sample_rate if len(edited_samples) > 0 else 0

    return {
        "original_duration": original_duration,
        "edited_duration": edited_duration,
        "time_saved": original_duration - edited_duration,
        "percent_reduction": ((original_duration - edited_duration) / original_duration * 100) if original_duration > 0 else 0,
        "silences_detected": len(silences),
        "speech_segments": len(speech_segments),
        "decisions": [
            {
                "start": d.start,
                "end": d.end,
                "action": d.action,
                "reason": d.reason,
                "original_duration": d.original_duration,
                "new_duration": d.new_duration,
            }
            for d in decisions
        ],
        "preset": preset.value,
        "config": {
            "vad_threshold": config.vad_threshold,
            "min_silence_ms": config.min_silence_ms,
            "max_kept_silence_ms": config.max_kept_silence_ms,
            "speech_padding_ms": config.speech_padding_ms,
            "crossfade_ms": config.crossfade_ms,
        },
    }


def process_clip_with_transcript(
    audio_path: str,
    transcript: Dict[str, Any],
    output_path: Optional[str] = None,
    preset: str = "linkedin",
    clip_start: Optional[float] = None,
    clip_end: Optional[float] = None,
    remove_fillers: bool = True,
    remove_restarts: bool = True,
    remove_opening_false_start: bool = True,
    lead_in_padding_ms: int = 400,
) -> Dict[str, Any]:
    """
    Process audio with intelligent filler and restart removal.

    This combines Silero VAD silence detection with transcript analysis to:
    1. Detect silences using VAD (safe cut points)
    2. Identify fillers (um, uh) and restarts from transcript
    3. Remove fillers/restarts by cutting at nearby silence boundaries
    4. Remove opening false starts (when you start, stop, restart)
    5. Add lead-in padding before actual content starts

    The key insight: We use transcript to identify WHAT to remove, but
    cut at VAD-detected silence points to avoid clipping words.

    Args:
        audio_path: Path to audio file
        transcript: Transcript dict with word-level timestamps
        output_path: Optional output path
        preset: Platform preset
        clip_start: Optional clip start time
        clip_end: Optional clip end time
        remove_fillers: Whether to remove filler words (um, uh)
        remove_restarts: Whether to remove restarts (repeated words)
        remove_opening_false_start: Whether to cut opening false starts
        lead_in_padding_ms: Silence padding before content starts (ms)

    Returns:
        Dict with edit statistics and what was removed
    """
    import tempfile
    import os
    import soundfile as sf

    from src.video.transcript_enhanced_editor import TranscriptEnhancedEditor

    # Map preset
    preset_map = {
        "linkedin": PlatformPreset.LINKEDIN,
        "youtube_shorts": PlatformPreset.YOUTUBE_SHORTS,
        "tiktok": PlatformPreset.TIKTOK,
        "podcast": PlatformPreset.PODCAST,
    }
    preset_enum = preset_map.get(preset, PlatformPreset.LINKEDIN)
    config = PRESETS[preset_enum]

    # Handle clip range
    working_path = audio_path
    temp_clip = None
    time_offset = clip_start or 0

    if clip_start is not None or clip_end is not None:
        samples, sr = sf.read(audio_path)
        if len(samples.shape) > 1:
            samples = samples.mean(axis=1)

        start_sample = int((clip_start or 0) * sr)
        end_sample = int((clip_end or len(samples) / sr) * sr)
        clipped = samples[max(0, start_sample):min(len(samples), end_sample)]

        temp_clip = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(temp_clip.name, clipped, sr)
        working_path = temp_clip.name

    try:
        # Step 1: Get VAD speech segments
        vad = SileroVADDetector(config=config)
        speech_segments = vad.detect_speech_segments(working_path, threshold=config.vad_threshold)
        silences = vad.detect_silence_segments(working_path, threshold=config.vad_threshold)

        # Step 2: Analyze transcript for fillers and restarts
        editor = TranscriptEnhancedEditor()
        analysis = editor.analyze_transcript(transcript, detect_restarts=remove_restarts)

        # Helper function to find a silence gap that contains a region
        def find_containing_silence(region_start: float, region_end: float):
            """
            Find a silence gap that contains or mostly contains a filler/restart.

            Returns the silence segment if found, None otherwise.
            The filler must be mostly within the silence (at least 50% overlap).
            """
            best_silence = None
            best_overlap = 0

            for silence in silences:
                # Calculate overlap between region and silence
                overlap_start = max(region_start, silence.start)
                overlap_end = min(region_end, silence.end)
                overlap = max(0, overlap_end - overlap_start)

                region_duration = region_end - region_start
                if region_duration > 0:
                    overlap_ratio = overlap / region_duration
                    # Filler must be at least 50% within the silence
                    if overlap_ratio >= 0.5 and overlap > best_overlap:
                        best_overlap = overlap
                        best_silence = silence

            return best_silence

        # Get removal regions (adjusted for clip offset)
        # Key insight: We only remove fillers/restarts that fall within VAD silence gaps
        # and we cut at the silence boundaries (not transcript boundaries) to avoid clipping
        removal_regions = []
        skipped_regions = []
        silences_to_fully_remove = set()  # Silence indices that contain fillers

        if remove_fillers:
            for filler in analysis.fillers:
                if filler.is_pure_filler:  # Only pure fillers (um, uh)
                    # Adjust timestamps for clip offset
                    adjusted_start = filler.start - time_offset
                    adjusted_end = filler.end - time_offset
                    if adjusted_start >= 0:  # Within clip range
                        # Find a silence gap that contains this filler
                        containing_silence = find_containing_silence(adjusted_start, adjusted_end)
                        if containing_silence:
                            # Mark this silence for full removal
                            silence_idx = silences.index(containing_silence)
                            silences_to_fully_remove.add(silence_idx)
                            removal_regions.append({
                                "start": adjusted_start,
                                "end": adjusted_end,
                                "type": "filler",
                                "word": filler.word,
                                "silence_start": containing_silence.start,
                                "silence_end": containing_silence.end,
                            })
                        else:
                            skipped_regions.append({
                                "start": adjusted_start,
                                "end": adjusted_end,
                                "type": "filler",
                                "word": filler.word,
                                "reason": "not within a silence gap",
                            })

        if remove_restarts:
            for restart in analysis.restarts:
                adjusted_start = restart.first_start - time_offset
                adjusted_end = restart.last_end - time_offset
                if adjusted_start >= 0:
                    containing_silence = find_containing_silence(adjusted_start, adjusted_end)
                    if containing_silence:
                        silence_idx = silences.index(containing_silence)
                        silences_to_fully_remove.add(silence_idx)
                        removal_regions.append({
                            "start": adjusted_start,
                            "end": adjusted_end,
                            "type": "restart",
                            "word": restart.repeated_word,
                            "silence_start": containing_silence.start,
                            "silence_end": containing_silence.end,
                        })
                    else:
                        skipped_regions.append({
                            "start": adjusted_start,
                            "end": adjusted_end,
                            "type": "restart",
                            "word": restart.repeated_word,
                            "reason": "not within a silence gap",
                        })

        # Handle opening false start
        opening_false_start_info = None
        content_start_time = 0.0  # Where real content begins
        lead_in_padding = lead_in_padding_ms / 1000.0

        if remove_opening_false_start and analysis.opening_false_start:
            fs = analysis.opening_false_start
            adjusted_real_start = fs.real_start - time_offset

            if adjusted_real_start > 0:
                opening_false_start_info = {
                    "words_cut": fs.words_cut,
                    "false_start_end": fs.false_start_end,
                    "real_start": fs.real_start,
                }
                # Content starts at real_start, minus lead-in padding
                content_start_time = max(0, adjusted_real_start - lead_in_padding)

        # Step 3: Build speech segments, excluding removal regions
        # We keep speech segments but mark regions containing fillers/restarts for removal
        audio_editor = AudioEditor(config)
        audio_editor.load_audio(working_path)
        audio_duration = len(audio_editor.samples) / audio_editor.sample_rate

        padding = config.speech_padding_ms / 1000.0
        max_kept_silence = config.max_kept_silence_ms / 1000.0

        decisions = []
        removed_items = []

        # Track if we need to prepend silence for lead-in
        prepend_silence_samples = None

        # If we have an opening false start, we'll need to prepend silence
        if content_start_time > 0 and lead_in_padding > 0:
            # Generate silence samples to prepend (will be added after applying edits)
            prepend_silence_samples = int(lead_in_padding * audio_editor.sample_rate)

        # Build edit decisions
        # Strategy: Keep all speech segments, handle silences based on whether they contain fillers

        # First, add all speech segments (with padding)
        for seg in speech_segments:
            seg_start = seg.start
            seg_end = seg.end

            # Skip segments entirely before content_start_time (false start content)
            if seg_end <= content_start_time:
                if opening_false_start_info:
                    removed_items.append({
                        "type": "opening_false_start",
                        "word": " ".join(opening_false_start_info["words_cut"]),
                        "start": seg_start + time_offset,
                        "end": seg_end + time_offset,
                        "duration": seg_end - seg_start,
                    })
                continue

            # Adjust segment start if it overlaps with content_start_time
            if seg_start < content_start_time:
                seg_start = content_start_time

            # Keep speech with padding
            padded_start = max(content_start_time, seg_start - padding)
            padded_end = min(audio_duration, seg_end + padding)
            decisions.append(EditDecision(
                start=padded_start,
                end=padded_end,
                action="keep",
                reason="speech",
                new_duration=padded_end - padded_start,
            ))

        # Handle silences
        for i, silence in enumerate(silences):
            # Skip silences before content starts
            if silence.end <= content_start_time:
                continue

            # Check if this silence should be fully removed (contains a filler/restart)
            if i in silences_to_fully_remove:
                # Record what we're removing (find the filler in this silence)
                for region in removal_regions:
                    if region.get("silence_start") == silence.start and region.get("silence_end") == silence.end:
                        removed_items.append({
                            "type": region["type"],
                            "word": region["word"],
                            "start": region["start"] + time_offset,
                            "end": region["end"] + time_offset,
                            "duration": region["end"] - region["start"],
                        })
                # Don't add this silence to decisions - it will be removed
                continue
            elif silence.duration > max_kept_silence:
                # Trim long silence
                decisions.append(EditDecision(
                    start=silence.start,
                    end=silence.start + max_kept_silence,
                    action="trim",
                    reason=f"silence trimmed",
                    new_duration=max_kept_silence,
                ))
            else:
                # Keep short silence
                decisions.append(EditDecision(
                    start=silence.start,
                    end=silence.end,
                    action="keep",
                    reason="short silence",
                    new_duration=silence.duration,
                ))

        # Sort and merge decisions
        decisions.sort(key=lambda d: d.start)
        decisions = _merge_decisions(decisions)

        # Apply edits (don't save yet if we need to prepend silence)
        edited_samples = audio_editor.apply_edits(decisions, output_path=None)

        # Prepend lead-in silence if needed
        if prepend_silence_samples and len(edited_samples) > 0:
            silence = np.zeros(prepend_silence_samples)
            edited_samples = np.concatenate([silence, edited_samples])

        # Save the final result
        if output_path and len(edited_samples) > 0:
            import soundfile as sf
            sf.write(output_path, edited_samples, audio_editor.sample_rate)

        # Calculate stats
        original_duration = len(audio_editor.samples) / audio_editor.sample_rate
        edited_duration = len(edited_samples) / audio_editor.sample_rate if len(edited_samples) > 0 else 0

        return {
            "original_duration": original_duration,
            "edited_duration": edited_duration,
            "time_saved": original_duration - edited_duration,
            "percent_reduction": ((original_duration - edited_duration) / original_duration * 100) if original_duration > 0 else 0,
            "silences_detected": len(silences),
            "speech_segments": len(speech_segments),
            "fillers_found": len([f for f in analysis.fillers if f.is_pure_filler]),
            "restarts_found": len(analysis.restarts),
            "removed_items": removed_items,
            "skipped_items": skipped_regions,
            "opening_false_start": opening_false_start_info,
            "lead_in_padding_ms": lead_in_padding_ms if opening_false_start_info else 0,
            "preset": preset,
        }

    finally:
        if temp_clip:
            try:
                os.unlink(temp_clip.name)
            except:
                pass


def get_vad_analysis(
    audio_path: str,
    preset: str = "linkedin",
    use_cache: bool = True,
) -> Dict[str, Any]:
    """
    Get VAD analysis for an audio file (cached for efficiency).

    This runs Silero VAD once and caches the results. Subsequent calls
    with the same audio_path return cached data instantly.

    Args:
        audio_path: Path to audio file
        preset: Platform preset (affects min_silence_ms threshold)
        use_cache: Whether to use cached results

    Returns:
        Dict with speech_segments, silences, duration, and preset config
    """
    global _vad_cache

    cache_key = f"{audio_path}:{preset}"

    if use_cache and cache_key in _vad_cache:
        return _vad_cache[cache_key]

    # Get preset config
    preset_map = {
        "linkedin": PlatformPreset.LINKEDIN,
        "youtube_shorts": PlatformPreset.YOUTUBE_SHORTS,
        "tiktok": PlatformPreset.TIKTOK,
        "podcast": PlatformPreset.PODCAST,
    }
    preset_enum = preset_map.get(preset, PlatformPreset.LINKEDIN)
    config = PRESETS[preset_enum]

    # Run VAD
    vad = SileroVADDetector(config=config)
    speech_segments = vad.detect_speech_segments(audio_path, threshold=config.vad_threshold)
    silences = vad.detect_silence_segments(audio_path, threshold=config.vad_threshold)

    # Get audio duration
    import torchaudio
    info = torchaudio.info(audio_path)
    duration = info.num_frames / info.sample_rate

    result = {
        "speech_segments": speech_segments,
        "silences": silences,
        "duration": duration,
        "config": config,
        "preset": preset,
    }

    if use_cache:
        _vad_cache[cache_key] = result

    return result


def estimate_edited_duration(
    audio_path: str,
    start: float = 0.0,
    end: Optional[float] = None,
    preset: str = "linkedin",
) -> Dict[str, Any]:
    """
    Estimate duration after silence removal WITHOUT rendering audio.

    This is a fast function for clip selection. It uses cached VAD data
    to calculate what the duration would be after applying a preset's
    silence removal settings.

    Args:
        audio_path: Path to audio file
        start: Start time in seconds (default: 0)
        end: End time in seconds (default: full duration)
        preset: Platform preset to simulate

    Returns:
        Dict with:
            - original_duration: Duration of the selected range
            - estimated_duration: Duration after silence removal
            - time_saved: Seconds that would be removed
            - percent_reduction: Percentage reduction
            - speech_time: Total speech time in range
            - silence_time: Total silence time in range
            - silences_in_range: Number of silence segments in range
    """
    # Get cached VAD analysis
    analysis = get_vad_analysis(audio_path, preset=preset)
    config = analysis["config"]
    full_duration = analysis["duration"]

    # Default end to full duration
    if end is None:
        end = full_duration

    # Clamp to valid range
    start = max(0.0, min(start, full_duration))
    end = max(start, min(end, full_duration))

    original_duration = end - start

    if original_duration <= 0:
        return {
            "original_duration": 0,
            "estimated_duration": 0,
            "time_saved": 0,
            "percent_reduction": 0,
            "speech_time": 0,
            "silence_time": 0,
            "silences_in_range": 0,
        }

    # Calculate silence handling in range
    # This mimics what the actual processor does:
    # - Keep all speech
    # - Trim long silences to max_kept_silence
    max_kept_silence = config.max_kept_silence_ms / 1000.0

    # Calculate speech time in range (for reporting)
    speech_time = 0.0
    for seg in analysis["speech_segments"]:
        seg_start = max(seg.start, start)
        seg_end = min(seg.end, end)
        if seg_end > seg_start:
            speech_time += (seg_end - seg_start)

    # Calculate silence time and what gets trimmed
    silence_time_original = 0.0
    time_removed = 0.0
    silences_in_range = 0

    for silence in analysis["silences"]:
        # Check overlap with our range
        sil_start = max(silence.start, start)
        sil_end = min(silence.end, end)
        if sil_end > sil_start:
            silences_in_range += 1
            sil_duration = sil_end - sil_start
            silence_time_original += sil_duration

            # If silence is longer than max, we trim off the excess
            if sil_duration > max_kept_silence:
                time_removed += (sil_duration - max_kept_silence)

    # Estimated duration = original - time removed from silences
    estimated_duration = original_duration - time_removed

    time_saved = time_removed
    percent_reduction = (time_saved / original_duration * 100) if original_duration > 0 else 0

    return {
        "original_duration": round(original_duration, 2),
        "estimated_duration": round(estimated_duration, 2),
        "time_saved": round(time_saved, 2),
        "percent_reduction": round(percent_reduction, 1),
        "speech_time": round(speech_time, 2),
        "silence_time": round(silence_time_original, 2),
        "silences_in_range": silences_in_range,
    }


def estimate_all_presets(
    audio_path: str,
    start: float = 0.0,
    end: Optional[float] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Estimate duration for all presets at once.

    Useful for showing the user how long a clip would be on each platform.

    Args:
        audio_path: Path to audio file
        start: Start time in seconds
        end: End time in seconds

    Returns:
        Dict keyed by preset name with estimation results
    """
    results = {}
    for preset in ["linkedin", "youtube_shorts", "tiktok", "podcast"]:
        results[preset] = estimate_edited_duration(audio_path, start, end, preset)
    return results


def clear_vad_cache(audio_path: Optional[str] = None) -> None:
    """
    Clear the VAD cache.

    Args:
        audio_path: If provided, only clear cache for this file.
                   If None, clear entire cache.
    """
    global _vad_cache
    if audio_path:
        keys_to_remove = [k for k in _vad_cache if k.startswith(audio_path)]
        for key in keys_to_remove:
            del _vad_cache[key]
    else:
        _vad_cache.clear()


if __name__ == "__main__":
    import sys
    import glob

    print("Silero VAD Silence Remover - Test Mode")
    print("=" * 60)

    # Test with sample audio if available
    test_audio = "data/audio"
    wav_files = glob.glob(f"{test_audio}/*.wav")

    if wav_files:
        audio_path = wav_files[0]
        print(f"Testing with: {audio_path}")

        for preset_name in ["linkedin", "youtube_shorts", "tiktok", "podcast"]:
            print(f"\n{preset_name.upper()} preset:")
            print("-" * 40)

            result = process_clip_waveform_only(
                audio_path=audio_path,
                preset=preset_name,
            )

            print(f"Original duration: {result['original_duration']:.1f}s")
            print(f"Edited duration: {result['edited_duration']:.1f}s")
            print(f"Time saved: {result['time_saved']:.1f}s ({result['percent_reduction']:.1f}%)")
            print(f"Silences detected: {result['silences_detected']}")
            print(f"Speech segments: {result['speech_segments']}")
    else:
        print(f"No WAV files found in {test_audio}/")
        print("Usage: python -m src.video.waveform_silence_remover")
