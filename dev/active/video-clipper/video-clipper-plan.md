# Video Clipper - Quick Reference

> **Full details**: See `master-plan.md` for complete architecture, schemas, and code snippets.

## What We're Building
Video clipper within social-media-posts that:
1. Uploads video → transcribes with faster-whisper
2. Detects silences → suggests clips via Claude Haiku
3. React UI for audio-first clip approval
4. Renders approved clips for LinkedIn/TikTok

## Key Decisions
- **Transcription**: faster-whisper local (large-v3, int8) - free, best accuracy
- **Project**: Extend social-media-posts (not new repo)
- **Frontend**: React + Tailwind + WaveSurfer.js
- **Deployment**: Hetzner DE (88.99.51.122) via Docker at posts.ab-civil.com

## Infrastructure (Reusing Existing)
- **Redis**: redis:6379 for Celery job queue
- **Database**: Supabase at db.ab-civil.com
- **Storage**: /mnt/misc/video-clipper (6.6TB available)
- **Proxy**: Caddy reverse proxy

## MVP Goal
Upload video → Full transcript with word timestamps → Silence detection → AI clip suggestions → View in React UI

## Deferred (Post-MVP)
- Video rendering with FFmpeg
- Intro/outro handling
- Caption styling
- Terminology database UI
