import { useRef, useEffect, useMemo } from 'react';
import type { TranscriptWord, TranscriptSegment } from '../types';

interface ClipTranscriptProps {
  segments: TranscriptSegment[];
  clipStart: number;
  clipEnd: number;
  currentTime: number;
  onSeek?: (time: number) => void;
  isPlaying?: boolean;
}

export function ClipTranscript({
  segments,
  clipStart,
  clipEnd,
  currentTime,
  onSeek,
  isPlaying = false,
}: ClipTranscriptProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const activeWordRef = useRef<HTMLSpanElement>(null);

  // Extract all words within clip bounds
  const clipWords = useMemo(() => {
    const words: (TranscriptWord & { segmentIndex: number })[] = [];

    segments.forEach((segment, segmentIndex) => {
      // Skip segments entirely outside clip bounds
      if (segment.end <= clipStart || segment.start >= clipEnd) return;

      if (segment.words && segment.words.length > 0) {
        // Use word-level timestamps
        segment.words.forEach((word) => {
          // Include words that overlap with clip bounds
          if (word.end > clipStart && word.start < clipEnd) {
            words.push({ ...word, segmentIndex });
          }
        });
      } else {
        // No word-level timestamps - create a single "word" from segment text
        // Only include if segment overlaps with clip
        if (segment.end > clipStart && segment.start < clipEnd) {
          words.push({
            word: segment.text,
            start: Math.max(segment.start, clipStart),
            end: Math.min(segment.end, clipEnd),
            confidence: segment.confidence ?? 1,
            segmentIndex,
          });
        }
      }
    });

    return words;
  }, [segments, clipStart, clipEnd]);

  // Find current word index based on playback time
  const currentWordIndex = useMemo(() => {
    if (!isPlaying && currentTime <= clipStart) return -1;

    for (let i = 0; i < clipWords.length; i++) {
      const word = clipWords[i];
      if (currentTime >= word.start && currentTime < word.end) {
        return i;
      }
      // If we're past this word but before the next, highlight this one
      if (i < clipWords.length - 1) {
        const nextWord = clipWords[i + 1];
        if (currentTime >= word.end && currentTime < nextWord.start) {
          return i;
        }
      }
    }

    // If we're past all words, highlight the last one
    if (clipWords.length > 0 && currentTime >= clipWords[clipWords.length - 1].end) {
      return clipWords.length - 1;
    }

    return -1;
  }, [clipWords, currentTime, isPlaying, clipStart]);

  // Auto-scroll to keep current word visible
  useEffect(() => {
    if (activeWordRef.current && containerRef.current && isPlaying) {
      const container = containerRef.current;
      const word = activeWordRef.current;

      const containerRect = container.getBoundingClientRect();
      const wordRect = word.getBoundingClientRect();

      // Check if word is outside visible area
      const isAbove = wordRect.top < containerRect.top;
      const isBelow = wordRect.bottom > containerRect.bottom;

      if (isAbove || isBelow) {
        word.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
        });
      }
    }
  }, [currentWordIndex, isPlaying]);

  const handleWordClick = (word: TranscriptWord) => {
    if (onSeek) {
      onSeek(word.start);
    }
  };

  if (clipWords.length === 0) {
    return (
      <div className="p-4 text-center text-zinc-500 text-sm">
        No transcript available for this clip
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="p-4 max-h-48 overflow-y-auto bg-zinc-900/50 rounded-lg border border-zinc-800"
    >
      <p className="text-sm leading-relaxed">
        {clipWords.map((word, index) => {
          const isActive = index === currentWordIndex;
          const isPast = index < currentWordIndex;

          return (
            <span
              key={`${word.start}-${index}`}
              ref={isActive ? activeWordRef : null}
              onClick={() => handleWordClick(word)}
              className={`
                cursor-pointer transition-colors duration-150 rounded px-0.5
                ${isActive
                  ? 'bg-emerald-500/30 text-white font-medium'
                  : isPast
                    ? 'text-zinc-400'
                    : 'text-zinc-300 hover:text-white hover:bg-zinc-700/50'
                }
              `}
              title={`${word.start.toFixed(1)}s`}
            >
              {word.word}
              {index < clipWords.length - 1 && ' '}
            </span>
          );
        })}
      </p>
    </div>
  );
}
