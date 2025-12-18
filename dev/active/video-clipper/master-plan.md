# Video Clipper Implementation Plan

## Overview
Build a video clipper platform within the existing `social-media-posts` project that:
1. Accepts video uploads
2. Transcribes with faster-whisper (local, large-v3 model)
3. Detects silence and suggests clip points
4. Provides React UI for audio-first clip approval
5. Renders approved clips for LinkedIn/TikTok

## Key Decisions
- **Transcription**: faster-whisper local (free, best accuracy)
- **Project**: Extend social-media-posts (not new repo)
- **Frontend**: React + Tailwind with WaveSurfer.js
- **Deployment**: Hetzner DE (88.99.51.122) via Docker

---

## Phase 1: Core Upload & Transcription (MVP Focus)

### 1.1 Project Structure Updates
**File: `/Users/adambower/dev/social-media-posts/`**

```
social-media-posts/
├── CLAUDE.md                    # Update with video clipper info
├── requirements.txt             # Add video/audio dependencies
├── .env                         # Already has needed keys
├── src/
│   ├── __init__.py
│   ├── llm/                     # Existing
│   ├── platforms/               # Existing
│   ├── templates/               # Existing
│   └── video/                   # NEW
│       ├── __init__.py
│       ├── transcriber.py       # faster-whisper integration
│       ├── silence_detector.py  # FFmpeg silence detection
│       ├── clip_suggester.py    # Claude Haiku analysis
│       └── renderer.py          # FFmpeg clip rendering
├── api/                         # NEW - FastAPI backend
│   ├── __init__.py
│   ├── main.py                  # FastAPI app
│   ├── routes/
│   │   ├── upload.py            # Video upload endpoints
│   │   ├── transcribe.py        # Transcription status
│   │   ├── clips.py             # Clip suggestions/approval
│   │   └── render.py            # Clip rendering
│   ├── models/
│   │   └── schemas.py           # Pydantic models
│   └── workers/
│       └── tasks.py             # Celery tasks
├── frontend/                    # NEW - React app
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── VideoUpload.tsx
│   │   │   ├── TranscriptView.tsx
│   │   │   ├── WaveformEditor.tsx
│   │   │   └── ClipApproval.tsx
│   │   └── api/
│   │       └── client.ts
│   └── tailwind.config.js
├── docker/
│   ├── Dockerfile
│   ├── Dockerfile.worker
│   └── docker-compose.yml
└── scripts/
    └── test_transcribe.py       # Local testing script
```

### 1.2 Dependencies to Add
**Update: `requirements.txt`**
```
# Video/Audio Processing
faster-whisper>=1.0.0
ffmpeg-python>=0.2.0

# Job Queue
celery>=5.3.0
redis>=5.0.0

# API
fastapi>=0.115.0
uvicorn>=0.32.0
python-multipart>=0.0.9
websockets>=12.0

# Existing deps remain...
```

### 1.3 Database Schema (Supabase)
**Tables to create in existing Supabase instance:**

```sql
-- Videos table
CREATE TABLE videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    filename TEXT NOT NULL,
    original_path TEXT NOT NULL,
    duration_seconds FLOAT,
    resolution TEXT,
    file_size_bytes BIGINT,
    status TEXT DEFAULT 'uploaded', -- uploaded, processing, transcribed, ready, error
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Transcripts table
CREATE TABLE transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    full_text TEXT,
    segments JSONB, -- Array of {start, end, text, confidence}
    language TEXT,
    model_used TEXT DEFAULT 'large-v3',
    processing_time_seconds FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Clip suggestions table
CREATE TABLE clip_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    start_time FLOAT NOT NULL,
    end_time FLOAT NOT NULL,
    transcript_excerpt TEXT,
    platform TEXT, -- linkedin, tiktok, both
    hook_reason TEXT,
    confidence_score FLOAT,
    status TEXT DEFAULT 'pending', -- pending, approved, rejected, rendered
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Rendered clips table
CREATE TABLE rendered_clips (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    suggestion_id UUID REFERENCES clip_suggestions(id) ON DELETE CASCADE,
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    output_path TEXT,
    storage_url TEXT, -- Supabase Storage URL
    duration_seconds FLOAT,
    file_size_bytes BIGINT,
    render_time_seconds FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 1.4 Core Implementation Files

**File: `src/video/transcriber.py`**
```python
"""
faster-whisper transcription with word-level timestamps.
Pattern follows: /Users/adambower/dev/windmill/automations/ringcentral_pipeline/stage3_transcribe.py
"""
from faster_whisper import WhisperModel
import tempfile
import os

