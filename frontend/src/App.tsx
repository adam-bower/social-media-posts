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
      setRefreshKey(k => k + 1); // Refresh clip list
    } catch (err) {
      console.error('Failed to compose clips:', err);
      alert('Failed to generate AI clips');
    } finally {
      setComposing(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col">
      {/* Header */}
      <header className="bg-white shadow-sm sticky top-0 z-50 safe-area-top">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 py-3 sm:py-4">
          {/* Top row: title and start over */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg sm:text-xl font-bold text-gray-900">Video Clipper</h1>
              <p className="text-xs sm:text-sm text-gray-500 hidden sm:block">Upload, transcribe, and create clips</p>
            </div>

            {state !== 'upload' && (
              <div className="flex items-center gap-2">
                {state === 'review' && (
                  <button
                    onClick={handleDelete}
                    disabled={deleting}
                    className="px-3 py-2 text-sm bg-red-100 text-red-700 rounded-lg hover:bg-red-200 disabled:opacity-50 touch-manipulation"
                  >
                    {deleting ? '...' : 'Delete'}
                  </button>
                )}
                <button
                  onClick={handleStartOver}
                  className="px-3 py-2 text-sm text-blue-600 hover:text-blue-700 font-medium touch-manipulation"
                >
                  New
                </button>
              </div>
            )}
          </div>

          {/* Bottom row: AI compose buttons (mobile-friendly) */}
          {state === 'review' && (
            <div className="mt-3 flex items-center gap-2 overflow-x-auto pb-1">
              <span className="text-xs text-gray-500 whitespace-nowrap">AI Compose:</span>
              <button
                onClick={() => handleComposeClips('linkedin')}
                disabled={composing}
                className="px-4 py-2 text-sm font-medium bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 disabled:opacity-50 whitespace-nowrap touch-manipulation"
              >
                {composing ? 'Generating...' : 'LinkedIn'}
              </button>
              <button
                onClick={() => handleComposeClips('tiktok')}
                disabled={composing}
                className="px-4 py-2 text-sm font-medium bg-pink-100 text-pink-700 rounded-lg hover:bg-pink-200 disabled:opacity-50 whitespace-nowrap touch-manipulation"
              >
                TikTok
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 max-w-7xl mx-auto px-3 sm:px-4 py-4 sm:py-8 w-full">
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

        {/* Review state - mobile: clips first, then transcript */}
        {state === 'review' && videoId && (
          <div className="flex flex-col lg:grid lg:grid-cols-2 gap-4 sm:gap-6">
            {/* Mobile: Clips first (more important) */}
            <div className="order-1 lg:order-2 space-y-4">
              {/* Selected clip info */}
              {selectedClip && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 sm:p-4">
                  <h4 className="font-medium text-blue-800 mb-1 sm:mb-2 text-sm sm:text-base">Selected Clip</h4>
                  <p className="text-xs sm:text-sm text-blue-700">
                    {selectedClip.platform.toUpperCase()} |{' '}
                    {Math.round(selectedClip.end_time - selectedClip.start_time)}s |{' '}
                    {Math.round((selectedClip.confidence_score || 0) * 100)}%
                  </p>
                  {selectedClip.hook_reason && (
                    <p className="text-xs sm:text-sm text-blue-600 mt-1 line-clamp-2">{selectedClip.hook_reason}</p>
                  )}
                </div>
              )}

              <ClipSuggestions
                key={refreshKey}
                videoId={videoId}
                onClipSelect={handleClipSelect}
              />
            </div>

            {/* Desktop: Transcript on left, Mobile: below clips */}
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
      <footer className="py-3 sm:py-4 text-center text-xs sm:text-sm text-gray-500 safe-area-bottom">
        Video Clipper | AB Civil
      </footer>
    </div>
  );
}

export default App;
