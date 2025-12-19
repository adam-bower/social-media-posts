# Content Generation Platform - Context & Reference

**Last Updated**: 2025-12-19 (Session 4 - Unified Pipeline Complete)

## Key Files

### Video Processing Pipeline (NEW - Session 4)
| Purpose | File |
|---------|------|
| **Unified Exporter** | `src/video/clip_exporter.py` - Main entry point |
| Silence Removal | `src/video/waveform_silence_remover.py` - Silero VAD |
| Subject Detection | `src/video/vision_detector.py` - Gemini Flash 2.5 |
| Crop Calculator | `src/video/crop_calculator.py` - Smart cropping |
| Caption Generator | `src/video/caption_generator.py` - ASS with karaoke |
| Video Renderer | `src/video/video_renderer.py` - FFmpeg pipeline |
| Edit Sync | `src/video/edit_sync.py` - Audio-to-video mapping |
| Export Formats | `src/video/export_formats.py` - Platform specs |
| Frame Sampler | `src/video/frame_sampler.py` - FFmpeg frame extraction |
| Caption Styles | `src/video/caption_styles.py` - Platform styling |

### Original Pipeline (Still Used)
| Purpose | File |
|---------|------|
| Transcriber (Deepgram) | `src/video/transcriber.py` |
| Audio extractor | `src/video/audio_extractor.py` |
| Clip Composer V2 | `src/video/clip_composer_v2.py` |
| Waveform Analyzer | `src/video/waveform_analyzer.py` |
| Audio assembler | `src/video/audio_assembler.py` |

### API & Frontend
| Purpose | File |
|---------|------|
| FastAPI app | `api/main.py` |
| Database client | `api/database.py` |
| API routes | `api/routes/upload.py`, `videos.py`, `transcripts.py`, `clips.py` |
| React frontend | `frontend/src/` |
| DB schema | `scripts/create_tables.sql` |

## Usage - Unified Export Pipeline

```python
from src.video.clip_exporter import export_clip

result = export_clip(
    video_path="data/video/C0044.MP4",
    clip_start=90.0,
    clip_end=123.0,
    output_path="output/clip.mp4",
    format_type="tiktok",       # tiktok, youtube_shorts, linkedin, etc.
    preset="linkedin",           # Silence removal: linkedin, tiktok, podcast
    transcript=transcript_dict,  # Optional, for captions
)

# Result contains:
# - success: bool
# - edited_duration: float
# - time_saved: float
# - subject_position: detected position
# - crop: calculated crop region
```

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

# Test unified exporter
python3 -c "from src.video.clip_exporter import export_clip; print('OK')"
```

---

## Session 2025-12-19 Notes (Session 4)

### Progress Made
- **Unified clip export pipeline COMPLETE** - `clip_exporter.py`
- **All video processing modules created and tested**:
  - Silero VAD silence removal
  - Gemini Flash 2.5 subject detection via OpenRouter
  - Smart crop calculation
  - Karaoke-style ASS captions
  - FFmpeg rendering with audio/video sync
- **Bug fix**: Disabled frame snapping to fix 118ms audio/video desync
- **Pushed to GitHub**: Commit `e1e0716`
- **Verified output**: 1080x1920 TikTok video with burned-in captions

### Test Results
| Preset | Original | Edited | Saved |
|--------|----------|--------|-------|
| LinkedIn | 33.0s | 30.65s | 7.1% |
| TikTok | 33.0s | 28.8s | 12.8% |

### Architecture Decision
- **Platform selection is PER CLIP** - user picks which platforms each clip targets
- **Text posts are STANDALONE** - can use transcript but not tied to video clips
- **Frontend to be restructured** with new routes: /upload, /clips, /exports, /text, /library

### What's NOT Done Yet
- Server deployment (code pushed but not deployed)
- Frontend restructure for new architecture
- Text post generation UI
- Export queue with background processing

---

## Previous Sessions

### Session 2025-12-18 (Session 3)
- LinkedIn posts imported (178 posts)
- clip_composer_v2.py with AB Civil context
- waveform_analyzer.py for boundary snapping

### Session 2025-12-17 (Session 2)
- MVP complete: upload → transcribe → silence detect → AI suggestions → review UI
- Deepgram transcription working
- React + Tailwind UI

---

## Next Steps When Resuming

1. **Deploy to server** - rsync code, install deps (PyTorch CPU, FFmpeg)
2. **Restructure frontend** - New routes matching the architecture
3. **Add platform selector to clip UI** - Checkboxes for TikTok, LinkedIn, etc.
4. **Create export queue** - Background processing with Celery
5. **Add text generation** - LinkedIn posts from transcript
