import { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.js';
import type { SpeechSegment, SilenceSegment, PresetConfig } from '../types';

// Simple debounce utility
function debounce<T extends (...args: never[]) => void>(fn: T, delay: number): T {
  let timeoutId: ReturnType<typeof setTimeout>;
  return ((...args: Parameters<T>) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), delay);
  }) as T;
}

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
  skipTrimmedSilences?: boolean;
  playbackRate?: number;
  onPlaybackRateChange?: (rate: number) => void;
  // Constrain the zoom bar to only show this range (with padding)
  constrainToClip?: boolean;
}

// Zoom bar handle for dragging viewport edges
interface ZoomBarState {
  isDragging: boolean;
  dragType: 'left' | 'right' | 'middle' | null;
  startX: number;
  startViewportLeft: number;
  startViewportRight: number;
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
  skipTrimmedSilences = false,
  playbackRate = 1,
  onPlaybackRateChange,
  constrainToClip = false,
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

  // Viewport state for zoom bar (0-1 range representing portion of timeline visible)
  const [viewportStart, setViewportStart] = useState(0);
  const [viewportEnd, setViewportEnd] = useState(1);

  // Zoom bar drag state
  const zoomBarRef = useRef<HTMLDivElement>(null);
  const [zoomBarDrag, setZoomBarDrag] = useState<ZoomBarState>({
    isDragging: false,
    dragType: null,
    startX: 0,
    startViewportLeft: 0,
    startViewportRight: 0,
  });

  // Track if clip region is selected
  const [isClipSelected, setIsClipSelected] = useState(false);

  // Active region for highlighting (click to select, then easier to drag)
  // Note: Used in region-clicked handler to track selection
  const [, setActiveRegionId] = useState<string | null>(null);

  // Playhead drag state
  const [isPlayheadDragging, setIsPlayheadDragging] = useState(false);

  // Compute the constrained range for the zoom bar (clip + padding)
  const constrainedStart = useMemo(() => {
    if (!constrainToClip || !duration) return 0;
    return Math.max(0, startTime - CONTEXT_PADDING);
  }, [constrainToClip, duration, startTime]);

  const constrainedEnd = useMemo(() => {
    if (!constrainToClip || !duration) return duration;
    return Math.min(duration, endTime + CONTEXT_PADDING);
  }, [constrainToClip, duration, endTime]);

  const constrainedDuration = useMemo(() => {
    return constrainedEnd - constrainedStart;
  }, [constrainedStart, constrainedEnd]);

  // Get max kept silence from config or default
  const maxKeptSilenceMs = presetConfig?.max_kept_silence_ms ?? 700;

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

  // Initialize WaveSurfer
  useEffect(() => {
    if (!containerRef.current || !scrollContainerRef.current) return;

    const regions = RegionsPlugin.create();
    regionsRef.current = regions;

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
      minPxPerSec: 1, // Allow zooming out to see full timeline
      plugins: [regions],
    });

    wavesurferRef.current = ws;

    ws.on('ready', () => {
      const audioDuration = ws.getDuration();
      setIsReady(true);
      setDuration(audioDuration);

      // Calculate view region - if constrainToClip, show only clip + padding
      const clipDuration = endTime - startTime;
      let viewStartTime: number;
      let viewEndTime: number;

      if (constrainToClip) {
        // Show only the clip region with padding
        viewStartTime = Math.max(0, startTime - CONTEXT_PADDING);
        viewEndTime = Math.min(audioDuration, endTime + CONTEXT_PADDING);
      } else {
        // Default: show ~20 seconds centered on clip start
        const maxInitialView = 20;
        const viewDuration = Math.min(clipDuration + CONTEXT_PADDING * 2, maxInitialView);
        viewStartTime = Math.max(0, startTime - CONTEXT_PADDING);
        viewEndTime = Math.min(audioDuration, viewStartTime + viewDuration);
      }

      // Convert to 0-1 viewport range
      const vpStart = viewStartTime / audioDuration;
      const vpEnd = viewEndTime / audioDuration;
      setViewportStart(vpStart);
      setViewportEnd(vpEnd);

      // Calculate zoom level based on viewport
      if (scrollContainerRef.current) {
        const containerWidth = scrollContainerRef.current.clientWidth;
        const actualViewDuration = viewEndTime - viewStartTime;
        const optimalZoom = containerWidth / actualViewDuration;
        const clampedZoom = Math.max(10, Math.min(500, optimalZoom));
        setZoomLevel(clampedZoom);
        ws.zoom(clampedZoom);

        // Scroll to view start
        setTimeout(() => {
          if (scrollContainerRef.current) {
            const scrollPosition = viewStartTime * clampedZoom;
            scrollContainerRef.current.scrollLeft = scrollPosition;
          }
        }, 100);
      }

      updateRegions();
    });

