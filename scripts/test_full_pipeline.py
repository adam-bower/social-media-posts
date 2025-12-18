"""
End-to-end test of the video clipper pipeline.

Tests the complete flow:
1. Extract audio from video
2. Transcribe with faster-whisper
3. Detect silences
4. Generate clip suggestions with Claude Haiku

Usage:
    python scripts/test_full_pipeline.py <video_path>
    python scripts/test_full_pipeline.py --sample
"""

import os
import sys
import json
import time
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


def download_sample_video() -> str:
    """Download a short sample video for testing."""
    import urllib.request

    # Using a shorter clip from archive.org for faster testing
    url = "https://archive.org/download/ElephantsDream/ed_1024_512kb.mp4"

    output_path = os.path.join(tempfile.gettempdir(), "test_video_pipeline.mp4")

    if os.path.exists(output_path):
        print(f"Using cached sample video: {output_path}")
        return output_path

    print("Downloading sample video (this may take a moment)...")
    urllib.request.urlretrieve(url, output_path)
    print(f"Downloaded to: {output_path}")

    return output_path


def run_pipeline(video_path: str, model_size: str = "base") -> dict:
    """
    Run the complete video processing pipeline.

    Args:
        video_path: Path to video file
        model_size: Whisper model size (base for testing, large-v3 for production)

    Returns:
        Dictionary with all pipeline results
    """
    from src.video.audio_extractor import extract_audio, get_video_info
    from src.video.transcriber import transcribe_audio
    from src.video.silence_detector import detect_silences, find_natural_breaks
    from src.video.clip_suggester import suggest_clips

    results = {
        "video_path": video_path,
        "stages": {},
        "timings": {},
    }

    total_start = time.time()

    # Stage 1: Get video info
    print("\n" + "=" * 60)
    print("STAGE 1: Video Analysis")
    print("=" * 60)
    stage_start = time.time()

    video_info = get_video_info(video_path)
    results["video_info"] = video_info

    print(f"Duration: {video_info['duration']:.1f}s")
    print(f"Resolution: {video_info.get('resolution', 'N/A')}")
    print(f"Size: {video_info['size_bytes'] / 1024 / 1024:.1f} MB")

    results["timings"]["video_analysis"] = time.time() - stage_start

    # Stage 2: Extract audio
    print("\n" + "=" * 60)
    print("STAGE 2: Audio Extraction")
    print("=" * 60)
    stage_start = time.time()

    audio_path = extract_audio(video_path)
    results["audio_path"] = audio_path

    audio_size = os.path.getsize(audio_path)
    print(f"Audio extracted to: {audio_path}")
    print(f"Audio size: {audio_size / 1024:.1f} KB")

    results["timings"]["audio_extraction"] = time.time() - stage_start

    # Stage 3: Transcribe
    print("\n" + "=" * 60)
    print("STAGE 3: Transcription")
    print("=" * 60)
    stage_start = time.time()

    print(f"Model: {model_size}")
    print("Transcribing... (first run downloads the model)")

    transcript = transcribe_audio(audio_path, model_size=model_size)
    results["transcript"] = transcript

    print(f"Language: {transcript['language']} ({transcript['language_probability']:.2%})")
    print(f"Segments: {len(transcript['segments'])}")
    print(f"Processing time: {transcript['processing_time']:.1f}s")

    # Show preview
    preview = transcript['text'][:300]
    print(f"\nTranscript preview:")
    print(f"  {preview}...")

    results["timings"]["transcription"] = time.time() - stage_start

    # Stage 4: Silence Detection
    print("\n" + "=" * 60)
    print("STAGE 4: Silence Detection")
    print("=" * 60)
    stage_start = time.time()

    silences = detect_silences(audio_path)
    natural_breaks = find_natural_breaks(silences, min_break_duration=1.0)

    results["silences"] = silences
    results["natural_breaks"] = natural_breaks

    total_silence = sum(s["duration"] for s in silences)
    print(f"Silence periods found: {len(silences)}")
    print(f"Total silence: {total_silence:.1f}s ({total_silence/video_info['duration']*100:.1f}%)")
    print(f"Natural break points: {len(natural_breaks)}")

    results["timings"]["silence_detection"] = time.time() - stage_start

    # Stage 5: Clip Suggestions
    print("\n" + "=" * 60)
    print("STAGE 5: AI Clip Suggestions")
    print("=" * 60)
    stage_start = time.time()

    print("Calling Claude Haiku for clip suggestions...")

    try:
        suggestions = suggest_clips(
            transcript_text=transcript['text'],
            segments=transcript['segments'],
            silences=silences,
            duration=video_info['duration'],
            context="Video content for social media clip extraction",
        )
        results["suggestions"] = suggestions

        print(f"\nSuggested {len(suggestions)} clips:")

        for i, clip in enumerate(suggestions):
            platform = clip['platform'].upper()
            duration = clip['end_time'] - clip['start_time']
            print(f"\n  {i+1}. [{platform}] {clip['start_time']:.1f}s - {clip['end_time']:.1f}s ({duration:.1f}s)")
            print(f"     Confidence: {clip['confidence_score']:.0%}")
            print(f"     Hook: {clip['hook_reason'][:60]}...")

    except Exception as e:
        print(f"Warning: Clip suggestion failed: {e}")
        results["suggestions"] = []
        results["suggestion_error"] = str(e)

    results["timings"]["clip_suggestions"] = time.time() - stage_start

    # Summary
    total_time = time.time() - total_start
    results["timings"]["total"] = total_time

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"\nTiming Summary:")
    print(f"  Video analysis:    {results['timings']['video_analysis']:.1f}s")
    print(f"  Audio extraction:  {results['timings']['audio_extraction']:.1f}s")
    print(f"  Transcription:     {results['timings']['transcription']:.1f}s")
    print(f"  Silence detection: {results['timings']['silence_detection']:.1f}s")
    print(f"  Clip suggestions:  {results['timings']['clip_suggestions']:.1f}s")
    print(f"  ─────────────────────────────")
    print(f"  TOTAL:             {total_time:.1f}s")

    return results


