# Unified Clip Pipeline Implementation Plan

## Overview
Merge the waveform-silence-removal and video-export projects into a single unified pipeline that exports social media clips with silence removal, intelligent cropping, and captions.

## Goals
- Single function to export a clip from source video
- Audio and video edits perfectly synced (same EditDecisions applied to both)
- Smart cropping centered on detected subject
- No unnecessary zoom (crop + downscale when possible)
- Karaoke-style captions from transcript

## Technical Approach
1. Create `clip_exporter.py` as the orchestrator
2. Extract audio from clip range
3. Run waveform silence removal → get EditDecisions
4. Apply same EditDecisions to video via edit_sync
5. Detect subject position with Gemini Flash 2.5
6. Calculate crop (minimal scaling)
7. Generate ASS captions if transcript provided
8. Render final video with FFmpeg

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/video/clip_exporter.py` | CREATE | Unified orchestration |
| `src/video/video_renderer.py` | MODIFY | Add clip_start/clip_end, fix audio sync |
| `src/video/crop_calculator.py` | MODIFY | Smart scaling (avoid zoom when possible) |

## Dependencies
- Existing: waveform_silence_remover.py, edit_sync.py, frame_sampler.py, vision_detector.py, caption_generator.py
- External: Gemini Flash 2.5 via OpenRouter, FFmpeg, Silero VAD

## Success Criteria
- [ ] Export clip with synced audio/video
- [ ] Subject properly centered in crop
- [ ] No zoom when source >= target resolution
- [ ] Captions appear with karaoke effect
- [ ] Test passes on C0044.MP4 clip (90s-123s)
