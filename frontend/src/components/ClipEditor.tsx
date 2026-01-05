import { useState, useEffect, useCallback, useMemo } from 'react';
import { WaveformEditor } from './WaveformEditor';
import { ClipTranscript } from './ClipTranscript';
import { PanningTranscript } from './PanningTranscript';
import {
  getVADAnalysis,
  getClipPreviewMetadata,
  getAudioUrl,
  createExport,
} from '../api/client';
import type {
  ClipSuggestion,
  TranscriptSegment,
  VADAnalysis,
  ClipPreviewMetadata,
  Platform,
  SilencePreset,
  PlatformAdjustments,
  ClipAdjustments,
} from '../types';

// Platform configuration - ordered by aggressiveness (least to most)
// LinkedIn: 700ms, YouTube Shorts: 200ms, TikTok: 150ms
const PLATFORMS: {
  id: Platform;
  label: string;
  icon: string;
  preset: SilencePreset;
  description: string;
}[] = [
  { id: 'linkedin', label: 'LinkedIn', icon: 'in', preset: 'linkedin', description: 'Natural pacing, 700ms max silence' },
  { id: 'youtube_shorts', label: 'YouTube', icon: 'yt', preset: 'youtube_shorts', description: 'Quick pacing, 200ms max silence' },
  { id: 'tiktok', label: 'TikTok', icon: 'tt', preset: 'tiktok', description: 'Fast pacing, 150ms max silence' },
];

interface ClipEditorProps {
  clip: ClipSuggestion;
  videoId: string;
  transcriptSegments: TranscriptSegment[];
  onClose: () => void;
  onExportComplete?: () => void;
}

