# Video Export Tasks

**Last Updated**: 2025-12-18 22:55 UTC

## Phase 1: Frame Sampling & Subject Detection ✅
- [x] Create `src/video/export_formats.py` with platform definitions
- [x] Create `src/video/frame_sampler.py` (FFmpeg frame extraction)
  - [x] Sparse mode: 5 frames (start, 25%, 50%, 75%, end)
  - [x] Dense mode: 1 frame per second
  - [x] Return as JPEG bytes for API calls
- [x] Create `src/video/vision_detector.py` (Qwen VL integration)
  - [x] `QwenVisionDetector` class with lazy API client
  - [x] `detect_subject()` method returning SubjectPosition
  - [x] `analyze_movement()` method for drift detection
- [x] Tested frame sampling with test video (need real video for vision API test)

## Phase 2: Crop Calculation ✅
- [x] Create `src/video/crop_calculator.py`
  - [x] `CropRegion` dataclass (x, y, width, height)
  - [x] `calculate_optimal_crop()` per format
  - [x] Vertical (9:16): head in upper third (~35% from top)
  - [x] Square (1:1): center on subject
  - [x] Validate subject fully within crop bounds
- [x] Confidence scoring
  - [x] Auto-approve: 85%+ confidence, no issues
  - [x] Flag for review: <70% OR subject may be cut off
- [x] Tested with simulated subject positions

## Phase 3: Audio-Video Sync ✅
- [x] Create `src/video/edit_sync.py`
  - [x] `VideoEditSegment` dataclass
  - [x] `audio_edits_to_video_segments()` function
  - [x] Frame boundary snapping based on FPS
- [x] Tested with simulated EditDecisions

## Phase 4: Caption Generation ✅
- [x] Create `src/video/caption_styles.py`
  - [x] TikTok style (Montserrat, center-middle, 450px margin)
  - [x] LinkedIn style (Helvetica, lower third, 120px margin)
  - [x] YouTube Shorts style (Montserrat, center-middle)
  - [x] All 6 export formats styled
- [x] Create `src/video/caption_generator.py`
  - [x] Generate ASS from word-level timestamps
  - [x] Group words into caption chunks (5-7 words)
  - [x] Karaoke effect with `\kf` tags
  - [x] Platform-specific positioning
- [x] Tested caption generation with simulated transcript

## Phase 5: Video Rendering ✅
- [x] Create `src/video/video_renderer.py`
  - [x] `RenderConfig` dataclass
  - [x] `render_video()` main function
  - [x] FFmpeg filter_complex: trim → scale → crop → subtitles
  - [x] Support for separate edited audio
  - [x] `render_all_formats()` for batch rendering
- [x] Tested rendering test video to TikTok format

## Phase 6: API Integration
- [ ] Create `api/routes/render.py`
  - [ ] `POST /clips/{id}/analyze-crop` endpoint
  - [ ] `POST /clips/{id}/render` endpoint
  - [ ] `POST /clips/{id}/render-all` endpoint
  - [ ] `GET /clips/{id}/renders` endpoint
- [ ] Update database schema
  - [ ] Add crop_analysis JSONB column
  - [ ] Add edit_decisions JSONB column
  - [ ] Add needs_review BOOLEAN column
- [ ] Register routes in `api/routes/__init__.py`

## Phase 7: Testing & Polish
- [ ] End-to-end test: upload → transcribe → suggest → approve → render
- [ ] Test all 4 output formats
- [ ] Test with different source resolutions (1080p, 4K)
- [ ] Handle edge cases (no subject detected, extreme movement)
- [ ] Performance optimization if needed

## Deployment
- [ ] Copy new files to Hetzner server
- [ ] Install any new dependencies
- [ ] Test on server with real video
