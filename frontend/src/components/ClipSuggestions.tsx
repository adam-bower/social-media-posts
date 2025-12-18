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
  linkedin: { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/30' },
  tiktok: { bg: 'bg-pink-500/20', text: 'text-pink-400', border: 'border-pink-500/30' },
  both: { bg: 'bg-purple-500/20', text: 'text-purple-400', border: 'border-purple-500/30' },
};

type EditPreset = 'youtube_shorts' | 'tiktok' | 'linkedin' | 'podcast' | 'off';

const PRESET_INFO: Record<EditPreset, { label: string; description: string }> = {
  youtube_shorts: { label: 'YT Shorts', description: 'Aggressive - fastest pacing' },
  tiktok: { label: 'TikTok', description: 'Fast - punchy cuts' },
  linkedin: { label: 'LinkedIn', description: 'Moderate - professional' },
  podcast: { label: 'Podcast', description: 'Light - natural speech' },
  off: { label: 'Raw', description: 'No editing' },
};

export function ClipSuggestions({ videoId, onClipSelect }: ClipSuggestionsProps) {
  const [clips, setClips] = useState<ClipSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [playingClipId, setPlayingClipId] = useState<string | null>(null);
  const [editPreset, setEditPreset] = useState<EditPreset>('linkedin');
  const audioRef = useRef<HTMLAudioElement | null>(null);

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
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    if (playingClipId === clip.id) {
      setPlayingClipId(null);
      return;
    }

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
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-8 text-center">
        <div className="w-6 h-6 border-2 border-zinc-600 border-t-zinc-300 rounded-full animate-spin mx-auto mb-3" />
        <p className="text-zinc-500 text-sm">Loading clips...</p>
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

  if (clips.length === 0) {
    return (
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-8 text-center">
        <p className="text-zinc-500">No clips yet. Use "Generate" above.</p>
      </div>
    );
  }

  const pendingClips = clips.filter(c => c.status === 'pending');
  const approvedClips = clips.filter(c => c.status === 'approved');
  const rejectedClips = clips.filter(c => c.status === 'rejected');

  return (
    <div className="bg-zinc-900 rounded-xl border border-zinc-800 overflow-hidden">
      {/* Header */}
      <div className="p-3 sm:p-4 border-b border-zinc-800 bg-zinc-900/50">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="font-medium text-white text-sm sm:text-base">Clips</h3>
            <p className="text-xs text-zinc-500">
              {pendingClips.length} pending · {approvedClips.length} approved · {rejectedClips.length} rejected
            </p>
          </div>
        </div>

        {/* Edit preset selector */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          <span className="text-xs text-zinc-500 whitespace-nowrap">Style:</span>
          <div className="flex gap-1">
            {(Object.keys(PRESET_INFO) as EditPreset[]).map((preset) => (
              <button
                key={preset}
                onClick={() => handlePresetChange(preset)}
                className={`
                  px-3 py-1.5 text-xs rounded-lg transition-all whitespace-nowrap touch-manipulation
                  ${editPreset === preset
                    ? 'bg-white text-zinc-900 font-medium'
                    : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 active:bg-zinc-600'
                  }
                `}
              >
                {PRESET_INFO[preset].label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Clips list */}
      <div className="divide-y divide-zinc-800">
        {clips.map((clip) => {
          const colors = PLATFORM_COLORS[clip.platform];
          const duration = clip.end_time - clip.start_time;
          const isLoading = actionLoading === clip.id;
          const isPlaying = playingClipId === clip.id;

          return (
            <div
              key={clip.id}
              className={`p-3 sm:p-4 transition-opacity ${clip.status === 'rejected' ? 'opacity-40' : ''}`}
            >
              <div className="flex flex-col sm:flex-row sm:items-start gap-3 sm:gap-4">
                {/* Play button + info */}
                <div className="flex items-start gap-3 flex-1">
                  {/* Play button */}
                  <button
                    onClick={() => handlePlayClip(clip)}
                    className={`
                      flex-shrink-0 w-12 h-12 flex items-center justify-center rounded-full
                      transition-all touch-manipulation active:scale-95
                      ${isPlaying
                        ? 'bg-white text-zinc-900'
                        : 'bg-zinc-800 hover:bg-zinc-700 active:bg-zinc-600 text-zinc-300'
                      }
                    `}
                  >
                    {isPlaying ? (
                      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                      </svg>
                    ) : (
                      <svg className="w-5 h-5 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M8 5v14l11-7z" />
                      </svg>
                    )}
                  </button>

                  <div
                    className="flex-1 cursor-pointer min-w-0"
                    onClick={() => onClipSelect?.(clip)}
                  >
                    {/* Platform badge and time */}
                    <div className="flex flex-wrap items-center gap-1.5 mb-1.5">
                      <span className={`
                        text-xs font-medium px-2 py-0.5 rounded-full border
                        ${colors.bg} ${colors.text} ${colors.border}
                      `}>
                        {clip.platform.toUpperCase()}
                      </span>
                      <span className="text-xs text-zinc-500">
                        {formatTime(clip.start_time)} - {formatTime(clip.end_time)}
                      </span>
                      <span className="text-xs text-zinc-600">
                        ({formatDuration(duration)})
                      </span>
                    </div>

                    {/* Hook reason */}
                    {clip.hook_reason && (
                      <p className="text-sm text-zinc-300 mb-1 line-clamp-2">
                        {clip.hook_reason}
                      </p>
                    )}

                    {/* Confidence score */}
                    {clip.confidence_score !== undefined && (
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1 bg-zinc-800 rounded-full max-w-20">
                          <div
                            className="h-full bg-emerald-500 rounded-full"
                            style={{ width: `${clip.confidence_score * 100}%` }}
                          />
                        </div>
                        <span className="text-xs text-zinc-500">
                          {Math.round(clip.confidence_score * 100)}%
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex sm:flex-col gap-2 ml-15 sm:ml-0">
                  {clip.status === 'pending' && (
                    <>
                      <button
                        onClick={() => handleApprove(clip.id)}
                        disabled={isLoading}
                        className="flex-1 sm:flex-none px-4 py-2.5 text-sm font-medium bg-emerald-500/10 text-emerald-400 rounded-lg hover:bg-emerald-500/20 active:bg-emerald-500/30 disabled:opacity-50 touch-manipulation border border-emerald-500/20"
                      >
                        {isLoading ? '...' : 'Approve'}
                      </button>
                      <button
                        onClick={() => handleReject(clip.id)}
                        disabled={isLoading}
                        className="flex-1 sm:flex-none px-4 py-2.5 text-sm font-medium bg-zinc-800 text-zinc-400 rounded-lg hover:bg-zinc-700 active:bg-zinc-600 disabled:opacity-50 touch-manipulation"
                      >
                        {isLoading ? '...' : 'Reject'}
                      </button>
                    </>
                  )}

                  {clip.status === 'approved' && (
                    <span className="px-4 py-2 text-sm font-medium text-emerald-400 bg-emerald-500/10 rounded-lg border border-emerald-500/20 text-center">
                      Approved
                    </span>
                  )}

                  {clip.status === 'rejected' && (
                    <span className="px-4 py-2 text-sm font-medium text-zinc-500 bg-zinc-800 rounded-lg text-center">
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
