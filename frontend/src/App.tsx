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
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Video Clipper</h1>
            <p className="text-sm text-gray-500">Upload, transcribe, and create clips</p>
          </div>

          {state !== 'upload' && (
            <div className="flex items-center gap-3">
              {state === 'review' && (
                <>
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-gray-500">AI Compose:</span>
                    <button
                      onClick={() => handleComposeClips('linkedin')}
                      disabled={composing}
                      className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 disabled:opacity-50"
                    >
                      LinkedIn
                    </button>
                    <button
                      onClick={() => handleComposeClips('tiktok')}
                      disabled={composing}
                      className="px-2 py-1 text-xs bg-pink-100 text-pink-700 rounded hover:bg-pink-200 disabled:opacity-50"
                    >
                      TikTok
                    </button>
                  </div>
                  <button
                    onClick={handleDelete}
                    disabled={deleting}
                    className="px-3 py-1 text-sm bg-red-100 text-red-700 rounded hover:bg-red-200 disabled:opacity-50"
                  >
                    {deleting ? 'Deleting...' : 'Delete'}
                  </button>
                </>
              )}
              <button
                onClick={handleStartOver}
                className="text-sm text-blue-600 hover:text-blue-700"
              >
                Start Over
              </button>
            </div>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
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
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left column: Transcript */}
            <div>
              <TranscriptView
                videoId={videoId}
                currentTime={currentTime}
                onSegmentClick={handleSegmentClick}
              />
            </div>

            {/* Right column: Clip suggestions */}
            <div className="space-y-6">
              {/* Selected clip info */}
              {selectedClip && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h4 className="font-medium text-blue-800 mb-2">Selected Clip</h4>
                  <p className="text-sm text-blue-700">
                    {selectedClip.platform.toUpperCase()} |
                    {Math.round(selectedClip.end_time - selectedClip.start_time)}s |
                    {Math.round((selectedClip.confidence_score || 0) * 100)}% confidence
                  </p>
                  {selectedClip.hook_reason && (
                    <p className="text-sm text-blue-600 mt-1">{selectedClip.hook_reason}</p>
                  )}
                </div>
              )}

              <ClipSuggestions
                key={refreshKey}
                videoId={videoId}
                onClipSelect={handleClipSelect}
              />
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="mt-auto py-4 text-center text-sm text-gray-500">
        Video Clipper v0.1.0 | AB Civil
      </footer>
    </div>
  );
}

export default App;
