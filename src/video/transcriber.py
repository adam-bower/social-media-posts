"""
Transcription with word-level timestamps.

Supports three backends:
1. Deepgram API (BEST for filler detection - um, uh, like, you know) - DEFAULT
2. OpenAI Whisper API (fast, good accuracy)
3. Local faster-whisper (free, slower on CPU)

Usage:
    from src.video.transcriber import transcribe_audio
    result = transcribe_audio("audio.wav")  # Uses Deepgram by default
    result = transcribe_audio("audio.wav", backend="openai")
    result = transcribe_audio("audio.wav", backend="local")
"""

import os
import time
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()


def transcribe_audio_deepgram(
    audio_path: str,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Transcribe audio using Deepgram API with filler word detection.

    Best for capturing um, uh, like, you know, etc.

    Args:
        audio_path: Path to audio file
        language: Optional language code (auto-detected if None)

    Returns:
        Dict with text, segments, language, etc.
    """
    import requests

    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        raise ValueError("DEEPGRAM_API_KEY not found")

    start_time = time.time()

    # Read audio file
    with open(audio_path, "rb") as f:
        audio_data = f.read()

    # Determine content type
    ext = os.path.splitext(audio_path)[1].lower()
    content_types = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
        ".ogg": "audio/ogg",
    }
    content_type = content_types.get(ext, "audio/wav")

    # Build request
    params = {
        "model": "nova-2",
        "filler_words": "true",  # KEY: Preserve um, uh, like, you know
        "smart_format": "true",
        "punctuate": "true",
        "utterances": "true",
        "words": "true",  # Word-level timestamps
    }
    if language:
        params["language"] = language

    url = "https://api.deepgram.com/v1/listen?" + "&".join(f"{k}={v}" for k, v in params.items())

    response = requests.post(
        url,
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": content_type,
        },
        data=audio_data,
        timeout=300,
    )
    response.raise_for_status()
    result = response.json()

    processing_time = time.time() - start_time

    # Parse response
    channels = result.get("results", {}).get("channels", [])
    if not channels:
        return {
            "text": "",
            "segments": [],
            "language": language or "en",
            "language_probability": 0,
            "duration": 0,
            "processing_time": processing_time,
            "model": "deepgram-nova-2",
        }

    alternatives = channels[0].get("alternatives", [])
    if not alternatives:
        return {
            "text": "",
            "segments": [],
            "language": language or "en",
            "language_probability": 0,
            "duration": 0,
            "processing_time": processing_time,
            "model": "deepgram-nova-2",
        }

    transcript_data = alternatives[0]
    full_text = transcript_data.get("transcript", "")
    words = transcript_data.get("words", [])

    # Get duration from metadata
    metadata = result.get("metadata", {})
    duration = metadata.get("duration", 0)
    detected_language = metadata.get("detected_language", language or "en")

    # Build segments from utterances or words
    utterances = result.get("results", {}).get("utterances", [])

    segments = []
    if utterances:
        # Use utterances as segments
        for utt in utterances:
            seg_start = utt.get("start", 0)
            seg_end = utt.get("end", 0)
            seg_text = utt.get("transcript", "")

            # Find words that belong to this utterance
            seg_words = []
            for w in words:
                w_start = w.get("start", 0)
                w_end = w.get("end", 0)
                if w_start >= seg_start and w_end <= seg_end + 0.1:
                    seg_words.append({
                        "word": w.get("punctuated_word", w.get("word", "")),
                        "start": w_start,
                        "end": w_end,
                        "confidence": w.get("confidence", 0),
                    })

            segments.append({
                "start": seg_start,
                "end": seg_end,
                "text": seg_text,
                "words": seg_words,
            })
    else:
        # Fallback: create one segment with all words
        if words:
            segments.append({
                "start": words[0].get("start", 0),
                "end": words[-1].get("end", 0),
                "text": full_text,
                "words": [
                    {
                        "word": w.get("punctuated_word", w.get("word", "")),
                        "start": w.get("start", 0),
                        "end": w.get("end", 0),
                        "confidence": w.get("confidence", 0),
                    }
                    for w in words
                ],
            })

    return {
        "text": full_text,
        "segments": segments,
        "language": detected_language,
        "language_probability": 1.0,
        "duration": duration,
        "processing_time": processing_time,
        "model": "deepgram-nova-2",
    }


def transcribe_audio_openai(
    audio_path: str,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Transcribe audio using OpenAI Whisper API.

    Fast and accurate, captures filler words (um, uh, etc.)

    Args:
        audio_path: Path to audio file
        language: Optional language code (auto-detected if None)

    Returns:
        Dict with text, segments, language, etc.
    """
    import openai

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found")

    client = openai.OpenAI(api_key=api_key)

    start_time = time.time()

    with open(audio_path, "rb") as audio_file:
        # Use verbose_json to get word-level timestamps
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
            language=language,
        )

    processing_time = time.time() - start_time

    # Convert OpenAI response to our format
    # Note: OpenAI returns Pydantic models, not dicts - use attribute access
    segments = []
    for seg in response.segments or []:
        segment_data = {
            "start": getattr(seg, "start", 0),
            "end": getattr(seg, "end", 0),
            "text": getattr(seg, "text", "").strip(),
            "words": [],
        }
        segments.append(segment_data)

    # Add word-level timestamps
    if response.words:
        word_idx = 0
        for seg in segments:
            seg_words = []
            while word_idx < len(response.words):
                word = response.words[word_idx]
                word_start = getattr(word, "start", 0)
                word_end = getattr(word, "end", 0)

                # Check if word belongs to this segment
                if word_start >= seg["start"] and word_end <= seg["end"] + 0.5:
                    seg_words.append({
                        "word": getattr(word, "word", ""),
                        "start": word_start,
                        "end": word_end,
                    })
                    word_idx += 1
                elif word_start > seg["end"] + 0.5:
                    break
                else:
                    word_idx += 1

            seg["words"] = seg_words

    return {
        "text": response.text,
        "segments": segments,
        "language": response.language or "en",
        "language_probability": 1.0,
        "duration": response.duration or 0,
        "processing_time": processing_time,
        "model": "whisper-1-api",
    }