export function ClipEditor({
  clip,
  videoId,
  transcriptSegments,
  onClose,
  onExportComplete,
}: ClipEditorProps) {
  // Active platform tab
  const [activePlatform, setActivePlatform] = useState<Platform>('linkedin');

  // Clip boundaries (editable)
  const [startTime, setStartTime] = useState(clip.start_time);
  const [endTime, setEndTime] = useState(clip.end_time);

  // VAD analysis data per platform
  const [vadAnalysisByPlatform, setVadAnalysisByPlatform] = useState<Record<Platform, VADAnalysis | null>>({
    linkedin: null,
    tiktok: null,
    youtube_shorts: null,
    instagram_reels: null, // kept for type compatibility but not used
    both: null,
  });

  // Preview metadata per platform (shows time saved, edited duration)
  const [previewMetadata, setPreviewMetadata] = useState<Record<Platform, ClipPreviewMetadata | null>>({
    linkedin: null,
    tiktok: null,
    youtube_shorts: null,
    instagram_reels: null, // kept for type compatibility but not used
    both: null,
  });

  // Loading states
  const [loadingPlatforms, setLoadingPlatforms] = useState<Set<Platform>>(new Set());
  const [error, setError] = useState<string | null>(null);

  // Playback state
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  // Preview mode - when true, skips over trimmed silences
  const [previewMode, setPreviewMode] = useState(false);

  // Playback speed (0.75x to 1.5x)
  const [playbackRate, setPlaybackRate] = useState(1);

  // Per-platform adjustments (max silence slider)
  const [platformAdjustments, setPlatformAdjustments] = useState<Record<Platform, ClipAdjustments>>({
    linkedin: {},
    tiktok: {},
    youtube_shorts: {},
    instagram_reels: {}, // kept for type compatibility
    both: {},
  });

  // Track if initial preload is done
  const [isPreloading, setIsPreloading] = useState(true);

  // Show/hide advanced settings
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false);

  // Selected platforms for export
  const [selectedPlatforms, setSelectedPlatforms] = useState<Set<Platform>>(new Set([clip.platform]));

  // Export state
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  // Get current platform's preset
  const currentPlatformConfig = PLATFORMS.find(p => p.id === activePlatform);
  const currentPreset = currentPlatformConfig?.preset ?? 'linkedin';

  // Load VAD analysis and preview metadata for a platform
  const loadPlatformData = useCallback(async (platform: Platform) => {
    const platformConfig = PLATFORMS.find(p => p.id === platform);
    if (!platformConfig) return;

    setLoadingPlatforms(prev => new Set(prev).add(platform));
    setError(null);

    try {
      const [vad, preview] = await Promise.all([
        getVADAnalysis(videoId, platformConfig.preset),
        getClipPreviewMetadata(videoId, startTime, endTime, platformConfig.preset),
      ]);

      setVadAnalysisByPlatform(prev => ({ ...prev, [platform]: vad }));
      setPreviewMetadata(prev => ({ ...prev, [platform]: preview }));
    } catch (err) {
      console.error(`Failed to load data for ${platform}:`, err);
      setError(`Failed to load ${platformConfig.label} preview`);
    } finally {
      setLoadingPlatforms(prev => {
        const next = new Set(prev);
        next.delete(platform);
        return next;
      });
    }
  }, [videoId, startTime, endTime]);

  // Preload ALL platforms on mount to show time saved in tabs
  useEffect(() => {
    async function preloadAllPlatforms() {
      setIsPreloading(true);

      // Load all platforms in parallel
      await Promise.all(
        PLATFORMS.map(platform => loadPlatformData(platform.id))
      );

      setIsPreloading(false);
    }

    preloadAllPlatforms();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only run once on mount

  // Load data for active platform when it changes (if not already loaded)
  useEffect(() => {
    if (!vadAnalysisByPlatform[activePlatform] && !isPreloading) {
      loadPlatformData(activePlatform);
    }
  }, [activePlatform, vadAnalysisByPlatform, loadPlatformData, isPreloading]);

  // Get the original audio URL (full video audio)
  const originalAudioUrl = useMemo(() => {
    return getAudioUrl(videoId);
  }, [videoId]);

  // Handle boundary changes from waveform editor
  const handleBoundaryChange = useCallback((start: number, end: number) => {
    setStartTime(start);
    setEndTime(end);
    // Clear ALL cached metadata so it reloads with new boundaries
    setPreviewMetadata({
      linkedin: null,
      tiktok: null,
      youtube_shorts: null,
      instagram_reels: null,
      both: null,
    });
  }, []);

  // Handle max silence slider change
  const handleMaxSilenceChange = useCallback((platform: Platform, value: number) => {
    setPlatformAdjustments(prev => ({
      ...prev,
      [platform]: { ...prev[platform], max_kept_silence_ms: value },
    }));
  }, []);

  // Toggle platform selection for export
  const togglePlatformSelection = (platform: Platform) => {
    setSelectedPlatforms(prev => {
      const next = new Set(prev);
      if (next.has(platform)) {
        next.delete(platform);
      } else {
        next.add(platform);
      }
      return next;
    });
  };

  // Handle export
  const handleExport = async () => {
    if (selectedPlatforms.size === 0) return;

    setIsExporting(true);
    setExportError(null);

    try {
      // Build adjustments
      const adjustments: PlatformAdjustments = {
        overrides: Object.fromEntries(
          Object.entries(platformAdjustments).filter(([_, adj]) => Object.keys(adj).length > 0)
        ) as Record<Platform, ClipAdjustments>,
      };

      // Add boundary adjustments if changed
      if (startTime !== clip.start_time || endTime !== clip.end_time) {
        adjustments.base = {
          boundaries: {
            start_offset: startTime - clip.start_time,
            end_offset: endTime - clip.end_time,
          },
        };
      }

      await createExport(
        clip.id,
        Array.from(selectedPlatforms).filter(p => p !== 'both'),
        currentPreset,
        true,
        adjustments
      );

      onExportComplete?.();
      onClose();
    } catch (err) {
      console.error('Export failed:', err);
      setExportError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  // Handle seek from transcript
  const handleSeek = useCallback((time: number) => {
    // Convert absolute time to relative time in the clip
    const relativeTime = time - startTime;
    setCurrentTime(Math.max(0, relativeTime));
  }, [startTime]);

  // Current platform data
  const currentVadAnalysis = vadAnalysisByPlatform[activePlatform];
  const currentPreviewMetadata = previewMetadata[activePlatform];
  const isLoading = loadingPlatforms.has(activePlatform);

  const clipDuration = endTime - startTime;

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col">
      {/* Header - sticky at top */}
      <div className="sticky top-0 z-10 bg-zinc-900 border-b border-zinc-800 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={onClose}
              className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors"
              style={{ minWidth: '44px', minHeight: '44px' }}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
            </button>
            <div>
              <h1 className="text-lg font-semibold text-white">Edit Clip</h1>
              <p className="text-sm text-zinc-400 mt-0.5 line-clamp-1">
                {clip.hook_reason || clip.transcript_excerpt || `Clip ${clip.id.slice(0, 8)}`}
              </p>
            </div>
          </div>

          {/* Export button in header */}
          <button
            onClick={handleExport}
            disabled={isExporting || selectedPlatforms.size === 0 || isLoading}
            className={`
              px-6 py-2.5 rounded-lg font-medium text-sm transition-all
              flex items-center gap-2
              ${isExporting
                ? 'bg-zinc-700 text-zinc-400 cursor-wait'
                : selectedPlatforms.size === 0
                  ? 'bg-zinc-700 text-zinc-500 cursor-not-allowed'
                  : 'bg-emerald-600 text-white hover:bg-emerald-500'
              }
            `}
            style={{ minHeight: '44px' }}
          >
            {isExporting ? (
              <>
                <div className="w-4 h-4 border-2 border-zinc-500 border-t-white rounded-full animate-spin" />
                Exporting...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
                Export {selectedPlatforms.size > 0 ? `(${selectedPlatforms.size})` : ''}
              </>
            )}
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto px-6 py-6 space-y-6">
          {/* Error state */}
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 text-center">
              <p className="text-red-400">{error}</p>
              <button
                onClick={() => loadPlatformData(activePlatform)}
                className="mt-2 px-4 py-2 bg-zinc-800 text-zinc-300 rounded-lg hover:bg-zinc-700 transition-colors"
              >
                Retry
              </button>
            </div>
          )}

          {/* Export error */}
          {exportError && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
              {exportError}
            </div>
          )}

          {/* Single waveform with preview mode toggle */}
          <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-5">
            {/* Header with mode toggle */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <h2 className="text-base font-semibold text-white">
                  Clip Editor
                </h2>
                {/* Preview mode indicator */}
                {previewMode && (
                  <span className="px-2 py-0.5 bg-emerald-500/20 text-emerald-400 text-xs rounded-full">
                    Preview Mode
                  </span>
                )}
              </div>

              {/* Stats */}
              {currentPreviewMetadata && currentPreviewMetadata.time_saved > 0 ? (
                <div className="flex items-center gap-3 text-sm">
                  <span className="text-zinc-400 font-mono">{clipDuration.toFixed(1)}s</span>
                  <span className="text-zinc-600">→</span>
                  <span className="text-emerald-400 font-mono">{currentPreviewMetadata.edited_duration.toFixed(1)}s</span>
                  <span className="text-emerald-500/70 text-xs">(-{currentPreviewMetadata.time_saved.toFixed(1)}s)</span>
                </div>
              ) : (
                <span className="text-zinc-400 font-mono text-sm">{clipDuration.toFixed(1)}s</span>
              )}
            </div>

            {/* Panning transcript above waveform */}
            <PanningTranscript
              segments={transcriptSegments}
              clipStart={startTime}
              clipEnd={endTime}
              currentTime={startTime + currentTime}
              onSeek={handleSeek}
              isPlaying={isPlaying}
            />

            {/* Loading state */}
            {isLoading ? (
              <div className="h-32 flex items-center justify-center">
                <div className="flex items-center gap-3 text-zinc-400">
                  <div className="w-5 h-5 border-2 border-zinc-600 border-t-zinc-300 rounded-full animate-spin" />
                  <span className="text-sm">Loading {currentPlatformConfig?.label} analysis...</span>
                </div>
              </div>
            ) : (
              <WaveformEditor
                audioUrl={originalAudioUrl}
                startTime={startTime}
                endTime={endTime}
                speechSegments={currentVadAnalysis?.speech_segments}
                silenceSegments={currentVadAnalysis?.silence_segments}
                presetConfig={currentVadAnalysis?.config}
                onBoundaryChange={handleBoundaryChange}
                onTimeUpdate={setCurrentTime}
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                skipTrimmedSilences={previewMode}
                playbackRate={playbackRate}
                onPlaybackRateChange={setPlaybackRate}
                constrainToClip
              />
            )}

            {/* Preview mode toggle */}
            <div className="mt-4 flex items-center justify-center gap-2">
              <button
                onClick={() => setPreviewMode(false)}
                className={`
                  px-4 py-2 rounded-lg text-sm font-medium transition-all
                  ${!previewMode
                    ? 'bg-zinc-700 text-white'
                    : 'bg-zinc-800 text-zinc-400 hover:text-zinc-300'
                  }
                `}
              >
                Edit Mode
              </button>
              <button
                onClick={() => setPreviewMode(true)}
                className={`
                  px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2
                  ${previewMode
                    ? 'bg-emerald-600 text-white'
                    : 'bg-zinc-800 text-zinc-400 hover:text-zinc-300'
                  }
                `}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                </svg>
                Preview (Skip Silences)
              </button>
            </div>

            {/* Hint */}
            <p className="text-center text-xs text-zinc-500 mt-2">
              {previewMode
                ? 'Playing skips over red (trimmed) sections'
                : 'Drag edges to adjust clip boundaries'}
            </p>
          </div>

          {/* Platform selection row */}
          <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-white">Export Platforms</h2>
              <span className="text-xs text-zinc-500">
                Select platforms to export
              </span>
            </div>

            <div className="flex flex-wrap gap-3">
              {PLATFORMS.map(platform => {
                const isSelected = selectedPlatforms.has(platform.id);
                const isActive = activePlatform === platform.id;
                const meta = previewMetadata[platform.id];
                const isLoadingPlatform = loadingPlatforms.has(platform.id);

                return (
                  <button
                    key={platform.id}
                    onClick={() => {
                      togglePlatformSelection(platform.id);
                      setActivePlatform(platform.id);
                    }}
                    className={`
                      relative px-4 py-3 rounded-lg text-sm font-medium transition-all
                      flex flex-col items-start gap-1 min-w-[140px]
                      ${isSelected
                        ? 'bg-emerald-600/20 border-2 border-emerald-500 text-white'
                        : 'bg-zinc-800 border-2 border-transparent text-zinc-300 hover:bg-zinc-700'
                      }
                      ${isActive ? 'ring-2 ring-zinc-500 ring-offset-2 ring-offset-zinc-900' : ''}
                    `}
                    style={{ minHeight: '64px' }}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-bold uppercase opacity-60">
                        {platform.icon}
                      </span>
                      {platform.label}
                      {isSelected && (
                        <svg className="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </div>
                    <div className="text-[11px] text-zinc-500">
                      {isLoadingPlatform ? (
                        <span className="flex items-center gap-1">
                          <div className="w-2 h-2 border border-zinc-500 border-t-zinc-300 rounded-full animate-spin" />
                          Loading...
                        </span>
                      ) : meta && meta.time_saved > 0 ? (
                        <span className="text-emerald-400">-{meta.time_saved.toFixed(1)}s</span>
                      ) : (
                        platform.description
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Advanced settings (hidden by default) */}
          <div className="bg-zinc-900 rounded-xl border border-zinc-800">
            <button
              onClick={() => setShowAdvancedSettings(!showAdvancedSettings)}
              className="w-full px-5 py-4 flex items-center justify-between text-left"
            >
              <span className="text-sm font-medium text-zinc-400">Advanced Settings</span>
              <svg
                className={`w-4 h-4 text-zinc-500 transition-transform ${showAdvancedSettings ? 'rotate-180' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {showAdvancedSettings && (
              <div className="px-5 pb-5 space-y-4">
                {/* Silence threshold slider */}
                <div className="space-y-2">
                  <label className="flex items-center justify-between text-sm">
                    <span className="text-zinc-400">Max Kept Silence</span>
                    <span className="font-mono text-white">
                      {platformAdjustments[activePlatform]?.max_kept_silence_ms ?? currentVadAnalysis?.config.max_kept_silence_ms ?? 700}ms
                    </span>
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={2000}
                    step={50}
                    value={platformAdjustments[activePlatform]?.max_kept_silence_ms ?? currentVadAnalysis?.config.max_kept_silence_ms ?? 700}
                    onChange={(e) => handleMaxSilenceChange(activePlatform, parseInt(e.target.value))}
                    className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                  />
                  <div className="flex justify-between text-[10px] text-zinc-500">
                    <span>Aggressive (0ms)</span>
                    <span>Natural (2000ms)</span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Transcript section */}
          <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-5">
            <h2 className="text-base font-semibold text-white mb-4">Transcript</h2>
            <ClipTranscript
              segments={transcriptSegments}
              clipStart={startTime}
              clipEnd={endTime}
              currentTime={startTime + currentTime}
              onSeek={handleSeek}
              isPlaying={isPlaying}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
