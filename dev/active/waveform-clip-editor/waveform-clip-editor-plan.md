# Waveform Clip Editor Implementation Plan

## Overview
Transform the video clip editor from a simple approve/export flow into an interactive waveform-based editor with visual silence trimming, word-level transcript highlighting, and streamlined platform export.

## Goals
- Show waveform with visual indication of where silence gets trimmed
- Allow dragging to adjust both clip boundaries and individual silence trims
- Support per-platform adjustments with "base + override" pattern
- Remove the separate "Approve" step - go directly to platform selection
- Display transcript continuously with word highlighting during playback
- Show export platforms directly in the preview

## Technical Approach

### Backend
1. New `/vad-analysis` endpoint to expose speech/silence segments
2. Enhance `/clip-preview` to return metadata and accept silence overrides
3. Update export endpoint to accept custom adjustments

### Frontend
1. Enhance existing WaveformEditor with silence regions and drag handles
2. Create ClipTranscript component for word-level highlighting
3. Create ClipEditor as full-featured modal editor
4. Refactor ClipSuggestions to remove approve/reject, add edit button

## Files to Create/Modify

### Backend
- `api/routes/videos.py` - Add `/vad-analysis`, enhance `/clip-preview`
- `api/routes/exports.py` - Accept adjustments in export request

### Frontend (New)
- `frontend/src/components/ClipTranscript.tsx` - Word highlighting component
- `frontend/src/components/ClipEditor.tsx` - Full editor with tabs

### Frontend (Modify)
- `frontend/src/types/index.ts` - Add VADAnalysis, ClipAdjustment types
- `frontend/src/api/client.ts` - Add getVADAnalysis, getClipPreviewMetadata
- `frontend/src/components/WaveformEditor.tsx` - Add silence regions, drag handles
- `frontend/src/components/ClipSuggestions.tsx` - Remove approve/reject, simplify

## Dependencies
- WaveSurfer.js (already installed)
- Silero VAD (already implemented in backend)
- Word-level transcript timing (already available)

## Success Criteria
- [ ] Can see waveform with speech (green) and silence (red/gray) regions
- [ ] Can drag handles to adjust clip start/end boundaries
- [ ] Can drag handles to adjust individual silence trim points
- [ ] Transcript shows continuous text with current word highlighted
- [ ] Can click a word to seek to that position
- [ ] Can select platforms and export directly (no approve step)
- [ ] Base adjustments apply to all platforms by default
- [ ] Can override adjustments per-platform if needed
- [ ] Touch-friendly on mobile (44px minimum targets)
