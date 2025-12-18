# Video Clipper - Context & Reference

**Last Updated**: 2025-12-18 (Session 3)

> **Full architecture**: See `master-plan.md` for complete details.

## Key Reference Files

### Patterns to Follow
| Pattern | File |
|---------|------|
| Whisper transcription | `/Users/adambower/dev/windmill/automations/ringcentral_pipeline/stage3_transcribe.py` |
| Supabase client | `/Users/adambower/dev/windmill/f/slack/daily_summary.py` |
| Dual-mode (local/Windmill) | `/Users/adambower/dev/windmill/f/slack/pdf_to_project_setup.py` |
| Server infrastructure | `/Users/adambower/dev/robot-server/CLAUDE.md` |

### This Project - Key Files Created
| Purpose | File |
|---------|------|
| Transcriber (Deepgram) | `src/video/transcriber.py` |
| Audio extractor | `src/video/audio_extractor.py` |
| Silence detector | `src/video/silence_detector.py` |
| Clip suggester (basic) | `src/video/clip_suggester.py` |
| **Clip Composer V2** | `src/video/clip_composer_v2.py` (AB Civil context + LinkedIn post examples) |
| **Waveform Analyzer** | `src/video/waveform_analyzer.py` (snaps boundaries to natural pauses) |
| Audio assembler | `src/video/audio_assembler.py` (smart editing with filler removal) |
| FastAPI app | `api/main.py` |
| Database client | `api/database.py` |
| API routes | `api/routes/upload.py`, `videos.py`, `transcripts.py`, `clips.py` |
| React frontend | `frontend/src/` |
| DB schema | `scripts/create_tables.sql` |
| **LinkedIn import** | `scripts/import_linkedin_posts.py` |

### Config Files
- `/Users/adambower/dev/social-media-posts/CLAUDE.md` - Project docs
- `/Users/adambower/dev/social-media-posts/.env` - API keys (already configured)
- `/Users/adambower/dev/social-media-posts/requirements.txt` - Dependencies

## Server Specs (Hetzner DE)
- **CPU**: Intel i5-13500 (14 cores, 20 threads)
- **RAM**: 64GB (47GB available)
- **Storage**: 9.3TB on /mnt/misc
- **SSH**: `ssh -i ~/.ssh/id_ed25519_robot admin@88.99.51.122`

## Local Development
```bash
# Start API (port 8000)
python3 -m uvicorn api.main:app --reload

# Start frontend (port 3000)
cd frontend && npm run dev

# Frontend proxies /api to localhost:8000
```

## Dual-Mode Pattern
```python
def get_api_key(key_name: str) -> str:
    """Works both locally and in Windmill."""
    key = os.getenv(key_name)
    if key:
        return key
    try:
        import wmill
        return wmill.get_variable(f"f/ai/{key_name.lower()}")
    except:
        raise ValueError(f"{key_name} not found")
```

---

## Session 2025-12-17 Notes

### Progress Made
- **MVP COMPLETE**: All 5 phases implemented and tested
- Built full pipeline: upload → transcribe → silence detect → AI clip suggestions → review UI
- Successfully processed a 6-minute test video end-to-end
- Installed FFmpeg via Homebrew (was missing initially)
- Created all Supabase tables

### Key Implementation Details
- Using `base` Whisper model for testing (faster), `large-v3` for production
- Clip suggestions via OpenRouter → Claude Haiku
- React + Tailwind v4 + Vite for frontend
- Background task processing in FastAPI (not Celery yet)

### Discoveries
- LinkedIn posts database is in Postiz (https://social.ab-civil.com), not Supabase
- Postiz has its own PostgreSQL: `docker exec -it postiz-postgres psql -U postgres`

### What's Working
- Video upload with drag-drop
- Audio extraction via FFmpeg
- Transcription with faster-whisper (word-level timestamps)
- Silence detection
- AI clip suggestions (LinkedIn/TikTok platforms)
- Transcript view with clickable segments
- Clip approve/reject buttons

### Deferred
- WebSocket real-time updates
- Audio preview component (needs audio endpoint)
- Video rendering (Phase 2)

---

## Session 2025-12-18 Notes

### Progress Made
- **LinkedIn posts imported to Supabase**: 178 posts from `/Users/adambower/dev/windmill-server/data/linkedin_posts_cleaned.json`
- **Created `clip_composer_v2.py`**: Major upgrade with AB Civil context and LinkedIn post examples
- **Created `waveform_analyzer.py`**: Analyzes audio amplitude to find natural pauses (326 pause points detected)
- **Refined clip extraction prompt**: Added rules for controversial hooks, problem→solution arcs, segment combination
- **API working end-to-end**: `/videos/{id}/compose-clips` generates quality clips with waveform snapping

### Key Implementation Details
- **Transcription**: Deepgram-only (no fallbacks per user request). Deepgram best for filler word detection.
- **Clip Composer V2** fetches top 10 high-performing LinkedIn posts (50+ likes) as examples for Sonnet
- **System prompt includes**: AB Civil context (what they do, tone/voice, topics that resonate)
- **Waveform analysis**: RMS envelope with -25dB threshold for natural pauses, snaps clip boundaries to silence

### Clip Quality Examples Generated
- "The Worst Survey Type That's Killing Projects" (24.6s, 90% confidence)
- "How Engineers Create Massive Change Orders" (34.9s, 85% confidence)
- "The #1 Way to Prevent Earthwork Disasters" (23.6s, 80% confidence)

### Database Tables Added
- `linkedin_posts` - 178 posts with content, likes, comments, estimated_date
- `clip_suggestions` columns: `is_composed`, `composition_segments` (for multi-segment clips)

### Deferred
- Video rendering (actual clip export with FFmpeg)
- WaveSurfer.js waveform visualization in UI
- Docker deployment

## Next Steps When Resuming
1. **Test with fresh video upload** - Full end-to-end flow via UI with new V2 composer
2. **Review and adjust prompts** - Fine-tune system prompt based on clip quality
3. **Add video rendering** - Export actual video clips (not just audio) with FFmpeg
4. **UI improvements** - WaveSurfer.js waveform, clip boundary adjustment
5. **Docker deployment** - Package for Hetzner server
