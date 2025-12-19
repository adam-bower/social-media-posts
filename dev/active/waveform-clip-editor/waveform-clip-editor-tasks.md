# Waveform Clip Editor Tasks

**Last Updated**: 2025-12-19

## Phase 1: Backend API
- [x] Add `GET /videos/{video_id}/vad-analysis` endpoint in `api/routes/videos.py`
  - Return speech_segments, silence_segments, duration, preset, config
  - Uses `get_vad_analysis()` from waveform_silence_remover.py (cached)
  - Added Pydantic schemas: VADAnalysisResponse, SpeechSegment, SilenceSegment, PresetConfigResponse
- [x] Enhance `GET /videos/{video_id}/clip-preview` endpoint
  - Added `return_metadata=true` parameter to return JSON instead of audio
  - Added `silence_overrides` parameter for custom trim amounts (JSON string)
  - Switched to waveform-based editing (Silero VAD) for better accuracy
  - Added ClipPreviewMetadata schema with speech/silence segments and edit decisions
- [x] Update export endpoint to accept adjustments
  - Added `adjustments` field to ExportRequest with PlatformAdjustments schema
  - Added ClipAdjustments, SilenceOverride, ClipBoundaryAdjustment schemas
  - Updated database.create_export() to store adjustments as JSON
  - Updated process_export() to apply boundary adjustments and silence config
  - Merges base adjustments with platform-specific overrides

## Phase 2: Frontend Types & API
- [x] Add TypeScript interfaces in `frontend/src/types/index.ts`
  - VADAnalysis, SpeechSegment, SilenceSegment, EditDecision, PresetConfig
  - ClipPreviewMetadata, SilenceOverride, ClipBoundaryAdjustment
  - ClipAdjustments, PlatformAdjustments
- [x] Add API functions in `frontend/src/api/client.ts`
  - getVADAnalysis(videoId, preset) - fetch VAD analysis for a video
  - getClipPreviewMetadata(videoId, start, end, preset, silenceOverrides)
  - Updated createExport() to accept PlatformAdjustments

## Phase 3: WaveformEditor Enhancement
- [x] Add silence region visualization
  - Green overlay for speech segments (rgba green-500)
  - Gray overlay for kept silence (rgba zinc-400)
  - Red overlay for trimmed silence (rgba red-500)
- [x] Add draggable clip boundary handles (start/end)
  - Uses WaveSurfer regions plugin with resize: true
- [x] Add draggable silence trim handles
  - Trimmed regions resizable when onSilenceAdjustment provided
- [x] Ensure touch-friendly (44px min targets)
  - Play button has minHeight: 44px
- [x] Update props interface with new callbacks
  - Added speechSegments, silenceSegments, presetConfig
  - Added silenceAdjustments, onSilenceAdjustment
  - Added onTimeUpdate, readOnly props
  - Exported SilenceAdjustment interface

## Phase 4: ClipTranscript Component (NEW)
- [x] Create `frontend/src/components/ClipTranscript.tsx`
- [x] Render words as continuous inline text (no line breaks)
  - Extracts words from segments within clip bounds
  - Falls back to segment text if no word-level timestamps
- [x] Highlight current word based on playback time
  - Active word: emerald background, white text
  - Past words: zinc-400 text
  - Future words: zinc-300 with hover effect
- [x] Support clicking word to seek
  - onClick calls onSeek(word.start)
- [x] Auto-scroll to keep current word visible
  - Uses scrollIntoView with smooth behavior

## Phase 5: ClipEditor Component (NEW)
- [x] Create `frontend/src/components/ClipEditor.tsx`
- [x] Layout: header, waveform, tabs, transcript, stats, platforms, export button
  - Modal overlay with rounded corners
  - Header with title and close button
  - Scrollable content area
  - Fixed footer with platform selection and export
- [x] Implement tab system (Base + platform tabs)
  - Base tab for global settings
  - Dynamic tabs for selected platforms
  - Orange indicator dot for tabs with overrides
- [x] Show adjustments per-tab with override indicators
  - Max kept silence slider (0-2000ms)
  - Per-silence overrides tracked in state
- [x] Integrate WaveformEditor and ClipTranscript
  - Passes VAD analysis to WaveformEditor
  - Passes transcript segments to ClipTranscript
  - Connected via currentTime state
- [x] Connect audio playback with transcript highlighting
  - onTimeUpdate callback syncs currentTime
  - isPlaying state passed to ClipTranscript
- [x] Platform selection with checkboxes
  - Toggle buttons for each platform
  - Emerald background when selected
- [x] Export button with selected platforms count
  - Shows count in button text
  - Disabled when no platforms selected

## Phase 6: ClipSuggestions Refactor
- [x] Remove handleApprove, handleReject functions
  - Removed all approval workflow code
- [x] Remove approve/reject buttons
  - Removed expanded section with approve/reject
- [x] Remove status-based filtering (pending/approved)
  - All clips now shown equally
- [x] Simplify clip card: Play button, time range, Edit button
  - Clean card with play, info, and Edit button
- [x] Add Edit button that opens ClipEditor modal
  - "Edit & Export" button opens ClipEditor
  - Stops audio when opening editor
- [x] Show completed exports inline on card
  - Export badges shown below clip info
  - Shows platform, status, and time saved

## Phase 7: Export with Adjustments
- [x] Update createExport API call to include adjustments
  - Already implemented in ClipEditor.handleExport()
  - Passes PlatformAdjustments with base and overrides
- [x] Apply per-platform overrides when exporting
  - Backend merges base with platform overrides
  - Applies boundary and silence adjustments
- [x] Show export progress in ClipEditor
  - Modal closes after export starts
  - Progress shown in ClipSuggestions list

## Phase 8: Testing & Polish
- [x] Build passes with no TypeScript errors
  - Fixed unused variable in WaveformEditor.tsx
- [ ] Test on mobile (touch interactions)
- [ ] Test with long clips (performance)
- [ ] Test edge cases (no silence, all silence)
- [x] Deploy frontend to Vercel
  - Deployed via `vercel --prod` CLI
  - URL: https://frontend-flax-sigma-15.vercel.app
- [x] Sync updated code to server container
  - Rsync to Hetzner, Docker rebuild with `--no-cache`
  - Fixed torchaudio < 2.9 pinning for Silero VAD compatibility
  - Fixed CORS for Vercel origin
- [x] Verify end-to-end flow
  - VAD analysis endpoint working
  - Waveform editor loading with zoom controls

## Phase 9: Waveform Zoom Feature (NEW - Completed)
- [x] Add zoom controls to WaveformEditor
  - Zoom in/out buttons with 1.5x multiplier
  - Fit button to reset to optimal view
  - Zoom level indicator (px/s)
- [x] Default to clip-focused view
  - Shows clip with 5s context padding on each side
  - Auto-scrolls to clip position on load
- [x] Horizontal scroll container
  - Waveform scrolls horizontally when zoomed
- [x] Pinch-to-zoom support
  - WaveSurfer ZoomPlugin enabled

## Local Testing URLs
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
