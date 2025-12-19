import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.js';
import ZoomPlugin from 'wavesurfer.js/dist/plugins/zoom.js';
import type { SpeechSegment, SilenceSegment, PresetConfig } from '../types';

export interface SilenceAdjustment {
  silenceIndex: number;
  keepMs: number;
}

interface WaveformEditorProps {
  audioUrl: string;
  startTime: number;
  endTime: number;
  speechSegments?: SpeechSegment[];
  silenceSegments?: SilenceSegment[];
  presetConfig?: PresetConfig;
  silenceAdjustments?: SilenceAdjustment[];
  onBoundaryChange?: (start: number, end: number) => void;
  onSilenceAdjustment?: (silenceIndex: number, keepMs: number) => void;
  onPlay?: () => void;
  onPause?: () => void;
  onTimeUpdate?: (time: number) => void;
  compact?: boolean;
  readOnly?: boolean;
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 10);
  return `${mins}:${secs.toString().padStart(2, '0')}.${ms}`;
}

function formatTimeShort(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Context padding in seconds
const CONTEXT_PADDING = 5;

export function WaveformEditor({
  audioUrl,
  startTime,
  endTime,
  speechSegments = [],
  silenceSegments = [],
  presetConfig,
  silenceAdjustments = [],
  onBoundaryChange,
  onSilenceAdjustment,
  onPlay,
  onPause,
  onTimeUpdate,
  compact = false,
  readOnly = false,
}: WaveformEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const regionsRef = useRef<RegionsPlugin | null>(null);
  const clipRegionRef = useRef<any>(null);
  const silenceRegionsRef = useRef<Map<number, any>>(new Map());

  const [isReady, setIsReady] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(startTime);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [zoomLevel, setZoomLevel] = useState(50); // pixels per second

  // Get max kept silence from config or default
  const maxKeptSilenceMs = presetConfig?.max_kept_silence_ms ?? 700;

  // Calculate the view window with 5s padding around clip content
  const viewWindow = useMemo(() => {
    const viewStart = Math.max(0, startTime - CONTEXT_PADDING);
    const viewEnd = endTime + CONTEXT_PADDING;
    return { start: viewStart, end: viewEnd, duration: viewEnd - viewStart };
  }, [startTime, endTime]);

  // Calculate which silences will be trimmed
  const getEffectiveSilences = useCallback(() => {
    return silenceSegments.map((silence, index) => {
      const adjustment = silenceAdjustments.find(a => a.silenceIndex === index);
      const keepMs = adjustment?.keepMs ?? maxKeptSilenceMs;
      const silenceDuration = (silence.end - silence.start) * 1000;
      const trimmedMs = Math.max(0, silenceDuration - keepMs);
      const isTrimmed = trimmedMs > 0;

      return {
        ...silence,
        index,
        keepMs,
        trimmedMs,
        isTrimmed,
        keptDuration: Math.min(silenceDuration, keepMs) / 1000,
      };
    });
  }, [silenceSegments, silenceAdjustments, maxKeptSilenceMs]);

  // Calculate optimal zoom level based on container width
  const calculateOptimalZoom = useCallback((containerWidth: number) => {
    // We want to show the view window (clip + 5s padding on each side)
    const viewDuration = viewWindow.duration;
    // Calculate pixels per second to fit view window in container
    const optimalPxPerSec = containerWidth / viewDuration;
    // Clamp between reasonable bounds
    return Math.max(10, Math.min(500, optimalPxPerSec));
  }, [viewWindow.duration]);

  // Initialize WaveSurfer
  useEffect(() => {
    if (!containerRef.current || !scrollContainerRef.current) return;

    const regions = RegionsPlugin.create();
    regionsRef.current = regions;

    const zoom = ZoomPlugin.create({
      scale: 0.5,
      maxZoom: 500,
    });

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: '#3f3f46', // zinc-700
      progressColor: '#71717a', // zinc-500
      cursorColor: '#ffffff',
      cursorWidth: 2,
      height: compact ? 64 : 96,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      normalize: true,
      minPxPerSec: 10, // Minimum zoom
      plugins: [regions, zoom],
    });

    wavesurferRef.current = ws;

    ws.on('ready', () => {
      const audioDuration = ws.getDuration();
      setIsReady(true);
      setDuration(audioDuration);

      // Calculate optimal zoom to show clip with 5s padding
      if (scrollContainerRef.current) {
        const containerWidth = scrollContainerRef.current.clientWidth;
        const optimalZoom = calculateOptimalZoom(containerWidth);
        setZoomLevel(optimalZoom);
        ws.zoom(optimalZoom);

        // Scroll to show the view window (centered on clip)
        setTimeout(() => {
          if (scrollContainerRef.current) {
            const scrollPosition = viewWindow.start * optimalZoom;
            scrollContainerRef.current.scrollLeft = scrollPosition;
          }
        }, 100);
      }

      updateRegions();
    });

    ws.on('timeupdate', (time) => {
      setCurrentTime(time);
      onTimeUpdate?.(time);

      // Stop at clip end
      if (time >= endTime && isPlaying) {
        ws.pause();
        ws.setTime(startTime);
      }
    });

    ws.on('play', () => {
      setIsPlaying(true);
      onPlay?.();
    });

    ws.on('pause', () => {
      setIsPlaying(false);
      onPause?.();
    });

    ws.on('error', (err) => {
      console.error('WaveSurfer error:', err);
      setError('Failed to load audio');
    });

    // Handle clip boundary region updates
    regions.on('region-updated', (region: any) => {
      if (region.id === 'clip-boundary' && !readOnly) {
        onBoundaryChange?.(region.start, region.end);
      }
    });

    // Load audio
    ws.load(audioUrl);

    return () => {
      ws.destroy();
    };
  }, [audioUrl]);

  // Update regions when data changes
  const updateRegions = useCallback(() => {
    if (!regionsRef.current || !isReady) return;

    const regions = regionsRef.current;

    // Clear existing regions
    regions.clearRegions();
    silenceRegionsRef.current.clear();

    // Add clip boundary region (draggable handles)
    const clipRegion = regions.addRegion({
      id: 'clip-boundary',
      start: startTime,
      end: endTime,
      color: 'rgba(16, 185, 129, 0.15)', // emerald with low transparency
      drag: false,
      resize: !readOnly,
      minLength: 1,
    });
    clipRegionRef.current = clipRegion;

    // Add speech segments (green overlay)
    speechSegments.forEach((speech, index) => {
      // Only show segments within clip bounds
      const segStart = Math.max(speech.start, startTime);
      const segEnd = Math.min(speech.end, endTime);

      if (segEnd > segStart) {
        regions.addRegion({
          id: `speech-${index}`,
          start: segStart,
          end: segEnd,
          color: 'rgba(34, 197, 94, 0.25)', // green-500
          drag: false,
          resize: false,
        });
      }
    });

    // Add silence segments
    const effectiveSilences = getEffectiveSilences();
    effectiveSilences.forEach((silence) => {
      // Only show segments within clip bounds
      const segStart = Math.max(silence.start, startTime);
      const segEnd = Math.min(silence.end, endTime);

      if (segEnd <= segStart) return;

      if (silence.isTrimmed) {
        // Show kept portion (gray)
        const keptEnd = segStart + silence.keptDuration;
        if (keptEnd > segStart) {
          regions.addRegion({
            id: `silence-kept-${silence.index}`,
            start: segStart,
            end: Math.min(keptEnd, segEnd),
            color: 'rgba(161, 161, 170, 0.3)', // zinc-400 - kept silence
            drag: false,
            resize: false,
          });
        }

        // Show trimmed portion (red striped)
        if (keptEnd < segEnd) {
          const trimmedRegion = regions.addRegion({
            id: `silence-trimmed-${silence.index}`,
            start: keptEnd,
            end: segEnd,
            color: 'rgba(239, 68, 68, 0.35)', // red-500 - trimmed
            drag: false,
            resize: !readOnly && !!onSilenceAdjustment,
          });
          silenceRegionsRef.current.set(silence.index, trimmedRegion);
        }
      } else {
        // Short silence - just show gray
        regions.addRegion({
          id: `silence-${silence.index}`,
          start: segStart,
          end: segEnd,
          color: 'rgba(161, 161, 170, 0.2)', // zinc-400 - short silence kept
          drag: false,
          resize: false,
        });
      }
    });
  }, [isReady, startTime, endTime, speechSegments, getEffectiveSilences, readOnly, onSilenceAdjustment]);

  // Update regions when props change
  useEffect(() => {
    updateRegions();
  }, [updateRegions]);

  // Update clip region bounds without full re-render
  useEffect(() => {
    if (clipRegionRef.current && isReady) {
      clipRegionRef.current.setOptions({
        start: startTime,
        end: endTime,
      });
    }
  }, [startTime, endTime, isReady]);

  // Handle zoom changes
  const handleZoom = useCallback((newZoom: number) => {
    if (!wavesurferRef.current || !isReady) return;
    const clampedZoom = Math.max(10, Math.min(500, newZoom));
    setZoomLevel(clampedZoom);
    wavesurferRef.current.zoom(clampedZoom);
  }, [isReady]);

  const handleZoomIn = useCallback(() => {
    handleZoom(zoomLevel * 1.5);
  }, [zoomLevel, handleZoom]);

  const handleZoomOut = useCallback(() => {
    handleZoom(zoomLevel / 1.5);
  }, [zoomLevel, handleZoom]);

  const handleZoomFit = useCallback(() => {
    if (!scrollContainerRef.current || !isReady) return;
    const containerWidth = scrollContainerRef.current.clientWidth;
    const optimalZoom = calculateOptimalZoom(containerWidth);
    handleZoom(optimalZoom);

    // Scroll to view window
    setTimeout(() => {
      if (scrollContainerRef.current) {
        const scrollPosition = viewWindow.start * optimalZoom;
        scrollContainerRef.current.scrollLeft = scrollPosition;
      }
    }, 50);
  }, [isReady, calculateOptimalZoom, handleZoom, viewWindow.start]);

  const handlePlayPause = useCallback(() => {
    if (!wavesurferRef.current || !isReady) return;

    if (isPlaying) {
      wavesurferRef.current.pause();
    } else {
      // Play from current position or clip start
      if (currentTime < startTime || currentTime >= endTime) {
        wavesurferRef.current.setTime(startTime);
      }
      wavesurferRef.current.play();
    }
  }, [isReady, isPlaying, startTime, endTime, currentTime]);

  const handleSeek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!wavesurferRef.current || !isReady || !containerRef.current || !scrollContainerRef.current) return;

    const scrollContainer = scrollContainerRef.current;
    const rect = containerRef.current.getBoundingClientRect();
    const scrollLeft = scrollContainer.scrollLeft;
    const x = e.clientX - rect.left + scrollLeft;
    const totalWidth = containerRef.current.scrollWidth;
    const percentage = x / totalWidth;
    const time = percentage * duration;

    // Clamp to clip bounds
    const clampedTime = Math.max(startTime, Math.min(endTime, time));
    wavesurferRef.current.setTime(clampedTime);
  }, [isReady, duration, startTime, endTime]);

  // Calculate time saved from silence trimming
  const timeSaved = getEffectiveSilences().reduce((acc, s) => acc + s.trimmedMs, 0) / 1000;
  const clipDuration = endTime - startTime;
  const editedDuration = clipDuration - timeSaved;

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-4 text-center">
        <p className="text-red-400 text-sm">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Zoom controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={handleZoomOut}
            disabled={!isReady || zoomLevel <= 10}
            className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            title="Zoom out"
          >
            <svg className="w-4 h-4 text-zinc-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM13 10H7" />
            </svg>
          </button>
          <button
            onClick={handleZoomFit}
            disabled={!isReady}
            className="px-3 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-xs text-zinc-300"
            title="Fit to view"
          >
            Fit
          </button>
          <button
            onClick={handleZoomIn}
            disabled={!isReady || zoomLevel >= 500}
            className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            title="Zoom in"
          >
            <svg className="w-4 h-4 text-zinc-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7" />
            </svg>
          </button>
          <span className="text-xs text-zinc-500 ml-2">
            {Math.round(zoomLevel)} px/s
          </span>
        </div>

        {/* Current time indicator */}
        {isReady && (
          <div className="px-2 py-1 bg-zinc-800 rounded text-xs font-mono text-white">
            {formatTime(currentTime)}
          </div>
        )}
      </div>

      {/* Waveform container with horizontal scroll */}
      <div
        ref={scrollContainerRef}
        className="relative bg-zinc-900 rounded-lg overflow-x-auto overflow-y-hidden border border-zinc-700"
        style={{ maxHeight: compact ? 80 : 112 }}
      >
        {/* Loading state */}
        {!isReady && (
          <div className="absolute inset-0 flex items-center justify-center bg-zinc-900 z-10">
            <div className="flex items-center gap-2 text-zinc-400">
              <div className="w-5 h-5 border-2 border-zinc-600 border-t-zinc-300 rounded-full animate-spin" />
              <span className="text-sm">Loading waveform...</span>
            </div>
          </div>
        )}

        {/* WaveSurfer container */}
        <div
          ref={containerRef}
          className="cursor-crosshair"
          onClick={handleSeek}
          style={{ minWidth: '100%' }}
        />

        {/* Legend */}
        {isReady && (speechSegments.length > 0 || silenceSegments.length > 0) && (
          <div className="absolute bottom-2 right-2 flex items-center gap-3 px-2 py-1 bg-black/60 rounded text-[10px] text-zinc-300">
            <span className="flex items-center gap-1">
              <span className="w-3 h-2 rounded-sm bg-green-500/50" />
              Speech
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-2 rounded-sm bg-zinc-400/40" />
              Kept
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-2 rounded-sm bg-red-500/50" />
              Trimmed
            </span>
          </div>
        )}

        {/* Resize handles hint */}
        {isReady && !readOnly && (
          <div className="absolute top-2 right-2 text-[10px] text-zinc-500">
            Drag edges to adjust
          </div>
        )}
      </div>

      {/* Scroll hint */}
      {isReady && duration > 0 && (
        <div className="text-xs text-zinc-500 text-center">
          Scroll horizontally to navigate • Use zoom controls or pinch to zoom
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center justify-between gap-4">
        <button
          onClick={handlePlayPause}
          disabled={!isReady}
          className={`
            min-w-[120px] px-4 py-2.5 rounded-lg font-medium text-sm transition-all
            touch-manipulation flex items-center justify-center gap-2
            ${isPlaying
              ? 'bg-white text-zinc-900'
              : 'bg-emerald-600 text-white hover:bg-emerald-500 active:bg-emerald-400'
            }
            disabled:opacity-50 disabled:cursor-not-allowed
          `}
          style={{ minHeight: '44px' }} // Touch-friendly
        >
          {isPlaying ? (
            <>
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
              </svg>
              Pause
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
              Play
            </>
          )}
        </button>

        {/* Duration stats */}
        <div className="flex-1 flex items-center justify-end gap-4 text-sm">
          <div className="flex items-center gap-2 text-zinc-400">
            <span className="text-zinc-500">Original:</span>
            <span className="font-mono">{formatTimeShort(clipDuration)}</span>
          </div>
          {timeSaved > 0 && (
            <>
              <span className="text-zinc-600">→</span>
              <div className="flex items-center gap-2 text-emerald-400">
                <span className="text-emerald-500/70">Edited:</span>
                <span className="font-mono">{formatTimeShort(editedDuration)}</span>
                <span className="text-xs text-emerald-500/50">
                  (-{timeSaved.toFixed(1)}s)
                </span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Clip boundary info */}
      <div className="flex items-center justify-between text-xs text-zinc-500 px-1">
        <span className="font-mono">
          {formatTimeShort(startTime)} → {formatTimeShort(endTime)}
        </span>
        <span>
          {speechSegments.length} speech segments · {silenceSegments.length} silences
        </span>
      </div>
    </div>
  );
}
