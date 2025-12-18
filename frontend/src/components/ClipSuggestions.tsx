import { useState, useEffect, useRef } from 'react';
import { getClipSuggestions, approveClip, rejectClip, getClipPreviewUrl, getTranscript } from '../api/client';
import type { ClipSuggestion, Transcript, TranscriptSegment } from '../types';

interface ClipSuggestionsProps {
  videoId: string;
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
  return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
}

type EditPreset = 'youtube_shorts' | 'tiktok' | 'linkedin' | 'podcast' | 'off';

const PRESET_INFO: Record<EditPreset, { label: string; reduction: number }> = {
  youtube_shorts: { label: 'YT Shorts', reduction: 0.35 },
  tiktok: { label: 'TikTok', reduction: 0.30 },
  linkedin: { label: 'LinkedIn', reduction: 0.20 },
  podcast: { label: 'Podcast', reduction: 0.10 },
  off: { label: 'Raw', reduction: 0 },
};

export function ClipSuggestions({ videoId }: ClipSuggestionsProps) {
  const [clips, setClips] = useState<ClipSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [playingClipId, setPlayingClipId] = useState<string | null>(null);
  const [expandedClipId, setExpandedClipId] = useState<string | null>(null);
  const [clipPresets, setClipPresets] = useState<Record<string, EditPreset>>({});
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [clipsData, transcriptData] = await Promise.all([
          getClipSuggestions(videoId),
          getTranscript(videoId).catch(() => null)
        ]);
        setClips(clipsData);
        setTranscript(transcriptData);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load clips');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [videoId]);

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  const handleApprove = async (clipId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setActionLoading(clipId);
    try {
      await approveClip(clipId);
      setClips(clips.map(c => c.id === clipId ? { ...c, status: 'approved' } : c));
    } catch (err) {
      console.error('Failed to approve clip:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (clipId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setActionLoading(clipId);
    try {
      await rejectClip(clipId);
      setClips(clips.map(c => c.id === clipId ? { ...c, status: 'rejected' } : c));
    } catch (err) {
      console.error('Failed to reject clip:', err);
    } finally {
      setActionLoading(null);
    }
  };

  // Get preset for a specific clip (default to 'off' for raw audio)
  const getClipPreset = (clipId: string): EditPreset => {
    return clipPresets[clipId] || 'off';
  };

  const setClipPreset = (clipId: string, preset: EditPreset) => {
    // Stop any playing audio when changing preset
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setPlayingClipId(null);
    setClipPresets(prev => ({ ...prev, [clipId]: preset }));
  };

  const handlePlayClip = (clip: ClipSuggestion, e: React.MouseEvent) => {
    e.stopPropagation();

    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    if (playingClipId === clip.id) {
      setPlayingClipId(null);
      return;
    }

    const preset = getClipPreset(clip.id);
    const audioUrl = getClipPreviewUrl(
      videoId,
      clip.start_time,
      clip.end_time,
      preset !== 'off',
      preset === 'off' ? 'linkedin' : preset
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

  const handleClipClick = (clip: ClipSuggestion) => {
    if (expandedClipId === clip.id) {
      setExpandedClipId(null);
    } else {
      setExpandedClipId(clip.id);
    }
  };

  // Get transcript segments for a clip
  const getClipSegments = (clip: ClipSuggestion): TranscriptSegment[] => {
    if (!transcript?.segments) return [];
    return transcript.segments.filter(
      seg => seg.end > clip.start_time && seg.start < clip.end_time
    );
  };

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
        <p className="text-zinc-500">No clips found for this video.</p>
      </div>
    );
  }

  const pendingClips = clips.filter(c => c.status === 'pending');
  const approvedClips = clips.filter(c => c.status === 'approved');

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h2 className="text-lg font-semibold text-white">Suggested Clips</h2>
        <p className="text-sm text-zinc-500">
          {pendingClips.length} pending · {approvedClips.length} approved
        </p>
      </div>

      {/* Clips list */}
      <div className="space-y-3">
        {clips.map((clip) => {
          const duration = clip.end_time - clip.start_time;
          const isLoading = actionLoading === clip.id;
          const isPlaying = playingClipId === clip.id;
          const isExpanded = expandedClipId === clip.id;
          const clipSegments = isExpanded ? getClipSegments(clip) : [];

          return (
            <div
              key={clip.id}
              className={`
                bg-zinc-900 rounded-xl border overflow-hidden transition-all
                ${clip.status === 'rejected' ? 'opacity-40 border-zinc-800' : 'border-zinc-800'}
                ${isExpanded ? 'ring-1 ring-white/20' : ''}
              `}
            >
              {/* Clip header - clickable to expand */}
              <div
                className="p-4 cursor-pointer hover:bg-zinc-800/50 active:bg-zinc-800 transition-colors"
                onClick={() => handleClipClick(clip)}
              >
                <div className="flex items-center gap-4">
                  {/* Play button */}
                  <button
                    onClick={(e) => handlePlayClip(clip, e)}
                    className={`
                      flex-shrink-0 w-12 h-12 flex items-center justify-center rounded-full
                      transition-all touch-manipulation active:scale-95
                      ${isPlaying
                        ? 'bg-white text-zinc-900'
                        : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-300'
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

                  {/* Clip info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 text-sm text-zinc-400 mb-1">
                      <span>{formatTime(clip.start_time)} - {formatTime(clip.end_time)}</span>
                      <span className="text-zinc-600">·</span>
                      <span>{formatDuration(duration)}</span>
                    </div>
                    {clip.hook_reason && (
                      <p className="text-sm text-zinc-300 line-clamp-2">{clip.hook_reason}</p>
                    )}
                  </div>

                  {/* Expand indicator */}
                  <svg
                    className={`w-5 h-5 text-zinc-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </div>

              {/* Expanded content */}
              {isExpanded && (
                <div className="border-t border-zinc-800 bg-zinc-800/30">
                  {/* Transcript with timestamps */}
                  <div className="p-4">
                    <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-3">Transcript</h4>
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {clipSegments.length > 0 ? (
                        clipSegments.map((seg, i) => (
                          <div key={i} className="flex gap-3">
                            <span className="text-xs font-mono text-zinc-500 w-10 flex-shrink-0 pt-0.5">
                              {formatTime(seg.start)}
                            </span>
                            <p className="text-sm text-zinc-300 leading-relaxed">{seg.text}</p>
                          </div>
                        ))
                      ) : (
                        <p className="text-sm text-zinc-500 italic">
                          {clip.transcript_excerpt || 'No transcript available'}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Edit style selector */}
                  <div className="px-4 pb-4">
                    <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-3">Edit Style</h4>
                    <div className="grid grid-cols-5 gap-2">
                      {(Object.keys(PRESET_INFO) as EditPreset[]).map((preset) => {
                        const info = PRESET_INFO[preset];
                        const estimatedDuration = duration * (1 - info.reduction);
                        const isActive = getClipPreset(clip.id) === preset;
                        return (
                          <button
                            key={preset}
                            onClick={(e) => {
                              e.stopPropagation();
                              setClipPreset(clip.id, preset);
                            }}
                            className={`
                              text-center p-2 rounded-lg transition-all touch-manipulation
                              ${isActive
                                ? 'bg-white text-zinc-900 ring-2 ring-white'
                                : 'bg-zinc-800/50 hover:bg-zinc-700/50'
                              }
                            `}
                          >
                            <div className={`text-[10px] font-medium mb-1 ${isActive ? 'text-zinc-600' : 'text-zinc-500'}`}>
                              {info.label}
                            </div>
                            <div className={`text-sm font-bold ${isActive ? 'text-zinc-900' : 'text-zinc-300'}`}>
                              {formatDuration(estimatedDuration)}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Actions */}
                  {clip.status === 'pending' && (
                    <div className="px-4 pb-4 flex gap-2">
                      <button
                        onClick={(e) => handleApprove(clip.id, e)}
                        disabled={isLoading}
                        className="flex-1 py-2.5 text-sm font-medium bg-emerald-500/20 text-emerald-400 rounded-lg hover:bg-emerald-500/30 disabled:opacity-50 touch-manipulation"
                      >
                        {isLoading ? '...' : 'Approve'}
                      </button>
                      <button
                        onClick={(e) => handleReject(clip.id, e)}
                        disabled={isLoading}
                        className="flex-1 py-2.5 text-sm font-medium bg-zinc-800 text-zinc-400 rounded-lg hover:bg-zinc-700 disabled:opacity-50 touch-manipulation"
                      >
                        {isLoading ? '...' : 'Reject'}
                      </button>
                    </div>
                  )}

                  {clip.status === 'approved' && (
                    <div className="px-4 pb-4">
                      <div className="py-2.5 text-sm font-medium text-emerald-400 bg-emerald-500/10 rounded-lg text-center">
                        ✓ Approved
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