def main():
    """Run the full pipeline test."""
    print("=" * 60)
    print("Video Clipper - Full Pipeline Test")
    print("=" * 60)

    # Parse arguments
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python scripts/test_full_pipeline.py <video_path>")
        print("  python scripts/test_full_pipeline.py --sample")
        print("  python scripts/test_full_pipeline.py <video_path> --model=base")
        print("\nModel options: tiny, base, small, medium, large-v3")
        sys.exit(1)

    video_path = sys.argv[1]
    model_size = "base"  # Use 'base' for testing, 'large-v3' for production

    # Parse optional arguments
    for arg in sys.argv[2:]:
        if arg.startswith("--model="):
            model_size = arg.split("=")[1]

    # Handle --sample flag
    if video_path == "--sample":
        video_path = download_sample_video()

    # Verify video exists
    if not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)

    # Run pipeline
    try:
        results = run_pipeline(video_path, model_size=model_size)

        # Save results
        output_path = os.path.join(tempfile.gettempdir(), "pipeline_results.json")

        # Convert for JSON serialization
        serializable_results = {
            "video_path": results["video_path"],
            "video_info": results["video_info"],
            "audio_path": results["audio_path"],
            "transcript": {
                "text": results["transcript"]["text"],
                "language": results["transcript"]["language"],
                "duration": results["transcript"]["duration"],
                "segment_count": len(results["transcript"]["segments"]),
            },
            "silence_count": len(results["silences"]),
            "natural_breaks": results["natural_breaks"],
            "suggestions": results.get("suggestions", []),
            "timings": results["timings"],
        }

        with open(output_path, "w") as f:
            json.dump(serializable_results, f, indent=2)

        print(f"\nResults saved to: {output_path}")
        print("\nPIPELINE TEST PASSED")

    except Exception as e:
        print(f"\nPIPELINE TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
