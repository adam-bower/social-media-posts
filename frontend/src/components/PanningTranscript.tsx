import { useRef, useEffect, useMemo } from 'react';
import type { TranscriptWord, TranscriptSegment } from '../types';

interface PanningTranscriptProps {
  segments: TranscriptSegment[];
  clipStart: number;
  clipEnd: number;
  currentTime: number;
  onSeek?: (time: number) => void;
  isPlaying?: boolean;
}

export function PanningTranscript({
  segments,
  clipStart,
  clipEnd,
  currentTime,
  onSeek,
  isPlaying = false,
}: PanningTranscriptProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
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

  // Smoothly scroll to center the active word
  useEffect(() => {
    if (!activeWordRef.current || !scrollContainerRef.current) return;

    const container = scrollContainerRef.current;
    const word = activeWordRef.current;

    // Calculate scroll position to center the word
    const containerWidth = container.clientWidth;
    const wordLeft = word.offsetLeft;
    const wordWidth = word.offsetWidth;
    const targetScroll = wordLeft - (containerWidth / 2) + (wordWidth / 2);

    // Smooth scroll to center
    container.scrollTo({
      left: Math.max(0, targetScroll),
      behavior: isPlaying ? 'smooth' : 'auto',
    });
  }, [currentWordIndex, isPlaying]);

  const handleWordClick = (word: TranscriptWord) => {
    if (onSeek) {
      onSeek(word.start);
    }
  };

  if (clipWords.length === 0) {
    return (
      <div className="h-10 flex items-center justify-center text-zinc-500 text-sm">
        No transcript available
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative h-12 overflow-hidden">
      {/* Fade edges */}
      <div className="absolute left-0 top-0 bottom-0 w-16 bg-gradient-to-r from-zinc-900 to-transparent z-10 pointer-events-none" />
      <div className="absolute right-0 top-0 bottom-0 w-16 bg-gradient-to-l from-zinc-900 to-transparent z-10 pointer-events-none" />

      {/* Center indicator line */}
      <div className="absolute left-1/2 top-0 bottom-0 w-0.5 bg-emerald-500/30 z-5 pointer-events-none" />

      {/* Scrolling word container */}
      <div
        ref={scrollContainerRef}
        className="h-full overflow-x-auto scrollbar-hide flex items-center px-[50%]"
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        <div className="flex items-center gap-2 whitespace-nowrap">
          {clipWords.map((word, index) => {
            const isActive = index === currentWordIndex;
            const isPast = index < currentWordIndex;

            return (
              <span
                key={`${word.start}-${index}`}
                ref={isActive ? activeWordRef : null}
                onClick={() => handleWordClick(word)}
                className={`
                  cursor-pointer transition-all duration-200 rounded px-1.5 py-0.5
                  text-base font-medium
                  ${isActive
                    ? 'bg-emerald-500/40 text-white scale-110 shadow-lg shadow-emerald-500/20'
                    : isPast
                      ? 'text-zinc-500'
                      : 'text-zinc-400 hover:text-white hover:bg-zinc-700/50'
                  }
                `}
              >
                {word.word}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
