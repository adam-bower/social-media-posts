import { useState, useEffect, useRef } from 'react';
import { getClipSuggestions, getClipPreviewUrl, getTranscript, getVideoExports } from '../api/client';
import { ClipEditor } from './ClipEditor';
import type { ClipSuggestion, Transcript, Export } from '../types';

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

export function ClipSuggestions({ videoId }: ClipSuggestionsProps) {
  const [clips, setClips] = useState<ClipSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [playingClipId, setPlayingClipId] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [audioProgress, setAudioProgress] = useState(0);
  const [audioDuration, setAudioDuration] = useState(0);
  const [audioCurrentTime, setAudioCurrentTime] = useState(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const progressRef = useRef<HTMLDivElement | null>(null);

  // Export state
  const [exports, setExports] = useState<Export[]>([]);

  // ClipEditor modal state
  const [editingClip, setEditingClip] = useState<ClipSuggestion | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [clipsData, transcriptData, exportsData] = await Promise.all([
          getClipSuggestions(videoId),
          getTranscript(videoId).catch(() => null),
          getVideoExports(videoId).catch(() => ({ exports: [], total: 0 })),
        ]);
        setClips(clipsData);
        setTranscript(transcriptData);
        setExports(exportsData.exports);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load clips');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [videoId]);

  // Poll for export status updates
  useEffect(() => {
    const hasActiveExports = exports.some(e => e.status === 'pending' || e.status === 'processing');
    if (!hasActiveExports) return;

    const interval = setInterval(async () => {
      try {
        const exportsData = await getVideoExports(videoId);
        setExports(exportsData.exports);
      } catch (err) {
        console.error('Failed to poll exports:', err);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [videoId, exports]);

  // Cleanup audio on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  // Handle seeking in progress bar
  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!audioRef.current || !progressRef.current) return;
    const rect = progressRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const percentage = Math.max(0, Math.min(1, clickX / rect.width));
    const newTime = percentage * audioRef.current.duration;
    audioRef.current.currentTime = newTime;
    setAudioCurrentTime(newTime);
    setAudioProgress(percentage * 100);
  };

  const handleSeekDrag = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.buttons !== 1) return;
    handleSeek(e);
  };

  const handlePlayClip = (clip: ClipSuggestion, e: React.MouseEvent) => {
    e.stopPropagation();

    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    if (playingClipId === clip.id) {
      setPlayingClipId(null);
      setAudioProgress(0);
      setAudioCurrentTime(0);
      setAudioDuration(0);
      return;
    }

    const audioUrl = getClipPreviewUrl(videoId, clip.start_time, clip.end_time, true, 'linkedin');
    const audio = new Audio(audioUrl);
    audioRef.current = audio;

    audio.onloadedmetadata = () => {
      setAudioDuration(audio.duration);
    };

    audio.ontimeupdate = () => {
      if (audio.duration) {
        setAudioCurrentTime(audio.currentTime);
        setAudioProgress((audio.currentTime / audio.duration) * 100);
      }
    };

    audio.onended = () => {
      setPlayingClipId(null);
      setAudioProgress(0);
      setAudioCurrentTime(0);
      audioRef.current = null;
    };

    audio.onerror = () => {
      console.error('Failed to load audio');
      setPlayingClipId(null);
      setAudioProgress(0);
      audioRef.current = null;
    };

    audio.play().catch(err => {
      console.error('Failed to play audio:', err);
      setPlayingClipId(null);
    });

    setPlayingClipId(clip.id);
  };

  const handleEditClip = (clip: ClipSuggestion, e: React.MouseEvent) => {
    e.stopPropagation();
    // Stop audio if playing
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setPlayingClipId(null);
    setEditingClip(clip);
  };

  const handleCloseEditor = () => {
    setEditingClip(null);
  };

  const handleExportComplete = async () => {
    // Refresh exports after successful export
    try {
      const exportsData = await getVideoExports(videoId);
      setExports(exportsData.exports);
    } catch (err) {
      console.error('Failed to refresh exports:', err);
    }
  };

  // Get exports for a specific clip
  const getClipExports = (clipId: string): Export[] => {
    return exports.filter(e => e.clip_id === clipId);
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

  const activeExports = exports.filter(e => e.status === 'pending' || e.status === 'processing');
  const completedExports = exports.filter(e => e.status === 'completed');

  return (
    <>
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white">Suggested Clips</h2>
            <p className="text-sm text-zinc-500">
              {clips.length} clip{clips.length !== 1 ? 's' : ''}
              {completedExports.length > 0 && ` · ${completedExports.length} exported`}
              {activeExports.length > 0 && ` · ${activeExports.length} exporting`}
            </p>
          </div>
        </div>

        {/* Clips list */}
        <div className="space-y-3">
          {clips.map((clip) => {
            const duration = clip.end_time - clip.start_time;
            const isPlaying = playingClipId === clip.id;
            const clipExports = getClipExports(clip.id);
            const completedCount = clipExports.filter(e => e.status === 'completed').length;
            const processingCount = clipExports.filter(e => e.status === 'processing' || e.status === 'pending').length;

            return (
              <div
                key={clip.id}
                className="bg-zinc-900 rounded-xl border border-zinc-800 overflow-hidden transition-all hover:border-zinc-700"
              >
                <div className="p-4">
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
                        <span className="font-mono">{formatTime(clip.start_time)} - {formatTime(clip.end_time)}</span>
                        <span className="text-zinc-600">·</span>
                        <span>{formatDuration(duration)}</span>
                        {completedCount > 0 && (
                          <>
                            <span className="text-zinc-600">·</span>
                            <span className="text-emerald-400 flex items-center gap-1">
                              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                              </svg>
                              {completedCount} exported
                            </span>
                          </>
                        )}
                        {processingCount > 0 && (
                          <>
                            <span className="text-zinc-600">·</span>
                            <span className="text-blue-400 flex items-center gap-1">
                              <div className="w-3 h-3 border border-blue-400 border-t-transparent rounded-full animate-spin" />
                              {processingCount} exporting
                            </span>
                          </>
                        )}
                      </div>

                      {/* Progress bar when playing */}
                      {isPlaying && (
                        <div className="mt-2 mb-1">
                          <div
                            ref={progressRef}
                            className="h-2 bg-zinc-700 rounded-full cursor-pointer relative group"
                            onClick={(e) => { e.stopPropagation(); handleSeek(e); }}
                            onMouseMove={(e) => { e.stopPropagation(); handleSeekDrag(e); }}
                          >
                            <div
                              className="absolute top-0 left-0 h-full bg-white rounded-full transition-all duration-100"
                              style={{ width: `${audioProgress}%` }}
                            />
                            <div
                              className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow-md opacity-0 group-hover:opacity-100 transition-opacity"
                              style={{ left: `calc(${audioProgress}% - 6px)` }}
                            />
                          </div>
                          <div className="flex justify-between text-xs text-zinc-500 mt-1">
                            <span>{formatTime(audioCurrentTime)}</span>
                            <span>{formatTime(audioDuration)}</span>
                          </div>
                        </div>
                      )}

                      {/* Hook reason when not playing */}
                      {!isPlaying && clip.hook_reason && (
                        <p className="text-sm text-zinc-300 line-clamp-2">{clip.hook_reason}</p>
                      )}
                    </div>

                    {/* Edit button */}
                    <button
                      onClick={(e) => handleEditClip(clip, e)}
                      className="flex-shrink-0 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition-colors touch-manipulation flex items-center gap-2"
                      style={{ minHeight: '44px' }}
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                      Edit & Export
                    </button>
                  </div>

                  {/* Export badges */}
                  {clipExports.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-zinc-800 flex flex-wrap gap-2">
                      {clipExports.map((exp) => (
                        <div
                          key={exp.id}
                          className={`
                            inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium
                            ${exp.status === 'completed' ? 'bg-emerald-500/20 text-emerald-400' :
                              exp.status === 'processing' ? 'bg-blue-500/20 text-blue-400' :
                              exp.status === 'pending' ? 'bg-yellow-500/20 text-yellow-400' :
                              'bg-red-500/20 text-red-400'
                            }
                          `}
                        >
                          {exp.status === 'processing' && (
                            <div className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
                          )}
                          {exp.status === 'completed' && (
                            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                            </svg>
                          )}
                          <span className="capitalize">{exp.platform.replace('_', ' ')}</span>
                          {exp.status === 'processing' && (
                            <span className="text-[10px] opacity-70">{Math.round(exp.progress)}%</span>
                          )}
                          {exp.status === 'completed' && exp.time_saved && (
                            <span className="text-[10px] opacity-70">-{exp.time_saved.toFixed(1)}s</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ClipEditor Modal */}
      {editingClip && (
        <ClipEditor
          clip={editingClip}
          videoId={videoId}
          transcriptSegments={transcript?.segments || []}
          onClose={handleCloseEditor}
          onExportComplete={handleExportComplete}
        />
      )}
    </>
  );
}
