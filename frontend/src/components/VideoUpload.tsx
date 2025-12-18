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
      <div className="max-w-xl mx-auto p-6">
        <div className="bg-green-50 border border-green-200 rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <svg className="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <h3 className="text-lg font-semibold text-green-800">Upload Complete</h3>
          </div>

          <div className="space-y-2 text-sm text-green-700 mb-6">
            <p><span className="font-medium">File:</span> {uploadedVideo.filename}</p>
            <p><span className="font-medium">Size:</span> {formatFileSize(uploadedVideo.file_size_bytes)}</p>
            <p><span className="font-medium">ID:</span> {uploadedVideo.id}</p>
          </div>

          <button
            onClick={handleStartProcessing}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 px-4 rounded-lg transition-colors"
          >
            Start Processing
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-xl mx-auto p-6">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          border-2 border-dashed rounded-lg p-12 text-center transition-colors cursor-pointer
          ${isDragging
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 hover:border-gray-400'
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

        <label htmlFor="video-upload" className="cursor-pointer">
          <svg
            className="w-12 h-12 mx-auto mb-4 text-gray-400"
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
              <p className="text-gray-600 mb-2">Uploading...</p>
              <div className="w-48 mx-auto bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-200"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <p className="text-sm text-gray-500 mt-2">{uploadProgress}%</p>
            </div>
          ) : (
            <>
              <p className="text-gray-600 mb-2">
                <span className="text-blue-600 font-medium">Click to upload</span> or drag and drop
              </p>
              <p className="text-sm text-gray-500">MP4, MOV, WebM, or AVI (max 5GB)</p>
            </>
          )}
        </label>
      </div>

      {error && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {/* Existing processed videos */}
      {existingVideos.length > 0 && onResumeReview && (
        <div className="mt-8">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Previously Processed Videos</h3>
          <div className="space-y-3">
            {existingVideos.map((video) => (
              <div
                key={video.id}
                className="flex items-center justify-between p-4 bg-white border rounded-lg hover:border-blue-300 transition-colors"
              >
                <div>
                  <p className="font-medium text-gray-800">{video.filename}</p>
                  <p className="text-sm text-gray-500">
                    {video.duration_seconds ? `${Math.round(video.duration_seconds / 60)}m ${Math.round(video.duration_seconds % 60)}s` : 'Unknown duration'}
                    {video.resolution && ` • ${video.resolution}`}
                  </p>
                </div>
                <button
                  onClick={() => onResumeReview(video.id)}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
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
