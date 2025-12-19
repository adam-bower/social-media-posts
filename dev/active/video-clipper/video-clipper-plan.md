# Content Generation Platform - Architecture

> **Evolution**: Started as "video clipper", now expanding to full content generation platform.

## What We're Building

A unified content generation platform that takes video recordings and produces:
- **Short video clips** for TikTok, Reels, Shorts, LinkedIn
- **Long-form text posts** for LinkedIn, blog
- **Twitter/X threads** from transcript excerpts
- All from a single video source, under one roof

Scheduling/publishing handled separately via Postiz (social.ab-civil.com).

## Core Architecture

### Data Flow
```
Source Video
    ↓
Transcribe (Deepgram, word-level timestamps)
    ↓
┌─────────────────────────────────────────┐
│  CLIP SELECTOR                          │
│  - View transcript with timestamps      │
│  - Select segments (start/end)          │
│  - Preview with waveform                │
│  - Pick platforms PER CLIP:             │
│    [x] TikTok  [x] LinkedIn Video       │
│    [ ] Reels   [ ] Shorts               │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  EXPORT QUEUE                           │
│  - Each clip × selected platforms       │
│  - Process in background                │
│  - Show progress                        │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  REVIEW / DOWNLOAD                      │
│  - Preview each export                  │
│  - Download or send to Postiz           │
└─────────────────────────────────────────┘
```

### Separate Text Generation Flow
```
Source (Video transcript OR direct input)
    ↓
┌─────────────────────────────────────────┐
│  TEXT GENERATOR                         │
│  - Select source (transcript/manual)    │
│  - Pick output type:                    │
│    • LinkedIn long-form post            │
│    • Twitter thread                     │
│    • Blog post                          │
│  - AI generates draft                   │
│  - Edit and refine                      │
└─────────────────────────────────────────┘
```

## Data Model

```
Project
  └── Sources[] (uploaded videos)
       ├── transcript
       └── Clips[]
            ├── start_time, end_time
            ├── platforms: ["tiktok", "linkedin"]
            └── Exports[]
                 ├── platform
                 ├── status (pending/processing/done/failed)
                 └── output_path

TextPost
  ├── source (transcript_id or null)
  ├── platform
  ├── content
  └── status
```

## Frontend Structure

```
/app
  /upload          - Upload video, start transcription
  /clips           - Select clips from transcript, pick platforms
  /exports         - View export queue and results
  /text            - Generate text posts from transcripts
  /library         - All generated content (videos + text)
```

## Key Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Platform selection | Per clip | User controls which platforms each clip targets |
| Text posts | Standalone | Can come from transcript but not tied to clips |
| Video export | Unified pipeline | `clip_exporter.py` handles all video processing |
| Transcription | Deepgram | Best filler word detection |
| Silence removal | Silero VAD | Neural network-based, handles background noise |
| Subject detection | Gemini Flash 2.5 | Fast, accurate for cropping |

## Technology Stack

### Backend
- **FastAPI** - API server
- **Celery + Redis** - Background job queue
- **Supabase** - Database (PostgreSQL)
- **FFmpeg** - Video/audio processing
- **PyTorch** - Silero VAD (CPU-only)

### Frontend
- **React + Vite** - UI framework
- **Tailwind CSS** - Styling
- **WaveSurfer.js** - Waveform visualization

### AI/ML
- **Deepgram** - Transcription
- **OpenRouter** - LLM access (Claude, Gemini)
- **Silero VAD** - Voice activity detection

## Infrastructure

- **Server**: Hetzner DE (88.99.51.122)
- **Domain**: posts.ab-civil.com
- **Storage**: /mnt/misc/video-clipper (6.6TB)
- **Proxy**: Caddy reverse proxy

## Video Export Pipeline (COMPLETE)

The unified `clip_exporter.py` handles:
1. Audio extraction from clip range
2. Silero VAD silence detection → EditDecisions
3. Same edits applied to audio AND video (sync fix)
4. Subject detection with Gemini Flash 2.5
5. Smart crop centered on subject
6. Karaoke-style ASS captions
7. FFmpeg rendering with platform presets

### Platform Presets

| Platform | Aspect | Silence Preset | Edits |
|----------|--------|----------------|-------|
| TikTok | 9:16 | tiktok | Aggressive (12.8% reduction) |
| YouTube Shorts | 9:16 | youtube_shorts | Medium |
| Instagram Reels | 9:16 | tiktok | Aggressive |
| LinkedIn | 4:5 | linkedin | Conservative (7% reduction) |