def transcribe_audio_local(
    audio_path: str,
    model_size: str = "large-v3",
    compute_type: str = "int8",
    language: Optional[str] = None,
    vad_filter: bool = True,
    vad_min_silence_ms: int = 500,
) -> Dict[str, Any]:
    """
    Transcribe audio file locally with faster-whisper.

    Args:
        audio_path: Path to audio file (wav, mp3, m4a, etc.)
        model_size: Whisper model size (tiny, base, small, medium, large-v3)
        compute_type: Quantization type (int8, float16, float32)
        language: Optional language code (e.g., 'en'). Auto-detected if None.
        vad_filter: Enable Voice Activity Detection to skip silence
        vad_min_silence_ms: Minimum silence duration to filter (ms)

    Returns:
        Dictionary with text, segments, language, etc.
    """
    from faster_whisper import WhisperModel

    start_time = time.time()

    # Initialize model
    cache_dir = os.getenv("WHISPER_MODEL_CACHE")
    model = WhisperModel(
        model_size,
        device="auto",
        compute_type=compute_type,
        download_root=cache_dir,
    )

    # Configure VAD parameters
    vad_parameters = None
    if vad_filter:
        vad_parameters = {
            "min_silence_duration_ms": vad_min_silence_ms,
        }

    # Transcribe with word timestamps
    segments_generator, info = model.transcribe(
        audio_path,
        word_timestamps=True,
        vad_filter=vad_filter,
        vad_parameters=vad_parameters,
        language=language,
    )

    # Convert generator to list and extract data
    segments = []
    full_text_parts = []

    for segment in segments_generator:
        segment_data = {
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
            "confidence": segment.avg_logprob,
        }

        # Extract word-level timestamps if available
        if segment.words:
            segment_data["words"] = [
                {
                    "word": word.word.strip(),
                    "start": word.start,
                    "end": word.end,
                    "confidence": word.probability,
                }
                for word in segment.words
            ]

        segments.append(segment_data)
        full_text_parts.append(segment.text.strip())

    processing_time = time.time() - start_time

    return {
        "text": " ".join(full_text_parts),
        "segments": segments,
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
        "processing_time": processing_time,
        "model": model_size,
    }


def transcribe_audio(
    audio_path: str,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Transcribe audio file with word-level timestamps using Deepgram.

    Deepgram is the only backend - best filler word detection (um, uh, like, you know).

    Args:
        audio_path: Path to audio file
        language: Optional language code (auto-detected if None)

    Returns:
        Dictionary with text, segments, language, duration, etc.
    """
    return transcribe_audio_deepgram(audio_path, language)


def main(audio_path: str) -> Dict[str, Any]:
    """Windmill-compatible entry point for transcription."""
    return transcribe_audio(audio_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.video.transcriber <audio_path>")
        print("Example: python -m src.video.transcriber /path/to/audio.wav")
        sys.exit(1)

    audio_path = sys.argv[1]
    print(f"Transcribing: {audio_path}")
    print("-" * 60)

    result = transcribe_audio(audio_path)

    print(f"Language: {result['language']}")
    print(f"Duration: {result['duration']:.1f}s")
    print(f"Processing time: {result['processing_time']:.1f}s")
    print(f"Segments: {len(result['segments'])}")
    print(f"Model: {result['model']}")
    print("-" * 60)
    print("Transcript:")
    print(result['text'][:500] + "..." if len(result['text']) > 500 else result['text'])
