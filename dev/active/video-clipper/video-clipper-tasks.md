# Video Clipper Tasks

**Last Updated**: 2025-12-18 (Clip Composer V2 Complete)

## Phase 1: Core Infrastructure (Day 1-2) - COMPLETE
- [x] Update `requirements.txt` with video/audio dependencies
  - faster-whisper>=1.0.0
  - ffmpeg-python>=0.2.0
  - celery>=5.3.0
  - redis>=5.0.0
  - python-multipart>=0.0.9
  - websockets>=12.0
- [x] Create `src/video/__init__.py` module structure
- [x] Create Supabase tables via SQL (`scripts/create_tables.sql`):
  - videos (id, filename, status, duration, etc.)
  - transcripts (video_id, full_text, segments JSONB)
  - clip_suggestions (video_id, start_time, end_time, platform, hook_reason)
  - rendered_clips (suggestion_id, platform, output_path, storage_url)
- [x] Create basic FastAPI app in `api/main.py` with health check endpoint

## Phase 2: Transcription Engine (Day 3-4) - COMPLETE
- [x] Implement `src/video/audio_extractor.py`
  - FFmpeg command to extract audio from video
  - Support multiple input formats (mp4, mov, webm)
  - Output as WAV or MP3 for Whisper
- [x] Implement `src/video/transcriber.py`
  - Load faster-whisper large-v3 model (int8)
  - Word-level timestamps enabled
  - VAD filter for natural speech
  - Return structured result with segments
- [x] Create `scripts/test_transcribe.py` for local testing
- [x] Test with sample video file (6-minute video tested successfully)

## Phase 3: Silence Detection & Clip Suggestions (Day 5-6) - COMPLETE
- [x] Implement `src/video/silence_detector.py`
  - FFmpeg silencedetect filter
  - Parse stderr output for silence_start/silence_end
  - Configurable threshold (-30dB) and min duration (0.8s)
  - Return list: [{start, end, duration}]
- [x] Implement `src/video/clip_suggester.py`
  - OpenRouter client for Claude Haiku
  - System prompt with civil engineering context
  - Analyze transcript structure + silence data
  - Suggest LinkedIn clips (30-120s, professional insights)
  - Suggest TikTok clips (15-60s, high-energy hooks)
  - Return: [{start, end, platform, hook_reason, confidence}]
- [x] Create `scripts/test_full_pipeline.py` (end-to-end test)

## Phase 4: FastAPI Endpoints (Day 7-8) - COMPLETE
- [x] `POST /api/upload` - Accept video file
  - Save to /data/uploads/
  - Create video record in Supabase
  - Return video_id
- [x] `POST /api/videos/{id}/process` - Trigger processing
  - Extract audio
  - Transcribe
  - Detect silence
  - Generate suggestions
  - Update status throughout
- [x] `GET /api/videos/{id}` - Get video status and metadata
- [x] `GET /api/videos/{id}/transcript` - Get transcript with segments
- [x] `GET /api/videos/{id}/suggestions` - Get clip suggestions
- [x] `PATCH /api/clips/{id}` - Update clip status (approve/reject)
- [ ] WebSocket `/ws/videos/{id}` - Real-time processing updates (deferred)

## Phase 5: Minimal React UI (Day 9-10) - COMPLETE
- [x] Initialize React + Tailwind + Vite in `frontend/`
- [x] Create `VideoUpload.tsx` - Drag-drop with progress bar
- [x] Create `ProcessingStatus.tsx` - Show pipeline stages
- [x] Create `TranscriptView.tsx` - Scrollable transcript with timestamps
- [x] Create `ClipSuggestions.tsx` - List with approve/reject buttons
- [x] Create `AudioPreview.tsx` - HTML5 audio element for clip preview
- [x] Wire up API client with fetch/axios
- [x] Basic routing: Upload → Processing → Review

---

## Phase 6: Intelligent Clip Extraction (Session 3) - COMPLETE
- [x] Import LinkedIn posts to Supabase (178 posts)
- [x] Create `clip_composer_v2.py` with AB Civil context
- [x] Fetch high-performing LinkedIn posts as examples for Sonnet
- [x] Create `waveform_analyzer.py` for boundary snapping
- [x] Integrate waveform analysis into compose-clips API
- [x] Refine prompt for controversial hooks and segment combination

## Post-MVP: Enhanced UI (Week 2)
- [ ] WaveformEditor with WaveSurfer.js
- [ ] Clip boundary adjustment (drag handles on waveform)
- [ ] Click transcript to seek audio
- [ ] Visual distinction for AI-composed clips in UI
- [ ] Authentik OAuth integration

## Post-MVP: Video Rendering (Week 3)
- [ ] Implement `src/video/renderer.py`
- [ ] LinkedIn format: 1:1 square, 1080p, H.264
- [ ] TikTok format: 9:16 vertical, burned-in captions
- [ ] Celery workers for parallel rendering
- [ ] Caption generation via Claude Haiku

## Post-MVP: Production Deployment (Week 4)
- [ ] Create Dockerfile and Dockerfile.worker
- [ ] Create docker-compose.yml
- [ ] Add Caddy configuration for posts.ab-civil.com
- [ ] Deploy to Hetzner server
- [ ] Set up storage cleanup cron job
