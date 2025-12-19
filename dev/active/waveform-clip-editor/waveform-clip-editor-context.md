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
1. Start with backend `/vad-analysis` endpoint
2. Then frontend types and API client
3. Then enhance WaveformEditor with silence visualization
