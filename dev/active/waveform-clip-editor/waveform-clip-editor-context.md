# Waveform Clip Editor Context

**Last Updated**: 2025-12-19

## Key Files

### Backend
- `api/routes/videos.py` - Clip preview endpoint (lines 300-389), needs VAD analysis endpoint
- `src/video/waveform_silence_remover.py` - Has `get_vad_analysis()` function with caching, `SpeechSegment`/`SilenceSegment` dataclasses, `EditDecision` structure
- `src/video/smart_editor.py` - Edit decision logic, preset configs
- `api/routes/exports.py` - Export job creation, needs to accept adjustments

### Frontend
- `frontend/src/components/ClipSuggestions.tsx` - Main UI, currently has approve/reject flow
- `frontend/src/components/WaveformEditor.tsx` - Exists but UNUSED, uses WaveSurfer.js with regions plugin
- `frontend/src/types/index.ts` - TypeScript interfaces
- `frontend/src/api/client.ts` - API client functions

## Architecture Notes

### Current Flow
1. Upload video → Transcribe → AI suggests clips
2. User sees clip list → Expand to preview → Approve/Reject
3. After approval, select platforms → Export

### New Flow
1. Upload video → Transcribe → AI suggests clips
2. User sees clip list → Click Edit to open full editor
3. Editor shows waveform + transcript + platform selection
4. Adjust trims if needed → Select platforms → Export directly

### VAD Data Structure (from waveform_silence_remover.py)
```python
# Already available via get_vad_analysis()
{
    "speech_segments": [SpeechSegment(start, end), ...],
    "silences": [SilenceSegment(start, end), ...],
    "duration": float,
    "config": PresetConfig,
    "preset": str,
}
```

### Preset Configs
- LinkedIn: max_kept_silence=700ms, padding=150ms, min_silence=500ms
- TikTok: max_kept_silence=150ms, padding=80ms, min_silence=200ms
- YouTube Shorts: max_kept_silence=200ms, padding=100ms, min_silence=300ms
- Podcast: max_kept_silence=1000ms, padding=200ms, min_silence=800ms

## Decisions Made

- **Both boundaries adjustable**: User can adjust overall clip start/end AND individual silence trims
- **Base + override pattern**: Set base adjustments, optionally customize per-platform
- **Remove approve step**: Go directly to platform selection and export
- **WaveSurfer.js**: Already installed, use for waveform visualization
- **Touch targets**: Minimum 44px for mobile usability

## Important Patterns

### WaveSurfer Regions
WaveformEditor.tsx already has regions plugin setup:
```typescript
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions'
// Green for clip boundary, can add red for silence regions
```

### API Response Pattern
```typescript
const response = await fetch(`${API_BASE}/endpoint`);
return handleResponse<TypeName>(response);
```

## Next Steps
1. Test on mobile devices (touch interactions, zoom gestures)
2. Test with long clips (performance)
3. Test edge cases (no silence, all silence)

---

## Session 2025-12-19 Notes

### Progress Made
- Fixed Docker container environment variables (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY were missing)
- Fixed torchaudio/torchcodec compatibility issue by pinning `torch<2.9.0` and `torchaudio<2.9.0`
- Added `backend="soundfile"` to torchaudio.load() calls
- Updated docker-compose.yml to use `env_file: ../.env` instead of individual environment variables
- Fixed CORS issue for Vercel frontend (`frontend-flax-sigma-15.vercel.app`)
- **Added zoom controls to WaveformEditor**:
  - Zoom in/out/fit buttons
  - Default view shows clip with 5s context padding on each side
  - Horizontal scroll for navigating zoomed waveform
  - Pinch-to-zoom support via WaveSurfer ZoomPlugin

### Discoveries
- torchaudio 2.9+ requires torchcodec for its new backend - must pin to < 2.9 or use soundfile backend
- Docker `compose restart` doesn't reload env_file - need `down` + `up` to apply env changes
- FastAPI CORSMiddleware doesn't support wildcards like `https://*.vercel.app` - need explicit origins

### Key Files Modified
- `frontend/src/components/WaveformEditor.tsx` - Added ZoomPlugin, zoom controls, horizontal scroll
- `requirements.txt` - Pinned torch and torchaudio versions
- `docker/docker-compose.yml` - Switched to env_file
- `src/video/waveform_silence_remover.py` - Added backend="soundfile" parameter

### Deployed
- Frontend: https://frontend-flax-sigma-15.vercel.app (via Vercel CLI)
- Backend: https://video-clipper.ab-civil.com (Hetzner Docker)

### Blockers/Issues
- None currently - feature is deployed and working
