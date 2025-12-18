import { useEffect, useRef, useState, useCallback } from 'react';
import WaveSurfer from 'wavesurfer.js';
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.js';

interface SilenceRegion {
  start: number;
  end: number;
}

interface WaveformEditorProps {
  audioUrl: string;
  startTime: number;
  endTime: number;
  silences?: SilenceRegion[];
  onBoundaryChange?: (start: number, end: number) => void;
  onPlay?: () => void;
  onPause?: () => void;
  compact?: boolean;
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function WaveformEditor({
  audioUrl,
  startTime,
  endTime,
  silences = [],
  onBoundaryChange,
  onPlay,
  onPause,
  compact = false,
}: WaveformEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const regionsRef = useRef<RegionsPlugin | null>(null);
  const clipRegionRef = useRef<any>(null);

  const [isReady, setIsReady] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Initialize WaveSurfer
  useEffect(() => {
    if (!containerRef.current) return;

    const regions = RegionsPlugin.create();
    regionsRef.current = regions;

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: '#52525b', // zinc-600
      progressColor: '#a1a1aa', // zinc-400
      cursorColor: '#ffffff',
      cursorWidth: 2,
      height: compact ? 60 : 80,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      normalize: true,
      plugins: [regions],
    });

    wavesurferRef.current = ws;

    ws.on('ready', () => {
      setIsReady(true);
      setDuration(ws.getDuration());

      // Add clip boundary region (draggable)
      const clipRegion = regions.addRegion({
        start: startTime,
        end: endTime,
        color: 'rgba(16, 185, 129, 0.2)', // emerald with transparency
        drag: false,
        resize: true,
      });
      clipRegionRef.current = clipRegion;

      // Add silence regions (visual only, not draggable)
      silences.forEach((silence) => {
        // Only show silences within clip bounds
        if (silence.end > startTime && silence.start < endTime) {
          regions.addRegion({
            start: Math.max(silence.start, startTime),
            end: Math.min(silence.end, endTime),
            color: 'rgba(239, 68, 68, 0.3)', // red with transparency
            drag: false,
            resize: false,
          });
        }
      });
    });

    ws.on('timeupdate', (time) => {
      setCurrentTime(time);
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

    // Handle region updates
    regions.on('region-updated', (region: any) => {
      if (region === clipRegionRef.current) {
        onBoundaryChange?.(region.start, region.end);
      }
    });

    // Load audio
    ws.load(audioUrl);

    return () => {
      ws.destroy();
    };
  }, [audioUrl]); // Only re-init on audioUrl change

  // Update region when props change (without full re-init)
  useEffect(() => {
    if (clipRegionRef.current && isReady) {
      clipRegionRef.current.setOptions({
        start: startTime,
        end: endTime,
      });
    }
  }, [startTime, endTime, isReady]);

  const handlePlayPause = useCallback(() => {
    if (!wavesurferRef.current || !isReady) return;

    if (isPlaying) {
      wavesurferRef.current.pause();
    } else {
      // Play from clip start
      wavesurferRef.current.setTime(startTime);
      wavesurferRef.current.play();
    }
  }, [isReady, isPlaying, startTime]);

  const handleSeek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!wavesurferRef.current || !isReady || !containerRef.current) return;

    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const percentage = x / rect.width;
    const time = percentage * duration;

    wavesurferRef.current.setTime(time);
  }, [isReady, duration]);

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-center">
        <p className="text-red-400 text-sm">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* Waveform container */}
      <div
        className="relative bg-zinc-800 rounded-lg overflow-hidden cursor-crosshair"
        onClick={handleSeek}
      >
        {/* Loading state */}
        {!isReady && (
          <div className="absolute inset-0 flex items-center justify-center bg-zinc-800 z-10">
            <div className="flex items-center gap-2 text-zinc-400">
              <div className="w-4 h-4 border-2 border-zinc-600 border-t-zinc-300 rounded-full animate-spin" />
              <span className="text-sm">Loading waveform...</span>
            </div>
          </div>
        )}

        {/* WaveSurfer container */}
        <div ref={containerRef} className="w-full" />

        {/* Legend */}
        {isReady && silences.length > 0 && (
          <div className="absolute bottom-1 right-2 flex items-center gap-3 text-[10px] text-zinc-500">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-sm bg-emerald-500/40" />
              Clip
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-sm bg-red-500/40" />
              Silence (removed)
            </span>
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between">
        <button
          onClick={handlePlayPause}
          disabled={!isReady}
          className={`
            px-4 py-2 rounded-lg font-medium text-sm transition-all touch-manipulation flex items-center gap-2
            ${isPlaying
              ? 'bg-white text-zinc-900'
              : 'bg-zinc-700 text-white hover:bg-zinc-600 active:bg-zinc-500'
            }
            disabled:opacity-50
          `}
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
              Play Clip
            </>
          )}
        </button>

        <div className="flex items-center gap-3 text-sm text-zinc-400">
          <span className="font-mono">{formatTime(currentTime)}</span>
          <span>/</span>
          <span className="font-mono">{formatTime(duration)}</span>
        </div>
      </div>

      {/* Clip boundary info */}
      <div className="flex items-center justify-between text-xs text-zinc-500">
        <span>
          Clip: {formatTime(startTime)} → {formatTime(endTime)}
        </span>
        <span>
          Duration: {formatTime(endTime - startTime)}
          {silences.length > 0 && (
            <> · {silences.length} silences</>
          )}
        </span>
      </div>
    </div>
  );
}
