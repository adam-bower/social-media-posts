# Video Export Implementation Plan

## Overview

Add video export capabilities with AI-powered subject detection for smart cropping and burned-in captions. Export clips to multiple platform formats (TikTok, LinkedIn, YouTube Shorts) with edited audio synced to video.

## Goals

- Export videos with AI-detected crop regions for optimal framing
- Sync edited audio (silence removed) with video frames
- Burn in styled captions with word-by-word highlighting
- Support multiple output formats: 9:16, 1:1, 16:9
- Auto-approve crops when confidence is high, flag for review otherwise

## Target Formats

| Format | Aspect | Resolution | Use Case |
|--------|--------|------------|----------|
| TikTok/Reels | 9:16 | 1080x1920 | Vertical short-form |
| LinkedIn Feed | 1:1 | 1080x1080 | Square feed posts |
| YouTube Shorts | 9:16 | 1080x1920 | Vertical short-form |
| Original | 16:9 | Source | Full video clips |

## Technical Approach

1. **Frame Sampling**: Extract 5 frames (sparse) from clip for analysis
2. **Subject Detection**: Use Qwen VL at vision.ab-civil.com to detect speaker position
3. **Crop Calculation**: Center crop on subject with platform-specific positioning
4. **Audio-Video Sync**: Map existing EditDecisions to video frame segments
5. **Caption Generation**: Generate ASS subtitles from word-level timestamps
6. **Video Rendering**: FFmpeg filter_complex for crop, scale, caption burning

## Files to Create

```
src/video/
    export_formats.py        # Platform format definitions
    frame_sampler.py         # FFmpeg frame extraction
    vision_detector.py       # Qwen VL integration
    crop_calculator.py       # Crop region calculation
    edit_sync.py             # Audio-to-video segment mapping
    caption_generator.py     # ASS subtitle generation
    caption_styles.py        # Platform-specific caption styling
    video_renderer.py        # FFmpeg rendering pipeline

api/routes/
    render.py                # Video rendering endpoints
```

## Files to Modify

- `api/database.py` - Add crop_analysis, edit_decisions columns
- `api/routes/__init__.py` - Register render routes

## Dependencies

- **Qwen VL** at vision.ab-civil.com - Subject detection (configured in .env)
- **FFmpeg** - Video processing, subtitle burning
- **Montserrat font** - Caption styling (may need to bundle)
- **Existing**: waveform_silence_remover.py (EditDecision), transcriber.py (word timestamps)

## Success Criteria

- [ ] Extract frames from video and detect subject position via Qwen VL
- [ ] Calculate optimal crop regions for all 4 formats
- [ ] Confidence scoring works (85%+ auto-approve, <70% flag for review)
- [ ] Audio edits map correctly to video segments
- [ ] Generate styled ASS captions with karaoke word highlighting
- [ ] Render complete video with crop, captions, and edited audio
- [ ] End-to-end workflow from clip selection to multi-format export
