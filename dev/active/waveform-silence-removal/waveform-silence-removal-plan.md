# Waveform-First Silence Removal Implementation Plan

## Overview
Build a waveform-first audio editing pipeline that detects silence purely from audio analysis (RMS envelope or Silero VAD), rather than relying on potentially inaccurate transcription timestamps. This fixes the "discrepancies" word clipping bug and provides more reliable silence removal.

## Goals
- Fix word clipping bugs caused by inaccurate transcript timestamps
- Implement pure waveform-based silence detection (RMS + Silero VAD)
- Support platform-specific presets (LinkedIn, TikTok, YouTube Shorts, Podcast)
- Make transcript-based enhancements optional (for filler/restart detection)
- Prevent audio artifacts with crossfades and padding

## Technical Approach

### Core Principle
**Waveform determines WHERE to cut, transcript determines WHAT to cut.**

1. **RMS Envelope Analysis**: Compute RMS over 20ms windows with 10ms hop to detect actual silence
2. **Silero VAD Option**: Neural network-based speech detection for noisy audio
3. **Padding Buffers**: 100-200ms padding around all speech segments
4. **Crossfades**: 10ms fades at cut points to prevent clicks
5. **Preset System**: Different thresholds/timing for each platform

### Preset Parameters
| Preset | Silence Threshold | Min Silence | Max Kept Silence | Padding |
|--------|-------------------|-------------|------------------|---------|
| LinkedIn | -35 dB | 500ms | 700ms | 150ms |
| YouTube Shorts | -35 dB | 300ms | 200ms | 100ms |
| TikTok | -35 dB | 200ms | 150ms | 80ms |
| Podcast | -35 dB | 800ms | 1000ms | 200ms |

## Files to Create/Modify

### Create
- `/opt/video-clipper/src/video/waveform_silence_remover.py` - Core RMS-based silence removal
- `/opt/video-clipper/src/video/transcript_enhanced_editor.py` - Optional transcript enhancements

### Modify
- `/opt/video-clipper/src/video/audio_assembler.py` - Integrate new waveform-first approach
- `/opt/video-clipper/requirements.txt` - Add torch/torchaudio for Silero VAD

## Dependencies
- `numpy` - RMS computation (already installed)
- `soundfile` - Audio I/O (already installed)
- `torch>=1.12.0` - For Silero VAD
- `torchaudio>=0.12.0` - Audio loading for Silero

## Success Criteria
- [ ] RMS-based silence detection works without transcript
- [ ] Silero VAD works as alternative detection method
- [ ] "discrepancies" word is NOT clipped in test audio
- [ ] All platform presets produce expected results
- [ ] Crossfades prevent clicks/pops at cut points
- [ ] API supports vad_method parameter toggle
- [ ] Old smart_editor.py code remains as fallback
