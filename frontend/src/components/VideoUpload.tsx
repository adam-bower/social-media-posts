import { useState, useCallback, useEffect } from 'react';
import { uploadVideo, processVideo, getVideos } from '../api/client';
import type { UploadResponse, Video } from '../types';

interface VideoUploadProps {
  onUploadComplete: (videoId: string) => void;
  onResumeReview?: (videoId: string) => void;
}

export function VideoUpload({ onUploadComplete, onResumeReview }: VideoUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [uploadedVideo, setUploadedVideo] = useState<UploadResponse | null>(null);
  const [existingVideos, setExistingVideos] = useState<Video[]>([]);

  useEffect(() => {
    // Fetch existing processed videos
    getVideos({ status: 'ready', limit: 10 })
      .then(setExistingVideos)
      .catch(console.error);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFile(files[0]);
    }
  }, []);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFile(files[0]);
    }
  }, []);

  const handleFile = async (file: File) => {
    // Validate file type
    const validTypes = ['video/mp4', 'video/quicktime', 'video/webm', 'video/x-msvideo'];
    if (!validTypes.includes(file.type)) {
      setError('Invalid file type. Please upload MP4, MOV, WebM, or AVI.');
      return;
    }

    setError(null);
    setIsUploading(true);
    setUploadProgress(0);

    try {
      // Simulate progress (actual progress would need XMLHttpRequest)
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => Math.min(prev + 10, 90));
      }, 200);

      const response = await uploadVideo(file);

      clearInterval(progressInterval);
      setUploadProgress(100);
      setUploadedVideo(response);
      setIsUploading(false);
    } catch (err) {
      setIsUploading(false);
      setError(err instanceof Error ? err.message : 'Upload failed');
    }
  };

  const handleStartProcessing = async () => {
    if (!uploadedVideo) return;

    try {
      await processVideo(uploadedVideo.id);
      onUploadComplete(uploadedVideo.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start processing');
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
    return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`;
  };

  if (uploadedVideo) {
    return (
      <div className="max-w-xl mx-auto p-3 sm:p-6">
        <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-6">
          <div className="flex items-center gap-3 mb-4">
            <svg className="w-8 h-8 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <h3 className="text-lg font-semibold text-emerald-400">Upload Complete</h3>
          </div>

          <div className="space-y-2 text-sm text-emerald-300/80 mb-6">
            <p><span className="font-medium text-emerald-300">File:</span> {uploadedVideo.filename}</p>
            <p><span className="font-medium text-emerald-300">Size:</span> {formatFileSize(uploadedVideo.file_size_bytes)}</p>
            <p><span className="font-medium text-emerald-300">ID:</span> <span className="font-mono text-xs">{uploadedVideo.id}</span></p>
          </div>

          <button
            onClick={handleStartProcessing}
            className="w-full bg-white hover:bg-zinc-100 active:bg-zinc-200 text-zinc-900 font-medium py-3 px-4 rounded-lg transition-colors touch-manipulation"
          >
            Start Processing
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto p-3 sm:p-6">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          border-2 border-dashed rounded-xl p-8 sm:p-12 text-center transition-all cursor-pointer
          ${isDragging
            ? 'border-white bg-white/5'
            : 'border-zinc-700 hover:border-zinc-600 active:border-white active:bg-white/5'
          }
          ${isUploading ? 'pointer-events-none opacity-50' : ''}
        `}
      >
        <input
          type="file"
          accept="video/mp4,video/quicktime,video/webm,video/x-msvideo,.mp4,.mov,.webm,.avi"
          onChange={handleFileInput}
          className="hidden"
          id="video-upload"
          disabled={isUploading}
        />

        <label htmlFor="video-upload" className="cursor-pointer block touch-manipulation">
          <svg
            className="w-16 h-16 sm:w-12 sm:h-12 mx-auto mb-4 text-zinc-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>

          {isUploading ? (
            <div>
              <p className="text-zinc-400 mb-3">Uploading...</p>
              <div className="w-48 mx-auto bg-zinc-800 rounded-full h-2">
                <div
                  className="bg-white h-2 rounded-full transition-all duration-200"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <p className="text-sm text-zinc-500 mt-2">{uploadProgress}%</p>
            </div>
          ) : (
            <>
              <p className="text-base sm:text-lg text-zinc-400 mb-2">
                <span className="text-white font-medium">Tap to upload</span>
              </p>
              <p className="text-sm text-zinc-500">MP4, MOV, WebM, or AVI</p>
            </>
          )}
        </label>
      </div>

      {error && (
        <div className="mt-4 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400">
          {error}
        </div>
      )}

      {/* Existing processed videos */}
      {existingVideos.length > 0 && onResumeReview && (
        <div className="mt-6 sm:mt-8">
          <h3 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4">Previously Processed</h3>
          <div className="space-y-2 sm:space-y-3">
            {existingVideos.map((video) => (
              <div
                key={video.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between p-3 sm:p-4 bg-zinc-900 border border-zinc-800 rounded-xl hover:border-zinc-700 active:bg-zinc-800 transition-colors gap-2 sm:gap-4"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-medium text-white text-sm sm:text-base truncate">{video.filename}</p>
                  <p className="text-xs sm:text-sm text-zinc-500">
                    {video.duration_seconds ? `${Math.round(video.duration_seconds / 60)}m ${Math.round(video.duration_seconds % 60)}s` : 'Unknown'}
                    {video.resolution && ` · ${video.resolution}`}
                  </p>
                </div>
                <button
                  onClick={() => onResumeReview(video.id)}
                  className="w-full sm:w-auto px-4 py-3 sm:py-2 bg-white hover:bg-zinc-100 active:bg-zinc-200 text-zinc-900 text-sm font-medium rounded-lg transition-colors touch-manipulation"
                >
                  Review Clips
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
