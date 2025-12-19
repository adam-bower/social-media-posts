# Unified Clip Pipeline Tasks

**Last Updated**: 2025-12-19 01:50 UTC

## Phase 1: Create Unified Exporter ✅ COMPLETE
- [x] Create `src/video/clip_exporter.py` with `export_clip()` function
- [x] Integrate audio extraction for clip range
- [x] Integrate waveform_silence_remover for EditDecisions
- [x] Build VideoEditPlan from EditDecisions
- [x] Generate edited audio with audio_assembler

## Phase 2: Video Rendering ✅ COMPLETE (Integrated into clip_exporter)
- [x] Build FFmpeg command with clip_start offset
- [x] Apply same edits to video via filter_complex
- [x] Multi-segment split/trim/concat working

## Phase 3: Smart Cropping ✅ COMPLETE
- [x] Integrated crop_calculator.py
- [x] Scale and crop in single FFmpeg filter chain

## Phase 4: Subject Detection Integration ✅ COMPLETE
- [x] Sample frames from clip range (not full video)
- [x] Detect subject with Gemini Flash 2.5
- [x] Center crop on averaged subject position

## Phase 5: Caption Integration ✅ COMPLETE
- [x] Filter transcript words to clip range
- [x] Adjust timestamps relative to clip start
- [x] Account for silence removal timing changes (map through edit segments)
- [x] Generate ASS with karaoke effect

## Phase 6: Testing ✅ COMPLETE
- [x] Test with C0044.MP4 clip (90s-123s)
- [x] Verify audio/video sync is correct
- [x] Verify subject is centered (1080x1920 output)
- [x] Verify captions are timed correctly
- [x] Test with TikTok preset (aggressive edits) - 28.8s, 12.8% reduction
- [x] Test with LinkedIn preset (lighter edits) - 30.8s, 6.6% reduction

## Phase 7: Cleanup
- [ ] Remove/deprecate old separate workflows
- [ ] Update dev docs for video-export and waveform-silence-removal
- [ ] Document the unified API

---

## Implementation Notes

### Key File: `src/video/clip_exporter.py`

The unified exporter orchestrates the entire pipeline through `export_clip()`:

```python
from src.video.clip_exporter import export_clip

result = export_clip(
    video_path="data/video/C0044.MP4",
    clip_start=90.0,
    clip_end=123.0,
    output_path="output/clip.mp4",
    format_type="tiktok",      # Output format
    preset="linkedin",          # Silence removal preset
    transcript=transcript_dict, # Optional for captions
)
```

### Pipeline Steps

1. **Audio Extraction**: FFmpeg extracts audio from clip range at 16kHz mono (for Silero VAD)
2. **Silence Removal**: Silero VAD detects speech/silence, creates EditDecisions
3. **Video Edit Plan**: EditDecisions converted to VideoEditSegment list
4. **Audio Assembly**: Edited audio created from kept segments
5. **Subject Detection**: 5 frames sampled, analyzed with Gemini Flash 2.5
6. **Crop Calculation**: CropRegion computed to center subject
7. **Caption Generation**: Words filtered to clip, timestamps adjusted for edits
8. **FFmpeg Render**: Single command applies all video edits, scale, crop, subtitles

### Critical Sync Fix

The key insight: **Same EditDecisions apply to both audio AND video**

- Audio is edited using `audio_assembler.assemble_audio()`
- Video is edited using FFmpeg `trim` + `concat` filters
- Both use the exact same segment times, ensuring perfect sync

### Test Results

| Preset | Original | Edited | Saved | Segments |
|--------|----------|--------|-------|----------|
| LinkedIn | 33.0s | 30.65s | 2.35s (7.1%) | 3 |
| TikTok | 33.0s | 28.8s | 4.2s (12.8%) | 8 |

### Verification Checklist

- [x] Duration matches edited_duration (30.667s video vs 30.648s audio)
- [x] Audio/video sync within tolerance (18.7ms diff - under 50ms threshold)
- [x] Resolution is 1080x1920 (TikTok 9:16)
- [x] Subject detection working (98% confidence)
- [x] Crop centered on subject (position 0.50, 0.58)
- [x] Captions burned in with karaoke effect
- [x] Caption timestamps adjusted for edit segments

### Bug Fix Applied

**Issue**: Original code had 118ms audio/video desync caused by frame snapping
**Fix**: Disabled `snap_to_frames` in `create_video_edit_plan()` so video uses exact same segment times as audio
