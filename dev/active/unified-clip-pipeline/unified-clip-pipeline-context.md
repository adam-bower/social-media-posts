# Unified Clip Pipeline Context

**Last Updated**: 2025-12-18 23:30 UTC

## Key Files

### From waveform-silence-removal
- `src/video/waveform_silence_remover.py` - Silero VAD silence detection, platform presets
- `src/video/transcript_enhanced_editor.py` - Filler/restart detection
- `src/video/audio_assembler.py` - Audio segment assembly with crossfades
- `src/video/audio_extractor.py` - FFmpeg audio extraction

### From video-export
- `src/video/export_formats.py` - Platform format definitions (TikTok, LinkedIn, etc.)
- `src/video/frame_sampler.py` - FFmpeg frame extraction
- `src/video/vision_detector.py` - Gemini Flash 2.5 subject detection
- `src/video/crop_calculator.py` - Crop region calculation
- `src/video/edit_sync.py` - Audio-to-video edit mapping
- `src/video/caption_styles.py` - Platform caption styling
- `src/video/caption_generator.py` - ASS subtitle generation
- `src/video/video_renderer.py` - FFmpeg rendering pipeline

### Test Data
- `data/video/C0044.MP4` - 11-minute 1080p test video
- `data/audio/C0044.wav` - Extracted audio
- `data/audio/C0044_full_transcript.json` - Full transcript with word timestamps
- Test clip: 90s-123s ("quality over growth" section)

## Architecture Notes

### Previous Problem
Two separate projects created:
1. Audio edited with waveform_silence_remover → v3.wav (25.2s)
2. Video rendered with video_renderer applying different edits
3. Result: Complete audio/video desync

### Solution
Single pipeline that:
1. Gets EditDecisions from waveform_silence_remover
2. Applies SAME decisions to both audio AND video
3. Muxes them together

### Crop Math

**1080p source (1920x1080) → TikTok (9:16):**
- Crop width = 1080 * 9/16 = 607px
- Crop: 607x1080 from center
- Scale: 607x1080 → 1080x1920 (1.78x upscale, unavoidable)

**4K source (3840x2160) → TikTok (9:16):**
- Crop width = 2160 * 9/16 = 1215px
- Crop: 1215x2160 from center
- Scale: 1215x2160 → 1080x1920 (0.89x downscale, no zoom!)

## Decisions Made
- **Gemini Flash 2.5** for vision (not Qwen VL) - faster, more reliable
- **No zoom when possible** - only upscale if source < target resolution
- **Unified function** - one `export_clip()` call does everything
- **Edit decisions shared** - same cuts for audio and video

## Important Patterns

### Silence Removal Presets
| Preset | Min Silence | Max Kept | Padding |
|--------|-------------|----------|---------|
| LinkedIn | 500ms | 700ms | 150ms |
| TikTok | 200ms | 150ms | 80ms |

### FFmpeg Filter Chain
```
trim → setpts → split → [for each segment] → concat → scale → crop → subtitles
```

## Next Steps
1. Create clip_exporter.py
2. Update video_renderer.py to handle integrated flow
3. Test with C0044.MP4 clip
