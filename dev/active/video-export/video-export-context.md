# Video Export Context

**Last Updated**: 2025-12-18 21:00 UTC

## Key Files

### Existing (to integrate with)
- `src/video/waveform_silence_remover.py` - EditDecision dataclass, silence removal logic
- `src/video/transcriber.py` - Whisper/Deepgram transcription with word-level timestamps
- `src/video/audio_extractor.py` - FFmpeg audio extraction, ffprobe metadata
- `src/video/audio_assembler.py` - Audio segment assembly with crossfades
- `api/database.py` - Supabase database operations

### To Create
- `src/video/export_formats.py` - Platform format definitions
- `src/video/frame_sampler.py` - FFmpeg frame extraction
- `src/video/vision_detector.py` - Qwen VL integration
- `src/video/crop_calculator.py` - Crop region calculation
- `src/video/edit_sync.py` - Audio-to-video segment mapping
- `src/video/caption_generator.py` - ASS subtitle generation
- `src/video/caption_styles.py` - Platform-specific caption styling
- `src/video/video_renderer.py` - FFmpeg rendering pipeline
- `api/routes/render.py` - API endpoints

## Architecture Notes

### Pipeline Flow
```
1. Clip selected (start/end timestamps)
2. Audio processed (silence removal) → EditDecisions stored
3. Frames extracted from clip → sent to Qwen VL
4. Subject detected → crop regions calculated per format
5. Confidence scored → auto-approve or flag for review
6. When rendering requested:
   a. Map EditDecisions to video segments
   b. Generate ASS captions from word timestamps
   c. FFmpeg: trim segments → concat → crop → scale → burn captions → mux audio
```

### Vision AI Integration
- Qwen VL at `vision.ab-civil.com`
- Configured in .env: `QWEN_VISION_URL`, `QWEN_VISION_API_KEY`
- Send base64-encoded JPEG frames
- Returns subject position in normalized coordinates (0-1)

### Caption Safe Zones
| Platform | Bottom Margin | Caption Position |
|----------|---------------|------------------|
| TikTok | 367px (19%) | Center-middle |
| LinkedIn | 100px | Bottom third |
| YouTube Shorts | 367px (19%) | Center-middle |

## Decisions Made

- **Static crop only for MVP**: Talking-head videos have minimal movement. Tracking can be added later if needed.
- **Sparse-first sampling**: 5 frames (start, 25%, 50%, 75%, end) is enough for static speakers. Auto-retry with dense (1fps) if movement detected.
- **Reuse EditDecisions**: The existing waveform_silence_remover already produces edit decisions. Map them directly to video frames.
- **Conservative auto-approve**: 85% threshold prevents bad crops. Users can always override.
- **Burned-in captions required**: 91% longer watch time, 40% engagement boost. Karaoke-style word highlighting.
- **Font choice**: Montserrat Bold with outline for TikTok, Helvetica for LinkedIn.

## Important Patterns

### FFmpeg Commands Already Used
```python
# From audio_extractor.py
subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", ...])
subprocess.run(["ffmpeg", "-y", "-i", input_path, "-vn", "-ar", "16000", ...])

# From audio_assembler.py
subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list, ...])
```

### Windmill-Compatible Pattern
```python
def main(
    param1: str,
    param2: int = 30,
) -> Dict[str, Any]:
    """Docstring with args/returns."""
    # ... logic ...
    return {"success": True, "result": data}
```

## Test Data

- `data/video/C0044.MP4` - 11-minute 1080p test video
- `data/audio/C0044.wav` - Extracted audio
- `data/audio/C0044_full_transcript.json` - Full transcript with word timestamps
- User will record 4K videos going forward

## Next Steps

1. Create `export_formats.py` with platform definitions
2. Create `frame_sampler.py` for FFmpeg frame extraction
3. Create `vision_detector.py` for Qwen VL integration
4. Test subject detection on C0044.MP4 frames