def main(
    audio_path: str,
    model_size: str = "large-v3",
    compute_type: str = "int8"
) -> dict:
    """Transcribe audio with word-level timestamps."""
    model = WhisperModel(model_size, compute_type=compute_type)
    segments, info = model.transcribe(
        audio_path,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500}
    )
    # Return structured result...
```

**File: `src/video/silence_detector.py`**
```python
"""
FFmpeg-based silence detection for natural pause removal.
"""
import subprocess
import json

def detect_silences(
    audio_path: str,
    noise_threshold: str = "-30dB",
    min_duration: float = 0.8
) -> list:
    """Detect silence periods in audio."""
    cmd = [
        "ffmpeg", "-i", audio_path,
        "-af", f"silencedetect=noise={noise_threshold}:d={min_duration}",
        "-f", "null", "-"
    ]
    # Parse FFmpeg output for silence timestamps...
```

**File: `api/main.py`**
```python
"""
FastAPI application for video clipper.
Pattern follows existing Windmill dual-mode approach.
"""
from fastapi import FastAPI, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Video Clipper API")

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://posts.ab-civil.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes: /upload, /videos/{id}, /videos/{id}/transcript, /clips, etc.
```

---

## Phase 2: Clip Suggestion Engine

### 2.1 Claude Haiku Integration
**File: `src/video/clip_suggester.py`**

Uses OpenRouter (already in .env) to call Claude Haiku:
- Analyzes transcript structure
- Suggests LinkedIn clips (30-120s, professional insights)
- Suggests TikTok clips (15-60s, high-energy hooks)
- Returns timestamp ranges with reasoning

### 2.2 Civil Engineering Terminology
**File: `src/video/terminology.py`**

- Load custom terms from Supabase table
- Inject into system prompt for transcript correction
- Handle industry-specific jargon

---

## Phase 3: React Frontend

### 3.1 Key Components
- **VideoUpload.tsx**: Drag-drop upload with progress
- **TranscriptView.tsx**: Scrolling transcript with timestamps
- **WaveformEditor.tsx**: WaveSurfer.js audio visualization
- **ClipApproval.tsx**: Approve/reject/adjust clip boundaries

### 3.2 Audio-First Workflow
1. Upload video → extract audio immediately
2. Show waveform + transcript while video processes
3. User approves clips via audio preview (fast)
4. Only render video for approved clips (saves time)

---

## Phase 4: Video Rendering

### 4.1 FFmpeg Rendering
**File: `src/video/renderer.py`**

```python
def render_clip(
    video_path: str,
    start_time: float,
    end_time: float,
    platform: str,  # linkedin, tiktok
    add_captions: bool = True
) -> str:
    """Render clip with platform-specific formatting."""
    # LinkedIn: 1:1 square, 1080p
    # TikTok: 9:16 vertical, 1080x1920, burned-in captions
```

### 4.2 Celery Workers
- Process 2-3 clips simultaneously (CPU allows)
- Priority queue: LinkedIn first
- WebSocket updates to frontend

---

## Deployment Architecture

### Docker Compose Structure
```yaml
services:
  api:
    build: ./docker
    ports:
      - "127.0.0.1:8010:8000"
    volumes:
      - /mnt/misc/video-clipper:/data
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/1

  worker:
    build:
      context: ./docker
      dockerfile: Dockerfile.worker
    volumes:
      - /mnt/misc/video-clipper:/data
    deploy:
      replicas: 2

  frontend:
    build: ./frontend
    ports:
      - "127.0.0.1:3010:3000"
