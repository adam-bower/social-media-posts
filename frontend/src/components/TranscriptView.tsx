import { useState, useEffect, useRef } from 'react';
import { getTranscript } from '../api/client';
import type { Transcript, TranscriptSegment } from '../types';

interface TranscriptViewProps {
  videoId: string;
  currentTime?: number;
  onSegmentClick?: (time: number) => void;
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function TranscriptView({ videoId, currentTime = 0, onSegmentClick }: TranscriptViewProps) {
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const activeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchTranscript = async () => {
      try {
        setLoading(true);
        const data = await getTranscript(videoId);
        setTranscript(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load transcript');
      } finally {
        setLoading(false);
      }
    };

    fetchTranscript();
  }, [videoId]);

  // Auto-scroll to active segment
  useEffect(() => {
    if (activeRef.current) {
      activeRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [currentTime]);

  if (loading) {
    return (
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-8 text-center">
        <div className="w-6 h-6 border-2 border-zinc-600 border-t-zinc-300 rounded-full animate-spin mx-auto mb-3" />
        <p className="text-zinc-500 text-sm">Loading transcript...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-6 text-center">
        <p className="text-red-400">{error}</p>
      </div>
    );
  }

  if (!transcript) {
    return (
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-8 text-center">
        <p className="text-zinc-500">No transcript available</p>
      </div>
    );
  }

  const isActiveSegment = (segment: TranscriptSegment) => {
    return currentTime >= segment.start && currentTime < segment.end;
  };

  return (
    <div className="bg-zinc-900 rounded-xl border border-zinc-800 overflow-hidden">
      <div className="p-3 sm:p-4 border-b border-zinc-800 bg-zinc-900/50">
        <h3 className="font-medium text-white text-sm sm:text-base">Transcript</h3>
        <p className="text-xs text-zinc-500">
          {transcript.language?.toUpperCase() || 'EN'} · {transcript.segments.length} segments
        </p>
      </div>

      <div className="max-h-96 overflow-y-auto p-2 sm:p-3 space-y-1">
        {transcript.segments.map((segment, index) => {
          const isActive = isActiveSegment(segment);

          return (
            <div
              key={index}
              ref={isActive ? activeRef : null}
              onClick={() => onSegmentClick?.(segment.start)}
              className={`
                p-2 sm:p-3 rounded-lg cursor-pointer transition-all touch-manipulation
                ${isActive
                  ? 'bg-white/10 border border-white/20'
                  : 'hover:bg-zinc-800 active:bg-zinc-700 border border-transparent'
                }
              `}
            >
              <div className="flex items-start gap-2 sm:gap-3">
                <span className={`
                  text-xs font-mono px-2 py-1 rounded flex-shrink-0
                  ${isActive ? 'bg-white text-zinc-900' : 'bg-zinc-800 text-zinc-400'}
                `}>
                  {formatTime(segment.start)}
                </span>
                <p className={`text-sm ${isActive ? 'text-white' : 'text-zinc-300'}`}>
                  {segment.text}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Full text toggle */}
      <div className="p-3 sm:p-4 border-t border-zinc-800 bg-zinc-900/50">
        <details className="text-sm">
          <summary className="cursor-pointer text-zinc-400 hover:text-white transition-colors">
            View full transcript
          </summary>
          <div className="mt-3 p-4 bg-zinc-800 rounded-lg border border-zinc-700 text-zinc-300 whitespace-pre-wrap text-sm">
            {transcript.full_text}
          </div>
        </details>
      </div>
    </div>
  );
}
