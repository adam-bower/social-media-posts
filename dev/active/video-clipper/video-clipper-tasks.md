# Content Generation Platform - Tasks

**Last Updated**: 2025-12-19 (Session 4)

---

## COMPLETED

### Phase 1-5: Original MVP ✅
- [x] Video upload with drag-drop
- [x] Audio extraction via FFmpeg
- [x] Transcription with Deepgram (word-level timestamps)
- [x] Silence detection
- [x] AI clip suggestions
- [x] Basic React UI with transcript view
- [x] Clip approve/reject

### Phase 6: Intelligent Clip Extraction ✅
- [x] Import LinkedIn posts to Supabase (178 posts)
- [x] clip_composer_v2.py with AB Civil context
- [x] waveform_analyzer.py for boundary snapping

### Phase 7: Unified Video Export Pipeline ✅
- [x] Create `clip_exporter.py` - main orchestrator
- [x] Silero VAD silence removal (`waveform_silence_remover.py`)
- [x] Subject detection with Gemini Flash 2.5 (`vision_detector.py`)
- [x] Smart crop calculation (`crop_calculator.py`)
- [x] Karaoke-style captions (`caption_generator.py`)
- [x] FFmpeg rendering with audio/video sync
- [x] Fix 118ms desync bug (disable frame snapping)
- [x] Test with C0044.MP4 - verified working
- [x] Push to GitHub (commit `e1e0716`)

---

## IN PROGRESS

### Phase 8: Server Deployment
- [ ] rsync code from local to server (`/opt/social-media-posts/`)
- [ ] Install FFmpeg on server
- [ ] Install Python deps (PyTorch CPU-only)
- [ ] Create `.env` with `OPENROUTER_API_KEY`
- [ ] Test `clip_exporter.py` works on server

---

## TODO

### Phase 9: Frontend Restructure
New routing structure to match architecture:

```
/app
  /upload          - Upload video, start transcription
  /clips           - Select clips, pick platforms per clip
  /exports         - Export queue and results
  /text            - Text post generation
  /library         - All generated content
```

Tasks:
- [ ] Create new route structure
- [ ] Update navigation
- [ ] Add platform selector (checkboxes) to clip cards
- [ ] Create export queue view
- [ ] Add progress indicators for processing

### Phase 10: Platform Selection UI
- [ ] Add checkboxes for each platform on clip cards:
  - TikTok (9:16)
  - YouTube Shorts (9:16)
  - Instagram Reels (9:16)
  - LinkedIn Video (4:5)
- [ ] Show preview of crop/format per platform
- [ ] "Export Selected" button triggers queue

### Phase 11: Export Queue & Background Processing
- [ ] Create Celery worker for video exports
- [ ] Add `exports` table to Supabase
- [ ] API endpoint: `POST /api/clips/{id}/export`
- [ ] WebSocket or polling for progress updates
- [ ] Download links when complete

### Phase 12: Text Generation
- [ ] Create text generation UI
- [ ] Select source: transcript or manual input
- [ ] Output types: LinkedIn post, Twitter thread, Blog
- [ ] AI generates draft (Claude via OpenRouter)
- [ ] Edit and refine interface
- [ ] Save to library

### Phase 13: Library View
- [ ] Grid view of all generated content
- [ ] Filter by type (video, text) and platform
- [ ] Preview and download
- [ ] Send to Postiz integration (future)

---

## DEFERRED

### Docker Deployment
- [ ] Create Dockerfile
- [ ] Create docker-compose.yml
- [ ] Caddy configuration for posts.ab-civil.com

### Advanced Features
- [ ] Terminology database UI
- [ ] Authentik OAuth integration
- [ ] Intro/outro handling
- [ ] A/B caption styles
