# Waveform-First Silence Removal Context

**Last Updated**: 2025-12-18 20:15 UTC

## Key Files

### Local (`src/video/`)
- `waveform_silence_remover.py` - Silero VAD-based silence removal + duration estimation
- `transcript_enhanced_editor.py` - Filler/restart detection from transcripts
- `audio_assembler.py` - Updated with `create_edited_clip_waveform()` function
- `clip_suggester.py` - Updated with `suggest_clips_with_duration_estimates()`
- `clip_composer.py` - Updated with `compose_clips_with_duration_estimates()`
- `smart_editor.py` - Old transcript-based editor (kept as fallback, has clipping bug)
- `transcriber.py` - Deepgram/Whisper transcription

### Server Deployment
- **Location**: `/opt/video-clipper/src/video/`
- **Server**: Hetzner DE (88.99.51.122)
- **Status**: Core silence removal deployed, duration estimation not yet deployed

### Test Data
- `data/audio/C0044.wav` - 11-minute test video with natural pauses
- `data/audio/C0044_full_transcript.json` - Full transcript with word-level timestamps
- Best section for testing: 10:30-11:30 (8 fillers, 6 restarts)

### Test Clips Created
- `data/output/clip1_quality_over_growth_RAW.wav` - 33s raw (1:34-2:07, includes false start)
- `data/output/clip1_quality_over_growth_v3.wav` - 25s clean (1:41.5-2:07, after false start)

## Architecture

### Waveform-Based Flow (waveform_silence_remover.py)
1. **Silero VAD** detects speech/silence from audio waveform
2. Make edit decisions based on actual silence durations
3. Optionally use transcript for filler/restart detection
4. Cut ONLY at true silence points with padding
5. Apply crossfades to prevent clicks/pops

### Duration Estimation (Phase 7)
1. `get_vad_analysis()` - Runs VAD once, caches results
2. `estimate_edited_duration()` - Fast estimate without rendering (~98% accurate)
3. `estimate_all_presets()` - Compare duration across all platforms
4. Integrated into `clip_suggester.py` and `clip_composer.py`

## Key Design Decisions

- **Silero VAD only** - RMS detection removed (doesn't work with background noise)
- **Safe filler removal** - Only removes fillers within VAD-detected silence gaps
- **Opening false start** - Detects when speaker starts, stops, restarts
- **Lead-in padding** - 400ms silence before content starts
- **Duration caching** - VAD results cached for fast multiple queries

## Platform Presets
| Preset | Min Silence | Max Kept | Padding |
|--------|-------------|----------|---------|
| LinkedIn | 500ms | 700ms | 150ms |
| YouTube Shorts | 300ms | 200ms | 100ms |
| TikTok | 200ms | 150ms | 80ms |
| Podcast | 800ms | 1000ms | 200ms |

## Clip Selection Learnings (Phase 8)

### What Makes a Good Clip
1. **Strong hook in first 3 seconds** - questions, bold statements, problem statements
2. **Self-contained** - no dangling references ("as I mentioned...")
3. **Complete thought arc** - setup → insight → takeaway
4. **Clean boundaries** - starts after any false starts, ends at natural conclusion

### Hook Patterns That Work in Transcripts
- Questions: "Have you ever wondered why...?"
- Contrarian: "Most people think X, but actually..."
- Specific numbers: "50% of projects fail because..."
- Problem statements: "The biggest mistake I see is..."
- Bold claims: "This will save you $100,000..."
- Story openers: "Last week on a job site..."

### False Start Detection Gap
**Current limitation**: `transcript_enhanced_editor.py` detects stutters (repeated words within 500ms) but NOT sentence-level false starts (repeated phrases with 2-5 second gaps).

**Example from C0044 at 1:34-1:41**:
- "And if we can't get jobs out on time, if we can't..." [pause 5 seconds]
- "if we can't get jobs out on time, and if we can't deliver..."

**Solution**: For clip selection, choose start points AFTER false starts rather than trying to cut them out. The AI needs to detect these patterns and adjust boundaries.

### Platform Strategy (User's Context)
- **LinkedIn**: Professional tone, 30-90s, educational insights
- **TikTok**: NOT general viral content - building niche industry following
  - Same clips work for both platforms with different formatting
  - TikTok needs: captions, text hook overlays, vertical format
  - Content can be conversational/professional, not high-energy

---

## Session 2025-12-18 (Evening) Notes

### Progress Made
- Researched best practices for social media hooks and retention
- Manually analyzed C0044 transcript and selected 5 potential clips
- Extracted "Quality Over Growth" clip (top pick)
- First extraction (v1) included false start - problem identified
- Re-extracted with better start point (v3) - clean 25-second clip
- Validated by transcribing output and comparing to source

### Key Discovery: Sentence-Level False Starts
The transcript shows a pattern at 1:34-1:41 where the speaker starts a sentence, pauses 5 seconds, then restarts the same sentence. Current restart detection (500ms max gap) doesn't catch this.

**Better approach**: During clip selection, the AI should:
1. Detect repeated phrases/sentences with gaps > 2 seconds
2. Choose clip start point AFTER the restart, not before
3. This is a selection decision, not an editing decision

### Platform Insight
User clarified: TikTok strategy is niche industry audience, not general viral. This means:
- Same clips work for LinkedIn and TikTok
- Formatting differs (captions, overlays) but content is the same
- Don't need high-energy/entertainment style for TikTok

### Next Steps
1. **Rewrite clip selection prompts** to include:
   - Specific hook pattern detection
   - False start awareness (look for repeated phrases with gaps)
   - Niche TikTok guidance (not trying for viral)
2. Test new prompts on C0044 transcript
3. Compare AI selections to manual selections