```

### Caddy Configuration
```caddy
posts.ab-civil.com {
    # API routes
    handle /api/* {
        reverse_proxy localhost:8010
    }

    # WebSocket for real-time updates
    handle /ws/* {
        reverse_proxy localhost:8010
    }

    # React frontend
    handle {
        reverse_proxy localhost:3010
    }

    # Large video uploads (5GB max)
    request_body {
        max_size 5GB
    }
}
```

### Storage Layout
```
/mnt/misc/video-clipper/
├── uploads/          # Incoming videos (temp)
├── processing/       # FFmpeg working files (temp)
├── archive/          # Original videos (permanent)
├── clips/            # Rendered clips
└── models/           # faster-whisper model cache (~3GB for large-v3)
```

---

## Implementation Order

### MVP Sprint: Full Suggestion Pipeline (Priority)

**Goal**: Upload video → Transcribe → Detect silence → Suggest clips → View in UI

#### Day 1-2: Core Infrastructure
1. [ ] Update `requirements.txt` with video/audio deps
2. [ ] Create `src/video/` module structure with `__init__.py`
3. [ ] Create Supabase tables (videos, transcripts, clip_suggestions, rendered_clips)
4. [ ] Basic FastAPI app in `api/main.py` with health check

#### Day 3-4: Transcription Engine
1. [ ] Implement `src/video/transcriber.py` with faster-whisper
   - Download large-v3 model on first run (~3GB)
   - Word-level timestamps enabled
   - VAD filter for natural speech
2. [ ] Implement `src/video/audio_extractor.py` (FFmpeg audio extraction)
3. [ ] Create `scripts/test_transcribe.py` for local testing
4. [ ] Test with sample video file

#### Day 5-6: Silence Detection & Clip Suggestions
1. [ ] Implement `src/video/silence_detector.py`
   - FFmpeg silencedetect filter
   - Configurable threshold (-30dB) and min duration (0.8s)
   - Return list of silence periods with timestamps
2. [ ] Implement `src/video/clip_suggester.py`
   - OpenRouter → Claude Haiku integration
   - System prompt with civil engineering context
   - Analyze transcript + silence data
   - Return suggested clips with timestamps, platform, reasoning
3. [ ] Create `scripts/test_full_pipeline.py` (end-to-end test)

#### Day 7-8: FastAPI Endpoints
1. [ ] `POST /api/upload` - Accept video, save to disk, create DB record
2. [ ] `POST /api/videos/{id}/process` - Trigger processing pipeline
3. [ ] `GET /api/videos/{id}` - Get video status and metadata
4. [ ] `GET /api/videos/{id}/transcript` - Get transcript with segments
5. [ ] `GET /api/videos/{id}/suggestions` - Get clip suggestions
6. [ ] WebSocket `/ws/videos/{id}` - Real-time processing updates

#### Day 9-10: Minimal React UI
1. [ ] Initialize React + Tailwind + Vite in `frontend/`
2. [ ] Simple upload form with progress bar
3. [ ] Processing status indicator
4. [ ] Transcript display with timestamps
5. [ ] Clip suggestions list with approve/reject buttons
6. [ ] Basic audio preview (HTML5 audio element)

### Post-MVP: Polish & Deployment

#### Week 2: Enhanced UI
1. [ ] WaveformEditor with WaveSurfer.js
2. [ ] Clip boundary adjustment (drag handles)
3. [ ] Better transcript navigation (click to seek)
4. [ ] Authentik OAuth integration

#### Week 3: Video Rendering
1. [ ] Implement `src/video/renderer.py` with FFmpeg
2. [ ] LinkedIn format (1:1 square, 1080p)
3. [ ] TikTok format (9:16 vertical, burned-in captions)
4. [ ] Celery workers for parallel rendering

#### Week 4: Production Deployment
1. [ ] Docker configuration
2. [ ] Caddy routing setup
3. [ ] Deploy to Hetzner
4. [ ] Storage management (cleanup old files)

---

## Key Files Reference

| Purpose | File |
|---------|------|
| Transcription pattern | `/Users/adambower/dev/windmill/automations/ringcentral_pipeline/stage3_transcribe.py` |
| Supabase client pattern | `/Users/adambower/dev/windmill/f/slack/daily_summary.py` |
| Dual-mode (local/Windmill) | `/Users/adambower/dev/windmill/f/slack/pdf_to_project_setup.py` |
| Server infrastructure | `/Users/adambower/dev/robot-server/CLAUDE.md` |
| Existing project | `/Users/adambower/dev/social-media-posts/` |

---

## Questions Resolved
- ✅ Transcription: faster-whisper local (large-v3, int8)
- ✅ Project: Extend social-media-posts
- ✅ Frontend: React + Tailwind
- ✅ Infrastructure: Reuse existing Redis, Supabase, Caddy
- ✅ MVP Scope: Full pipeline (transcribe + silence + suggestions)

## Deferred Decisions (Post-MVP)
- **Intro/Outro**: Auto-prepend/append? Per-clip toggle? Platform-specific?
- **Screen Recording Detection**: Auto-detect and adjust framing for vertical?
- **Caption Styling**: Word-by-word highlight vs sentence blocks? Font/color?
- **Terminology Database**: UI for managing civil engineering terms?

## First Session Deliverables
When implementation starts, the first working session should produce:
1. Updated `requirements.txt` with faster-whisper, ffmpeg-python
2. `src/video/transcriber.py` - working transcription
3. `scripts/test_transcribe.py` - test script you can run locally
4. Supabase tables created (videos, transcripts, clip_suggestions)

This validates the core transcription works before building the full pipeline.
