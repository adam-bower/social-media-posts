"""
Test script for video transcription pipeline.

Tests:
1. Audio extraction from video
2. Transcription with faster-whisper
3. Word-level timestamp extraction

Usage:
    python scripts/test_transcribe.py <video_path>
    python scripts/test_transcribe.py --sample  # Download and test with sample video
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


def download_sample_video() -> str:
    """Download a short sample video for testing."""
    import urllib.request

    # Use a short public domain video
    # This is a 10-second test video from archive.org
    url = "https://archive.org/download/ElephantsDream/ed_1024_512kb.mp4"

    output_path = os.path.join(tempfile.gettempdir(), "test_video.mp4")

    if os.path.exists(output_path):
        print(f"Using cached sample video: {output_path}")
        return output_path

    print(f"Downloading sample video...")
    print(f"URL: {url}")

    urllib.request.urlretrieve(url, output_path)
    print(f"Downloaded to: {output_path}")

    return output_path


def test_audio_extraction(video_path: str) -> str:
    """Test audio extraction from video."""
    print("\n" + "=" * 60)
    print("STEP 1: Audio Extraction")
    print("=" * 60)

    from src.video.audio_extractor import extract_audio, get_video_info

    # Get video info
    print(f"\nVideo file: {video_path}")
    info = get_video_info(video_path)
    print(f"Duration: {info['duration']:.1f}s")
    print(f"Resolution: {info.get('resolution', 'N/A')}")
    print(f"Size: {info['size_bytes'] / 1024 / 1024:.1f} MB")

    # Extract audio
    print("\nExtracting audio...")
    audio_path = extract_audio(video_path)
    print(f"Audio extracted to: {audio_path}")

    audio_size = os.path.getsize(audio_path)
    print(f"Audio size: {audio_size / 1024:.1f} KB")

    return audio_path


def test_transcription(audio_path: str, model_size: str = "base") -> dict:
    """Test transcription with faster-whisper."""
    print("\n" + "=" * 60)
    print("STEP 2: Transcription")
    print("=" * 60)

    from src.video.transcriber import transcribe_audio

    print(f"\nAudio file: {audio_path}")
    print(f"Model: {model_size}")
    print("Transcribing... (this may take a moment on first run to download the model)")

    result = transcribe_audio(audio_path, model_size=model_size)

    print(f"\nLanguage: {result['language']} ({result['language_probability']:.2%})")
    print(f"Duration: {result['duration']:.1f}s")
    print(f"Processing time: {result['processing_time']:.1f}s")
    print(f"Segments: {len(result['segments'])}")

    print("\n" + "-" * 40)
    print("TRANSCRIPT:")
    print("-" * 40)
    print(result['text'][:1000])
    if len(result['text']) > 1000:
        print(f"\n... (truncated, full text is {len(result['text'])} chars)")

    # Show a sample segment with word timestamps
    if result['segments']:
        print("\n" + "-" * 40)
        print("SAMPLE SEGMENT (with word timestamps):")
        print("-" * 40)
        segment = result['segments'][0]
        print(f"Time: {segment['start']:.2f}s - {segment['end']:.2f}s")
        print(f"Text: {segment['text']}")
        if segment.get('words'):
            print("Words:")
            for word in segment['words'][:10]:
                print(f"  [{word['start']:.2f}-{word['end']:.2f}] {word['word']}")
            if len(segment['words']) > 10:
                print(f"  ... and {len(segment['words']) - 10} more words")

    return result


def main():
    """Run the transcription test."""
    print("=" * 60)
    print("Video Clipper - Transcription Test")
    print("=" * 60)

    # Parse arguments
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python scripts/test_transcribe.py <video_path>")
        print("  python scripts/test_transcribe.py --sample")
        print("  python scripts/test_transcribe.py <video_path> --model=base")
        print("\nModel options: tiny, base, small, medium, large-v3")
        sys.exit(1)

    video_path = sys.argv[1]
    model_size = "base"  # Use 'base' for testing (faster), 'large-v3' for production

    # Parse optional model argument
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

    # Run tests
    try:
        audio_path = test_audio_extraction(video_path)
        result = test_transcription(audio_path, model_size=model_size)

        # Save result to JSON
        output_path = os.path.join(tempfile.gettempdir(), "transcription_result.json")
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nFull result saved to: {output_path}")

        print("\n" + "=" * 60)
        print("TEST PASSED")
        print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