    ws.on('timeupdate', (time) => {
      setCurrentTime(time);
      onTimeUpdate?.(time);

      // Stop at clip end - use ws.isPlaying() since isPlaying state is stale in this closure
      if (time >= endTime && ws.isPlaying()) {
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

    // Handle region clicks for selection - highlight and make easier to resize
    regions.on('region-clicked', (region: any, e: MouseEvent) => {
      e.stopPropagation();

      // Set this region as active
      setActiveRegionId(region.id);

      if (region.id === 'clip-boundary') {
        setIsClipSelected(true);
      }

      // Update region styling to show it's selected
      // Brighter color for selected region
      if (region.id.startsWith('silence-trimmed-') || region.id === 'clip-boundary') {
        const originalColor = region.id === 'clip-boundary'
          ? 'rgba(16, 185, 129, 0.4)' // brighter emerald
          : 'rgba(239, 68, 68, 0.5)'; // brighter red
        region.setOptions({ color: originalColor });
      }
    });

    // Deselect when clicking outside regions
    ws.on('click', () => {
      setIsClipSelected(false);
      setActiveRegionId(null);
    });

    // Load audio
    ws.load(audioUrl);

    return () => {
      ws.destroy();
    };
  }, [audioUrl]);

  // Constrain scrolling to clip region when constrainToClip is enabled
  useEffect(() => {
    if (!constrainToClip || !scrollContainerRef.current || !isReady || !duration) return;

    const scrollContainer = scrollContainerRef.current;
    const minScrollTime = Math.max(0, startTime - CONTEXT_PADDING);
    const maxScrollTime = Math.min(duration, endTime + CONTEXT_PADDING);

    const handleScroll = () => {
      const minScroll = minScrollTime * zoomLevel;
      const maxScroll = maxScrollTime * zoomLevel - scrollContainer.clientWidth;

      if (scrollContainer.scrollLeft < minScroll) {
        scrollContainer.scrollLeft = minScroll;
      } else if (scrollContainer.scrollLeft > maxScroll) {
        scrollContainer.scrollLeft = Math.max(minScroll, maxScroll);
      }
    };

    scrollContainer.addEventListener('scroll', handleScroll);
    return () => scrollContainer.removeEventListener('scroll', handleScroll);
  }, [constrainToClip, isReady, duration, startTime, endTime, zoomLevel]);

  // Skip-preview logic: when playing and skipTrimmedSilences is true,
  // jump over trimmed silence regions
  useEffect(() => {
    if (!skipTrimmedSilences || !wavesurferRef.current || !isPlaying) return;

    const effectiveSilences = getEffectiveSilences();

    // Find if current time is inside a trimmed region
    for (const silence of effectiveSilences) {
      if (!silence.isTrimmed) continue;

      // Only check silences within clip bounds
      const segStart = Math.max(silence.start, startTime);
      const segEnd = Math.min(silence.end, endTime);
      if (segEnd <= segStart) continue;

      // Trimmed portion starts after keptDuration
      const keptEnd = segStart + silence.keptDuration;
      const trimmedStart = keptEnd;
      const trimmedEnd = segEnd;

      // If playhead is in the trimmed portion, skip to end of it
      if (currentTime >= trimmedStart && currentTime < trimmedEnd) {
        wavesurferRef.current.setTime(trimmedEnd);
        break;
      }
    }
  }, [currentTime, isPlaying, skipTrimmedSilences, getEffectiveSilences, startTime, endTime]);

  // Apply playback rate changes
  useEffect(() => {
    if (!wavesurferRef.current || !isReady) return;
    wavesurferRef.current.setPlaybackRate(playbackRate);
  }, [playbackRate, isReady]);

  // Update regions when data changes
  const updateRegions = useCallback(() => {
    if (!regionsRef.current || !isReady) return;

    const regions = regionsRef.current;

    // Clear existing regions
    regions.clearRegions();
    silenceRegionsRef.current.clear();

    // Add clip boundary region (draggable handles)
    // Selected state shows brighter border and handles
    const clipRegion = regions.addRegion({
      id: 'clip-boundary',
      start: startTime,
      end: endTime,
      color: isClipSelected
        ? 'rgba(16, 185, 129, 0.25)' // brighter when selected
        : 'rgba(16, 185, 129, 0.15)', // emerald with low transparency
      drag: false,
      resize: !readOnly,
      minLength: 1,
    });
    clipRegionRef.current = clipRegion;

    // Style the resize handles after region is created
    if (!readOnly && clipRegion.element) {
      const handles = clipRegion.element.querySelectorAll('[data-resize]');
      handles.forEach((handle: Element) => {
        const el = handle as HTMLElement;
        el.style.width = '10px';
        el.style.backgroundColor = 'rgba(16, 185, 129, 0.9)';
        el.style.cursor = 'ew-resize';
      });
    }

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
  }, [isReady, startTime, endTime, speechSegments, getEffectiveSilences, readOnly, onSilenceAdjustment, isClipSelected]);

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
    const clampedZoom = Math.max(1, Math.min(500, newZoom));
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
    if (!scrollContainerRef.current || !isReady || !duration) return;

    // Reset viewport to show clip with 5s padding centered
    const clipCenter = (startTime + endTime) / 2;
    const viewDuration = (endTime - startTime) + (CONTEXT_PADDING * 2);
    const viewStartTime = Math.max(0, clipCenter - viewDuration / 2);
    const viewEndTime = Math.min(duration, viewStartTime + viewDuration);

    const vpStart = viewStartTime / duration;
    const vpEnd = viewEndTime / duration;
    setViewportStart(vpStart);
    setViewportEnd(vpEnd);

    // Calculate and apply zoom
    const containerWidth = scrollContainerRef.current.clientWidth;
    const viewportDuration = viewEndTime - viewStartTime;
    const optimalZoom = containerWidth / viewportDuration;
    const clampedZoom = Math.max(10, Math.min(500, optimalZoom));

    setZoomLevel(clampedZoom);
    wavesurferRef.current?.zoom(clampedZoom);

    // Scroll to view window
    setTimeout(() => {
      if (scrollContainerRef.current) {
        const scrollPosition = viewStartTime * clampedZoom;
        scrollContainerRef.current.scrollLeft = scrollPosition;
      }
    }, 50);
  }, [isReady, duration, startTime, endTime]);

  // Apply viewport changes from zoom bar (for resizing - changes zoom)
  const applyViewport = useCallback((newVpStart: number, newVpEnd: number) => {
    if (!scrollContainerRef.current || !wavesurferRef.current || !containerRef.current || !duration) {
      return;
    }

    // Clamp values
    const vpStart = Math.max(0, Math.min(newVpStart, 0.99));
    const vpEnd = Math.max(vpStart + 0.01, Math.min(newVpEnd, 1));

    setViewportStart(vpStart);
    setViewportEnd(vpEnd);

    // Calculate zoom level based on viewport
    const containerWidth = scrollContainerRef.current.clientWidth;
    const viewportDuration = (vpEnd - vpStart) * duration;
    // Allow lower zoom for full timeline view (min 1 px/s)
    const newZoom = Math.max(1, Math.min(500, containerWidth / viewportDuration));

    setZoomLevel(newZoom);
    wavesurferRef.current.zoom(newZoom);

    // Force the waveform container to be the right width
    // WaveSurfer's zoom is async, so we need to set the width explicitly
    const totalWaveformWidth = duration * newZoom;
    containerRef.current.style.width = `${totalWaveformWidth}px`;

    // Scroll to viewport start
    const scrollContainer = scrollContainerRef.current;
    requestAnimationFrame(() => {
      const scrollPosition = vpStart * duration * newZoom;
      scrollContainer.scrollLeft = scrollPosition;
    });
  }, [duration]);

  // Debounced version for smooth dragging (50ms delay reduces re-renders)
  const debouncedApplyViewport = useMemo(
    () => debounce((newVpStart: number, newVpEnd: number) => {
      applyViewport(newVpStart, newVpEnd);
    }, 30),
    [applyViewport]
  );

  // Playhead drag handlers
  const handlePlayheadDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsPlayheadDragging(true);

    const onMove = (moveEvent: MouseEvent) => {
      if (!zoomBarRef.current || !wavesurferRef.current || !duration) return;

      const rect = zoomBarRef.current.getBoundingClientRect();
      const x = Math.max(0, Math.min(1, (moveEvent.clientX - rect.left) / rect.width));
      const newTime = x * duration;

      // Clamp to clip bounds
      const clampedTime = Math.max(startTime, Math.min(endTime, newTime));
      wavesurferRef.current.setTime(clampedTime);
    };

    const onUp = () => {
      setIsPlayheadDragging(false);
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, [duration, startTime, endTime]);

  // Zoom bar mouse handlers
  const handleZoomBarMouseDown = useCallback((e: React.MouseEvent, type: 'left' | 'right' | 'middle') => {
    e.preventDefault();
    e.stopPropagation();
    setZoomBarDrag({
      isDragging: true,
      dragType: type,
      startX: e.clientX,
      startViewportLeft: viewportStart,
      startViewportRight: viewportEnd,
    });
  }, [viewportStart, viewportEnd]);

  const handleZoomBarMouseMove = useCallback((e: MouseEvent) => {
    if (!zoomBarDrag.isDragging || !zoomBarRef.current) return;

    const barRect = zoomBarRef.current.getBoundingClientRect();
    const deltaX = e.clientX - zoomBarDrag.startX;
    const deltaPct = deltaX / barRect.width;

    const minViewportSize = 0.02; // Minimum 2% of timeline visible

    if (zoomBarDrag.dragType === 'middle') {
      // Drag entire viewport - use debounced for smooth sliding
      const viewportSize = zoomBarDrag.startViewportRight - zoomBarDrag.startViewportLeft;
      let newStart = zoomBarDrag.startViewportLeft + deltaPct;
      let newEnd = newStart + viewportSize;

      // Clamp to bounds
      if (newStart < 0) {
        newStart = 0;
        newEnd = viewportSize;
      }
      if (newEnd > 1) {
        newEnd = 1;
        newStart = 1 - viewportSize;
      }

      debouncedApplyViewport(newStart, newEnd);
    } else if (zoomBarDrag.dragType === 'left') {
      // Resize left edge - changes zoom (debounced)
      let newStart = zoomBarDrag.startViewportLeft + deltaPct;
      newStart = Math.max(0, Math.min(newStart, zoomBarDrag.startViewportRight - minViewportSize));
      debouncedApplyViewport(newStart, zoomBarDrag.startViewportRight);
    } else if (zoomBarDrag.dragType === 'right') {
      // Resize right edge - changes zoom (debounced)
      let newEnd = zoomBarDrag.startViewportRight + deltaPct;
      newEnd = Math.max(zoomBarDrag.startViewportLeft + minViewportSize, Math.min(newEnd, 1));
      debouncedApplyViewport(zoomBarDrag.startViewportLeft, newEnd);
    }
  }, [zoomBarDrag, debouncedApplyViewport]);

  const handleZoomBarMouseUp = useCallback(() => {
    setZoomBarDrag(prev => ({ ...prev, isDragging: false, dragType: null }));
  }, []);

  // Add global mouse listeners for drag
  useEffect(() => {
    if (zoomBarDrag.isDragging) {
      window.addEventListener('mousemove', handleZoomBarMouseMove);
      window.addEventListener('mouseup', handleZoomBarMouseUp);
      return () => {
        window.removeEventListener('mousemove', handleZoomBarMouseMove);
        window.removeEventListener('mouseup', handleZoomBarMouseUp);
      };
    }
  }, [zoomBarDrag.isDragging, handleZoomBarMouseMove, handleZoomBarMouseUp]);

  // Click on zoom bar to jump to position
  const handleZoomBarClick = useCallback((e: React.MouseEvent) => {
    if (!zoomBarRef.current || !duration) return;

    const rect = zoomBarRef.current.getBoundingClientRect();
    const clickPct = (e.clientX - rect.left) / rect.width;

    // Center viewport on click position
    const viewportSize = viewportEnd - viewportStart;
    let newStart = clickPct - viewportSize / 2;
    let newEnd = clickPct + viewportSize / 2;

    // Clamp to bounds
    if (newStart < 0) {
      newStart = 0;
      newEnd = viewportSize;
    }
    if (newEnd > 1) {
      newEnd = 1;
      newStart = 1 - viewportSize;
    }

    applyViewport(newStart, newEnd);
  }, [duration, viewportStart, viewportEnd, applyViewport]);

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

  // Spacebar play/pause keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Only handle spacebar, and not when typing in an input
      if (e.code === 'Space' &&
          e.target instanceof Element &&
          !['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) {
        e.preventDefault();
        handlePlayPause();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handlePlayPause]);

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
            disabled={!isReady || zoomLevel <= 1}
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
          className="cursor-crosshair relative"
          onClick={handleSeek}
          style={{ minWidth: '100%' }}
        />

        {/* Playhead line overlay on waveform - positioned absolutely within scroll container */}
        {isReady && duration > 0 && (
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-white pointer-events-none z-10"
            style={{
              // Position is relative to the full waveform width, not container
              left: `${currentTime * zoomLevel}px`,
              boxShadow: '0 0 6px rgba(255,255,255,0.8)',
            }}
          />
        )}

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

      {/* Premiere Pro-style Zoom Bar */}
      {isReady && duration > 0 && (
        <div className="px-1">
          {/* Timeline with clip indicator */}
          <div
            ref={zoomBarRef}
            className="relative h-8 bg-zinc-800 rounded cursor-pointer select-none"
            onClick={handleZoomBarClick}
          >
            {/* Time markers - use constrained range if enabled */}
            <div className="absolute inset-x-0 top-0 h-3 flex items-center justify-between px-2 text-[9px] text-zinc-500 font-mono pointer-events-none">
              <span>{formatTimeShort(constrainToClip ? constrainedStart : 0)}</span>
              <span>{formatTimeShort(constrainToClip ? constrainedStart + constrainedDuration / 2 : duration / 2)}</span>
              <span>{formatTimeShort(constrainToClip ? constrainedEnd : duration)}</span>
            </div>

            {/* Clip region indicator on the minimap */}
            <div
              className="absolute top-3 bottom-0 bg-emerald-500/30 pointer-events-none"
              style={constrainToClip ? {
                // When constrained, show clip position relative to the constrained range
                left: `${((startTime - constrainedStart) / constrainedDuration) * 100}%`,
                width: `${((endTime - startTime) / constrainedDuration) * 100}%`,
              } : {
                left: `${(startTime / duration) * 100}%`,
                width: `${((endTime - startTime) / duration) * 100}%`,
              }}
            />

            {/* Current playhead indicator - DRAGGABLE */}
            <div
              className={`absolute top-3 bottom-0 z-20 flex flex-col items-center cursor-ew-resize group ${
                isPlayheadDragging ? 'opacity-100' : ''
              }`}
              style={constrainToClip ? {
                left: `${((currentTime - constrainedStart) / constrainedDuration) * 100}%`,
                transform: 'translateX(-50%)',
              } : {
                left: `${(currentTime / duration) * 100}%`,
                transform: 'translateX(-50%)',
              }}
              onMouseDown={handlePlayheadDragStart}
            >
              {/* Playhead handle (top triangle) */}
              <div
                className={`w-0 h-0 border-l-[6px] border-r-[6px] border-t-[8px] border-l-transparent border-r-transparent ${
                  isPlayheadDragging ? 'border-t-emerald-400' : 'border-t-white group-hover:border-t-emerald-400'
                } transition-colors`}
              />
              {/* Playhead line */}
              <div
                className={`w-0.5 flex-1 ${
                  isPlayheadDragging ? 'bg-emerald-400' : 'bg-white group-hover:bg-emerald-400'
                } transition-colors`}
              />
            </div>

            {/* Viewport selector (draggable region) */}
            <div
              className={`absolute top-3 bottom-0 border-2 rounded-sm transition-colors ${
                zoomBarDrag.isDragging
                  ? 'border-emerald-400 bg-emerald-500/10'
                  : 'border-zinc-400 bg-zinc-600/20 hover:border-zinc-300'
              }`}
              style={constrainToClip && constrainedDuration > 0 ? {
                // Convert viewport (0-1 of full duration) to constrained range
                left: `${Math.max(0, (viewportStart * duration - constrainedStart) / constrainedDuration) * 100}%`,
                width: `${Math.min(1, (viewportEnd - viewportStart) * duration / constrainedDuration) * 100}%`,
                minWidth: '20px',
              } : {
                left: `${viewportStart * 100}%`,
                width: `${(viewportEnd - viewportStart) * 100}%`,
                minWidth: '20px',
              }}
              onMouseDown={(e) => handleZoomBarMouseDown(e, 'middle')}
            >
              {/* Left handle */}
              <div
                className="absolute left-0 top-0 bottom-0 w-2 cursor-ew-resize hover:bg-white/20 flex items-center justify-center"
                onMouseDown={(e) => {
                  e.stopPropagation();
                  handleZoomBarMouseDown(e, 'left');
                }}
              >
                <div className="w-0.5 h-3 bg-zinc-400 rounded-full" />
              </div>

              {/* Right handle */}
              <div
                className="absolute right-0 top-0 bottom-0 w-2 cursor-ew-resize hover:bg-white/20 flex items-center justify-center"
                onMouseDown={(e) => {
                  e.stopPropagation();
                  handleZoomBarMouseDown(e, 'right');
                }}
              >
                <div className="w-0.5 h-3 bg-zinc-400 rounded-full" />
              </div>
            </div>
          </div>

          {/* Hint */}
          <div className="text-[10px] text-zinc-500 text-center mt-1">
            Drag viewport to navigate • Drag edges to zoom
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
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

          {/* Speed controls */}
          {onPlaybackRateChange && (
            <div className="flex items-center gap-1 bg-zinc-800 rounded-lg p-1">
              <button
                onClick={() => onPlaybackRateChange(Math.max(0.75, playbackRate - 0.05))}
                disabled={!isReady || playbackRate <= 0.75}
                className="p-2 rounded hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                title="Slower"
              >
                <svg className="w-3 h-3 text-zinc-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
                </svg>
              </button>
              <button
                onClick={() => onPlaybackRateChange(1)}
                className="px-2 py-1 text-xs font-mono text-zinc-300 hover:bg-zinc-700 rounded transition-colors min-w-[48px]"
                title="Reset to 1x"
              >
                {playbackRate.toFixed(2)}x
              </button>
              <button
                onClick={() => onPlaybackRateChange(Math.min(1.5, playbackRate + 0.05))}
                disabled={!isReady || playbackRate >= 1.5}
                className="p-2 rounded hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                title="Faster"
              >
                <svg className="w-3 h-3 text-zinc-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
              </button>
            </div>
          )}
        </div>

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
