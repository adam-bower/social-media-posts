import { useState } from 'react';
import { VideoUpload } from './components/VideoUpload';
import { ProcessingStatus } from './components/ProcessingStatus';
import { TranscriptView } from './components/TranscriptView';
import { ClipSuggestions } from './components/ClipSuggestions';
import { deleteVideo, composeClips } from './api/client';
import type { ClipSuggestion } from './types';

type AppState = 'upload' | 'processing' | 'review';

function App() {
  const [state, setState] = useState<AppState>('upload');
  const [videoId, setVideoId] = useState<string | null>(null);
  const [selectedClip, setSelectedClip] = useState<ClipSuggestion | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [composing, setComposing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleUploadComplete = (id: string) => {
    setVideoId(id);
    setState('processing');
  };

  const handleResumeReview = (id: string) => {
    setVideoId(id);
    setState('review');
  };

  const handleProcessingComplete = () => {
    setState('review');
  };

  const handleProcessingError = (error: string) => {
    console.error('Processing error:', error);
  };

  const handleClipSelect = (clip: ClipSuggestion) => {
    setSelectedClip(clip);
    setCurrentTime(clip.start_time);
  };

  const handleSegmentClick = (time: number) => {
    setCurrentTime(time);
  };

  const handleStartOver = () => {
    setState('upload');
    setVideoId(null);
    setSelectedClip(null);
    setCurrentTime(0);
  };

  const handleDelete = async () => {
    if (!videoId) return;
    if (!confirm('Delete this video and all its clips?')) return;

    setDeleting(true);
    try {
      await deleteVideo(videoId);
      handleStartOver();
    } catch (err) {
      console.error('Failed to delete:', err);
      alert('Failed to delete video');
    } finally {
      setDeleting(false);
    }
  };

  const handleComposeClips = async (platform: string) => {
    if (!videoId) return;

    setComposing(true);
    try {
      const result = await composeClips(videoId, platform, 3);
      alert(`Generated ${result.clips_generated} AI-composed clips for ${platform}`);
      setRefreshKey(k => k + 1);
    } catch (err) {
      console.error('Failed to compose clips:', err);
      alert('Failed to generate AI clips');
    } finally {
      setComposing(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col">
      {/* Header */}
      <header className="bg-zinc-900/80 backdrop-blur-lg border-b border-zinc-800 sticky top-0 z-50 safe-area-top">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 py-3 sm:py-4">
          {/* Top row: title and actions */}
          <div className="flex items-center justify-between">
            <button
              onClick={handleStartOver}
              className="text-left touch-manipulation"
            >
              <h1 className="text-lg sm:text-xl font-semibold text-white hover:text-zinc-300 transition-colors">Video Clipper</h1>
              <p className="text-xs text-zinc-500 hidden sm:block">AI-powered clip extraction</p>
            </button>

            {state !== 'upload' && (
              <div className="flex items-center gap-2">
                {state === 'review' && (
                  <button
                    onClick={handleDelete}
                    disabled={deleting}
                    className="px-3 py-2 text-sm bg-red-500/10 text-red-400 rounded-lg hover:bg-red-500/20 active:bg-red-500/30 disabled:opacity-50 touch-manipulation border border-red-500/20"
                  >
                    {deleting ? '...' : 'Delete'}
                  </button>
                )}
                <button
                  onClick={handleStartOver}
                  className="px-3 py-2 text-sm bg-zinc-800 text-zinc-300 hover:bg-zinc-700 active:bg-zinc-600 font-medium rounded-lg touch-manipulation flex items-center gap-1.5"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                  </svg>
                  Home
                </button>
              </div>
            )}
          </div>

          {/* AI compose buttons */}
          {state === 'review' && (
            <div className="mt-3 flex items-center gap-2 overflow-x-auto pb-1">
              <span className="text-xs text-zinc-500 whitespace-nowrap">Generate:</span>
              <button
                onClick={() => handleComposeClips('linkedin')}
                disabled={composing}
                className="px-4 py-2 text-sm font-medium bg-blue-500/10 text-blue-400 rounded-lg hover:bg-blue-500/20 active:bg-blue-500/30 disabled:opacity-50 whitespace-nowrap touch-manipulation border border-blue-500/20"
              >
                {composing ? 'Working...' : 'LinkedIn'}
              </button>
              <button
                onClick={() => handleComposeClips('tiktok')}
                disabled={composing}
                className="px-4 py-2 text-sm font-medium bg-pink-500/10 text-pink-400 rounded-lg hover:bg-pink-500/20 active:bg-pink-500/30 disabled:opacity-50 whitespace-nowrap touch-manipulation border border-pink-500/20"
              >
                TikTok
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 max-w-7xl mx-auto px-3 sm:px-4 py-4 sm:py-6 w-full">
        {/* Upload state */}
        {state === 'upload' && (
          <VideoUpload
            onUploadComplete={handleUploadComplete}
            onResumeReview={handleResumeReview}
          />
        )}

        {/* Processing state */}
        {state === 'processing' && videoId && (
          <ProcessingStatus
            videoId={videoId}
            onComplete={handleProcessingComplete}
            onError={handleProcessingError}
          />
        )}

        {/* Review state */}
        {state === 'review' && videoId && (
          <div className="flex flex-col lg:grid lg:grid-cols-2 gap-4 sm:gap-6">
            {/* Clips first on mobile */}
            <div className="order-1 lg:order-2 space-y-4">
              {/* Selected clip info */}
              {selectedClip && (
                <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-3 sm:p-4">
                  <h4 className="font-medium text-emerald-400 mb-1 sm:mb-2 text-sm sm:text-base">Selected Clip</h4>
                  <p className="text-xs sm:text-sm text-emerald-300/80">
                    {selectedClip.platform.toUpperCase()} |{' '}
                    {Math.round(selectedClip.end_time - selectedClip.start_time)}s |{' '}
                    {Math.round((selectedClip.confidence_score || 0) * 100)}%
                  </p>
                  {selectedClip.hook_reason && (
                    <p className="text-xs sm:text-sm text-zinc-400 mt-1 line-clamp-2">{selectedClip.hook_reason}</p>
                  )}
                </div>
              )}

              <ClipSuggestions
                key={refreshKey}
                videoId={videoId}
                onClipSelect={handleClipSelect}
              />
            </div>

            {/* Transcript */}
            <div className="order-2 lg:order-1">
              <TranscriptView
                videoId={videoId}
                currentTime={currentTime}
                onSegmentClick={handleSegmentClick}
              />
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="py-3 sm:py-4 text-center text-xs text-zinc-600 safe-area-bottom">
        Video Clipper | AB Civil
      </footer>
    </div>
  );
}

export default App;
