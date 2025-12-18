import { useState, useEffect, useRef } from 'react';
import { getClipSuggestions, approveClip, rejectClip, getClipPreviewUrl } from '../api/client';
import type { ClipSuggestion, Platform } from '../types';

interface ClipSuggestionsProps {
  videoId: string;
  onClipSelect?: (clip: ClipSuggestion) => void;
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
}

const PLATFORM_COLORS: Record<Platform, { bg: string; text: string; border: string }> = {
  linkedin: { bg: 'bg-blue-100', text: 'text-blue-800', border: 'border-blue-200' },
  tiktok: { bg: 'bg-pink-100', text: 'text-pink-800', border: 'border-pink-200' },
  both: { bg: 'bg-purple-100', text: 'text-purple-800', border: 'border-purple-200' },
};

type EditPreset = 'youtube_shorts' | 'tiktok' | 'linkedin' | 'podcast' | 'off';

const PRESET_INFO: Record<EditPreset, { label: string; description: string }> = {
  youtube_shorts: { label: 'YT Shorts', description: 'Aggressive - fastest pacing' },
  tiktok: { label: 'TikTok', description: 'Fast - punchy cuts' },
  linkedin: { label: 'LinkedIn', description: 'Moderate - professional' },
  podcast: { label: 'Podcast', description: 'Light - natural speech' },
  off: { label: 'Off', description: 'No editing' },
};

