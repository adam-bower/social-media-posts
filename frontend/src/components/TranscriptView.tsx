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
      <div className="p-6 text-center text-gray-500">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
        Loading transcript...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-center text-red-600">
        {error}
      </div>
    );
  }

  if (!transcript) {
    return (
      <div className="p-6 text-center text-gray-500">
        No transcript available
      </div>
    );
  }

  const isActiveSegment = (segment: TranscriptSegment) => {
    return currentTime >= segment.start && currentTime < segment.end;
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border">
      <div className="p-4 border-b bg-gray-50">
        <h3 className="font-semibold text-gray-800">Transcript</h3>
        <p className="text-sm text-gray-500">
          Language: {transcript.language} | {transcript.segments.length} segments
        </p>
      </div>

      <div className="max-h-96 overflow-y-auto p-4 space-y-2">
        {transcript.segments.map((segment, index) => {
          const isActive = isActiveSegment(segment);

          return (
            <div
              key={index}
              ref={isActive ? activeRef : null}
              onClick={() => onSegmentClick?.(segment.start)}
              className={`
                p-3 rounded-lg cursor-pointer transition-colors
                ${isActive
                  ? 'bg-blue-100 border border-blue-300'
                  : 'hover:bg-gray-50 border border-transparent'
                }
              `}
            >
              <div className="flex items-start gap-3">
                <span className={`
                  text-xs font-mono px-2 py-1 rounded flex-shrink-0
                  ${isActive ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-600'}
                `}>
                  {formatTime(segment.start)}
                </span>
                <p className={`text-sm ${isActive ? 'text-blue-900' : 'text-gray-700'}`}>
                  {segment.text}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Full text toggle */}
      <div className="p-4 border-t bg-gray-50">
        <details className="text-sm">
          <summary className="cursor-pointer text-blue-600 hover:text-blue-700">
            View full transcript
          </summary>
          <div className="mt-3 p-4 bg-white rounded border text-gray-700 whitespace-pre-wrap">
            {transcript.full_text}
          </div>
        </details>
      </div>
    </div>
  );
}
