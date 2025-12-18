import { useState } from 'react';
import { VideoUpload } from './components/VideoUpload';
import { ProcessingStatus } from './components/ProcessingStatus';
import { ClipSuggestions } from './components/ClipSuggestions';
import { deleteVideo } from './api/client';

type AppState = 'upload' | 'processing' | 'review';

function App() {
  const [state, setState] = useState<AppState>('upload');
  const [videoId, setVideoId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

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

  const handleStartOver = () => {
    setState('upload');
    setVideoId(null);
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
          <ClipSuggestions videoId={videoId} />
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
