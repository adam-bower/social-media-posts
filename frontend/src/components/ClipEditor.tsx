import { useState, useEffect, useCallback } from 'react';
import { WaveformEditor, type SilenceAdjustment } from './WaveformEditor';
import { ClipTranscript } from './ClipTranscript';
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
  SilenceOverride,
} from '../types';

type TabId = 'base' | Platform;

interface ClipEditorProps {
  clip: ClipSuggestion;
  videoId: string;
  transcriptSegments: TranscriptSegment[];
  onClose: () => void;
  onExportComplete?: () => void;
}

const PLATFORM_INFO: Record<Platform, { label: string; icon: string; preset: SilencePreset }> = {
  linkedin: { label: 'LinkedIn', icon: 'in', preset: 'linkedin' },
  tiktok: { label: 'TikTok', icon: 'tt', preset: 'tiktok' },
  youtube_shorts: { label: 'YouTube', icon: 'yt', preset: 'youtube_shorts' },
  instagram_reels: { label: 'Instagram', icon: 'ig', preset: 'tiktok' },
  both: { label: 'Both', icon: '2x', preset: 'linkedin' },
};

export function ClipEditor({
  clip,
  videoId,
  transcriptSegments,
  onClose,
  onExportComplete,
}: ClipEditorProps) {
  // Clip boundaries (editable)
  const [startTime, setStartTime] = useState(clip.start_time);
  const [endTime, setEndTime] = useState(clip.end_time);

  // VAD analysis data
  const [vadAnalysis, setVadAnalysis] = useState<VADAnalysis | null>(null);
  const [previewMetadata, setPreviewMetadata] = useState<ClipPreviewMetadata | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Playback state
  const [currentTime, setCurrentTime] = useState(startTime);
  const [isPlaying, setIsPlaying] = useState(false);

  // Tab state
  const [activeTab, setActiveTab] = useState<TabId>('base');

  // Adjustments per tab
  const [baseAdjustments, setBaseAdjustments] = useState<ClipAdjustments>({});
  const [platformOverrides, setPlatformOverrides] = useState<Record<Platform, ClipAdjustments>>({
    linkedin: {},
    tiktok: {},
    youtube_shorts: {},
    instagram_reels: {},
    both: {},
  });

  // Selected platforms for export
  const [selectedPlatforms, setSelectedPlatforms] = useState<Platform[]>([clip.platform]);

  // Export state
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  // Load VAD analysis
  useEffect(() => {
    async function loadAnalysis() {
      setIsLoading(true);
      setError(null);

      try {
        const [vad, preview] = await Promise.all([
          getVADAnalysis(videoId, 'linkedin'),
          getClipPreviewMetadata(videoId, startTime, endTime, 'linkedin'),
        ]);

        setVadAnalysis(vad);
        setPreviewMetadata(preview);
      } catch (err) {
        console.error('Failed to load VAD analysis:', err);
        setError('Failed to load clip analysis');
      } finally {
        setIsLoading(false);
      }
    }

    loadAnalysis();
  }, [videoId, startTime, endTime]);

  // Handle boundary changes from waveform editor
  const handleBoundaryChange = useCallback((start: number, end: number) => {
    setStartTime(start);
    setEndTime(end);
  }, []);

  // Handle silence adjustment
  const handleSilenceAdjustment = useCallback((silenceIndex: number, keepMs: number) => {
    const override: SilenceOverride = {
      start: vadAnalysis?.silence_segments[silenceIndex]?.start ?? 0,
      end: vadAnalysis?.silence_segments[silenceIndex]?.end ?? 0,
      keep_ms: keepMs,
    };

    if (activeTab === 'base') {
      setBaseAdjustments(prev => ({
        ...prev,
        silence_overrides: [
          ...(prev.silence_overrides?.filter(o => o.start !== override.start) ?? []),
          override,
        ],
      }));
    } else {
      setPlatformOverrides(prev => ({
        ...prev,
        [activeTab]: {
          ...prev[activeTab as Platform],
          silence_overrides: [
            ...(prev[activeTab as Platform]?.silence_overrides?.filter(o => o.start !== override.start) ?? []),
            override,
          ],
        },
      }));
    }
  }, [activeTab, vadAnalysis]);

  // Get current adjustments based on active tab
  const currentAdjustments = activeTab === 'base'
    ? baseAdjustments
    : { ...baseAdjustments, ...platformOverrides[activeTab as Platform] };

  // Convert silence overrides to SilenceAdjustment format for WaveformEditor
  const silenceAdjustments: SilenceAdjustment[] = (currentAdjustments.silence_overrides ?? []).map(override => {
    const silenceIndex = vadAnalysis?.silence_segments.findIndex(
      s => Math.abs(s.start - override.start) < 0.1
    ) ?? -1;
    return {
      silenceIndex,
      keepMs: override.keep_ms,
    };
  }).filter(a => a.silenceIndex >= 0);

  // Toggle platform selection
  const togglePlatform = (platform: Platform) => {
    if (platform === 'both') return; // Don't allow selecting 'both'

    setSelectedPlatforms(prev => {
      if (prev.includes(platform)) {
        return prev.filter(p => p !== platform);
      }
      return [...prev, platform];
    });
  };

  // Handle export
  const handleExport = async () => {
    if (selectedPlatforms.length === 0) return;

    setIsExporting(true);
    setExportError(null);

    try {
      const adjustments: PlatformAdjustments = {
        base: Object.keys(baseAdjustments).length > 0 ? baseAdjustments : undefined,
        overrides: Object.fromEntries(
          Object.entries(platformOverrides).filter(([_, adj]) => Object.keys(adj).length > 0)
        ) as Record<Platform, ClipAdjustments>,
      };

      // Add boundary adjustments if changed
      if (startTime !== clip.start_time || endTime !== clip.end_time) {
        adjustments.base = {
          ...adjustments.base,
          boundaries: {
            start_offset: startTime - clip.start_time,
            end_offset: endTime - clip.end_time,
          },
        };
      }

      await createExport(
        clip.id,
        selectedPlatforms.filter(p => p !== 'both'),
        'linkedin',
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
    setCurrentTime(time);
    // WaveformEditor will pick this up via its own state
  }, []);

  const audioUrl = getAudioUrl(videoId);
  const clipDuration = endTime - startTime;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4">
      <div className="bg-zinc-900 rounded-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col border border-zinc-700 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold text-white">Edit Clip</h2>
            <p className="text-sm text-zinc-400 mt-0.5">
              Adjust boundaries and silence trimming
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-lg transition-colors"
            style={{ minWidth: '44px', minHeight: '44px' }}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="flex items-center gap-3 text-zinc-400">
                <div className="w-6 h-6 border-2 border-zinc-600 border-t-zinc-300 rounded-full animate-spin" />
                <span>Loading clip analysis...</span>
              </div>
            </div>
          ) : error ? (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 text-center">
              <p className="text-red-400">{error}</p>
            </div>
          ) : (
            <>
              {/* Waveform Editor */}
              <WaveformEditor
                audioUrl={audioUrl}
                startTime={startTime}
                endTime={endTime}
                speechSegments={vadAnalysis?.speech_segments}
                silenceSegments={vadAnalysis?.silence_segments}
                presetConfig={vadAnalysis?.config}
                silenceAdjustments={silenceAdjustments}
                onBoundaryChange={handleBoundaryChange}
                onSilenceAdjustment={handleSilenceAdjustment}
                onTimeUpdate={setCurrentTime}
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
              />

              {/* Tabs */}
              <div className="border-b border-zinc-800">
                <div className="flex gap-1">
                  <button
                    onClick={() => setActiveTab('base')}
                    className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
                      activeTab === 'base'
                        ? 'bg-zinc-800 text-white border-b-2 border-emerald-500'
                        : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'
                    }`}
                  >
                    Base
                  </button>
                  {selectedPlatforms.filter(p => p !== 'both').map(platform => (
                    <button
                      key={platform}
                      onClick={() => setActiveTab(platform)}
                      className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors flex items-center gap-2 ${
                        activeTab === platform
                          ? 'bg-zinc-800 text-white border-b-2 border-emerald-500'
                          : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'
                      }`}
                    >
                      <span className="text-[10px] font-bold uppercase opacity-60">
                        {PLATFORM_INFO[platform]?.icon}
                      </span>
                      {PLATFORM_INFO[platform]?.label}
                      {Object.keys(platformOverrides[platform] || {}).length > 0 && (
                        <span className="w-2 h-2 rounded-full bg-amber-500" title="Has overrides" />
                      )}
                    </button>
                  ))}
                </div>
              </div>

              {/* Tab Content */}
              <div className="bg-zinc-800/30 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-medium text-zinc-300">
                    {activeTab === 'base' ? 'Base Settings' : `${PLATFORM_INFO[activeTab as Platform]?.label} Overrides`}
                  </h3>
                  {activeTab !== 'base' && (
                    <span className="text-xs text-zinc-500">
                      Overrides base settings for this platform
                    </span>
                  )}
                </div>

                {/* Silence threshold slider */}
                <div className="space-y-2">
                  <label className="flex items-center justify-between text-sm">
                    <span className="text-zinc-400">Max Kept Silence</span>
                    <span className="font-mono text-white">
                      {currentAdjustments.max_kept_silence_ms ?? vadAnalysis?.config.max_kept_silence_ms ?? 700}ms
                    </span>
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={2000}
                    step={50}
                    value={currentAdjustments.max_kept_silence_ms ?? vadAnalysis?.config.max_kept_silence_ms ?? 700}
                    onChange={(e) => {
                      const value = parseInt(e.target.value);
                      if (activeTab === 'base') {
                        setBaseAdjustments(prev => ({ ...prev, max_kept_silence_ms: value }));
                      } else {
                        setPlatformOverrides(prev => ({
                          ...prev,
                          [activeTab]: { ...prev[activeTab as Platform], max_kept_silence_ms: value },
                        }));
                      }
                    }}
                    className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                  />
                  <div className="flex justify-between text-[10px] text-zinc-500">
                    <span>Aggressive (0ms)</span>
                    <span>Natural (2000ms)</span>
                  </div>
                </div>
              </div>

              {/* Transcript */}
              <div>
                <h3 className="text-sm font-medium text-zinc-300 mb-2">Transcript</h3>
                <ClipTranscript
                  segments={transcriptSegments}
                  clipStart={startTime}
                  clipEnd={endTime}
                  currentTime={currentTime}
                  onSeek={handleSeek}
                  isPlaying={isPlaying}
                />
              </div>

              {/* Stats */}
              {previewMetadata && (
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div className="bg-zinc-800/50 rounded-lg p-3">
                    <div className="text-2xl font-bold text-white">
                      {clipDuration.toFixed(1)}s
                    </div>
                    <div className="text-xs text-zinc-500">Original</div>
                  </div>
                  <div className="bg-zinc-800/50 rounded-lg p-3">
                    <div className="text-2xl font-bold text-emerald-400">
                      {previewMetadata.edited_duration.toFixed(1)}s
                    </div>
                    <div className="text-xs text-zinc-500">Edited</div>
                  </div>
                  <div className="bg-zinc-800/50 rounded-lg p-3">
                    <div className="text-2xl font-bold text-amber-400">
                      -{previewMetadata.time_saved.toFixed(1)}s
                    </div>
                    <div className="text-xs text-zinc-500">
                      Saved ({previewMetadata.percent_reduction.toFixed(0)}%)
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-zinc-800 bg-zinc-900/80">
          {/* Platform selection */}
          <div className="flex items-center gap-4 mb-4">
            <span className="text-sm text-zinc-400">Export to:</span>
            <div className="flex gap-2">
              {(['linkedin', 'tiktok', 'youtube_shorts', 'instagram_reels'] as Platform[]).map(platform => (
                <button
                  key={platform}
                  onClick={() => togglePlatform(platform)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    selectedPlatforms.includes(platform)
                      ? 'bg-emerald-600 text-white'
                      : 'bg-zinc-800 text-zinc-400 hover:text-white'
                  }`}
                  style={{ minHeight: '36px' }}
                >
                  {PLATFORM_INFO[platform].label}
                </button>
              ))}
            </div>
          </div>

          {/* Export error */}
          {exportError && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
              {exportError}
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center justify-between">
            <button
              onClick={onClose}
              className="px-4 py-2.5 text-zinc-400 hover:text-white transition-colors"
              style={{ minHeight: '44px' }}
            >
              Cancel
            </button>
            <button
              onClick={handleExport}
              disabled={isExporting || selectedPlatforms.length === 0 || isLoading}
              className={`
                px-6 py-2.5 rounded-lg font-medium text-sm transition-all
                flex items-center gap-2
                ${isExporting
                  ? 'bg-zinc-700 text-zinc-400 cursor-wait'
                  : selectedPlatforms.length === 0
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
                  Export {selectedPlatforms.length > 0 ? `(${selectedPlatforms.length})` : ''}
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