export function ClipSuggestions({ videoId, onClipSelect }: ClipSuggestionsProps) {
  const [clips, setClips] = useState<ClipSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [playingClipId, setPlayingClipId] = useState<string | null>(null);
  const [editPreset, setEditPreset] = useState<EditPreset>('tiktok');
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Stop audio when preset changes
  const handlePresetChange = (preset: EditPreset) => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setPlayingClipId(null);
    setEditPreset(preset);
  };

  useEffect(() => {
    const fetchClips = async () => {
      try {
        setLoading(true);
        const data = await getClipSuggestions(videoId);
        setClips(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load suggestions');
      } finally {
        setLoading(false);
      }
    };

    fetchClips();
  }, [videoId]);

  const handleApprove = async (clipId: string) => {
    setActionLoading(clipId);
    try {
      await approveClip(clipId);
      setClips(clips.map(c =>
        c.id === clipId ? { ...c, status: 'approved' } : c
      ));
    } catch (err) {
      console.error('Failed to approve clip:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (clipId: string) => {
    setActionLoading(clipId);
    try {
      await rejectClip(clipId);
      setClips(clips.map(c =>
        c.id === clipId ? { ...c, status: 'rejected' } : c
      ));
    } catch (err) {
      console.error('Failed to reject clip:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handlePlayClip = (clip: ClipSuggestion) => {
    // Stop currently playing audio if any
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    if (playingClipId === clip.id) {
      // Stop playing
      setPlayingClipId(null);
      return;
    }

    // Create new audio element and play
    const audioUrl = getClipPreviewUrl(
      videoId,
      clip.start_time,
      clip.end_time,
      editPreset !== 'off',
      editPreset === 'off' ? 'linkedin' : editPreset
    );
    const audio = new Audio(audioUrl);
    audioRef.current = audio;

    audio.onended = () => {
      setPlayingClipId(null);
      audioRef.current = null;
    };

    audio.onerror = () => {
      console.error('Failed to load audio');
      setPlayingClipId(null);
      audioRef.current = null;
    };

    audio.play().catch(err => {
      console.error('Failed to play audio:', err);
      setPlayingClipId(null);
    });

    setPlayingClipId(clip.id);
  };

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  if (loading) {
    return (
      <div className="p-6 text-center text-gray-500">
        <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
        Loading suggestions...
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

  if (clips.length === 0) {
    return (
      <div className="p-6 text-center text-gray-500">
        No clip suggestions available
      </div>
    );
  }

  const pendingClips = clips.filter(c => c.status === 'pending');
  const approvedClips = clips.filter(c => c.status === 'approved');
  const rejectedClips = clips.filter(c => c.status === 'rejected');

  return (
    <div className="bg-white rounded-lg shadow-sm border">
      <div className="p-3 sm:p-4 border-b bg-gray-50">
        <div className="flex items-center justify-between mb-2 sm:mb-3">
          <div>
            <h3 className="font-semibold text-gray-800 text-sm sm:text-base">Clip Suggestions</h3>
            <p className="text-xs sm:text-sm text-gray-500">
              {pendingClips.length} pending | {approvedClips.length} approved | {rejectedClips.length} rejected
            </p>
          </div>
        </div>

        {/* Edit preset selector - horizontal scroll on mobile */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          <span className="text-xs sm:text-sm text-gray-600 whitespace-nowrap">Edit:</span>
          <div className="flex gap-1">
            {(Object.keys(PRESET_INFO) as EditPreset[]).map((preset) => (
              <button
                key={preset}
                onClick={() => handlePresetChange(preset)}
                className={`
                  px-3 py-2 text-xs sm:text-sm rounded-lg transition-colors whitespace-nowrap touch-manipulation
                  ${editPreset === preset
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300 active:bg-gray-400'
                  }
                `}
                title={PRESET_INFO[preset].description}
              >
                {PRESET_INFO[preset].label}
              </button>
            ))}
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-1">
          {PRESET_INFO[editPreset].description}
        </p>
      </div>

      <div className="divide-y">
        {clips.map((clip) => {
          const colors = PLATFORM_COLORS[clip.platform];
          const duration = clip.end_time - clip.start_time;
          const isLoading = actionLoading === clip.id;
          const isPlaying = playingClipId === clip.id;

          return (
            <div
              key={clip.id}
              className={`p-3 sm:p-4 ${clip.status === 'rejected' ? 'opacity-50' : ''}`}
            >
              {/* Mobile: stacked layout, Desktop: row layout */}
              <div className="flex flex-col sm:flex-row sm:items-start gap-3 sm:gap-4">
                {/* Top row on mobile: Play button + info */}
                <div className="flex items-start gap-3 flex-1">
                  {/* Play button - larger on mobile for better touch */}
                  <button
                    onClick={() => handlePlayClip(clip)}
                    className={`
                      flex-shrink-0 w-12 h-12 sm:w-10 sm:h-10 flex items-center justify-center rounded-full
                      transition-colors touch-manipulation active:scale-95
                      ${isPlaying
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 hover:bg-gray-200 active:bg-gray-300 text-gray-600'
                      }
                    `}
                    title={isPlaying ? 'Stop' : 'Play clip preview'}
                  >
                    {isPlaying ? (
                      <svg className="w-5 h-5 sm:w-4 sm:h-4" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                      </svg>
                    ) : (
                      <svg className="w-5 h-5 sm:w-4 sm:h-4 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M8 5v14l11-7z" />
                      </svg>
                    )}
                  </button>

                  <div
                    className="flex-1 cursor-pointer min-w-0"
                    onClick={() => onClipSelect?.(clip)}
                  >
                    {/* Platform badge and time */}
                    <div className="flex flex-wrap items-center gap-1 sm:gap-2 mb-1 sm:mb-2">
                      <span className={`
                        text-xs font-medium px-2 py-0.5 sm:py-1 rounded-full
                        ${colors.bg} ${colors.text}
                      `}>
                        {clip.platform.toUpperCase()}
                      </span>
                      <span className="text-xs sm:text-sm text-gray-600">
                        {formatTime(clip.start_time)} - {formatTime(clip.end_time)}
                      </span>
                      <span className="text-xs sm:text-sm text-gray-400">
                        ({formatDuration(duration)})
                      </span>
                    </div>

                    {/* Hook reason */}
                    {clip.hook_reason && (
                      <p className="text-xs sm:text-sm text-gray-700 mb-1 sm:mb-2 line-clamp-2">
                        <span className="font-medium">Hook:</span> {clip.hook_reason}
                      </p>
                    )}

                    {/* Transcript excerpt - hidden on mobile to save space */}
                    {clip.transcript_excerpt && (
                      <p className="hidden sm:block text-sm text-gray-500 italic line-clamp-2">
                        "{clip.transcript_excerpt}"
                      </p>
                    )}

                    {/* Confidence score */}
                    {clip.confidence_score !== undefined && (
                      <div className="mt-1 sm:mt-2 flex items-center gap-2">
                        <div className="flex-1 h-1.5 bg-gray-200 rounded-full max-w-20 sm:max-w-24">
                          <div
                            className="h-full bg-green-500 rounded-full"
                            style={{ width: `${clip.confidence_score * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-gray-500">
                          {Math.round(clip.confidence_score * 100)}%
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Actions - horizontal on mobile, vertical on desktop */}
                <div className="flex sm:flex-col gap-2 pl-15 sm:pl-0">
                  {clip.status === 'pending' && (
                    <>
                      <button
                        onClick={() => handleApprove(clip.id)}
                        disabled={isLoading}
                        className="flex-1 sm:flex-none px-4 py-2 text-sm font-medium text-green-700 bg-green-100 hover:bg-green-200 active:bg-green-300 rounded-lg transition-colors disabled:opacity-50 touch-manipulation"
                      >
                        {isLoading ? '...' : 'Approve'}
                      </button>
                      <button
                        onClick={() => handleReject(clip.id)}
                        disabled={isLoading}
                        className="flex-1 sm:flex-none px-4 py-2 text-sm font-medium text-red-700 bg-red-100 hover:bg-red-200 active:bg-red-300 rounded-lg transition-colors disabled:opacity-50 touch-manipulation"
                      >
                        {isLoading ? '...' : 'Reject'}
                      </button>
                    </>
                  )}

                  {clip.status === 'approved' && (
                    <span className="px-4 py-2 text-sm font-medium text-green-700 bg-green-100 rounded-lg text-center">
                      Approved
                    </span>
                  )}

                  {clip.status === 'rejected' && (
                    <span className="px-4 py-2 text-sm font-medium text-gray-500 bg-gray-100 rounded-lg text-center">
                      Rejected
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
