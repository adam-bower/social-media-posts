import { useState, useEffect } from 'react';
import { getVideoStatus } from '../api/client';
import type { VideoStatus } from '../types';

interface ProcessingStatusProps {
  videoId: string;
  onComplete: () => void;
  onError: (error: string) => void;
}

const STATUS_LABELS: Record<VideoStatus, string> = {
  uploaded: 'Uploaded',
  extracting_audio: 'Extracting Audio',
  transcribing: 'Transcribing',
  analyzing: 'Analyzing & Suggesting Clips',
  ready: 'Ready',
  error: 'Error',
};

const STATUS_ORDER: VideoStatus[] = [
  'uploaded',
  'extracting_audio',
  'transcribing',
  'analyzing',
  'ready',
];

export function ProcessingStatus({ videoId, onComplete, onError }: ProcessingStatusProps) {
  const [status, setStatus] = useState<VideoStatus>('uploaded');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval>;

    const checkStatus = async () => {
      try {
        const result = await getVideoStatus(videoId);
        setStatus(result.status as VideoStatus);

        if (result.status === 'ready') {
          clearInterval(intervalId);
          onComplete();
        } else if (result.status === 'error') {
          clearInterval(intervalId);
          setErrorMessage(result.error_message || 'Processing failed');
          onError(result.error_message || 'Processing failed');
        }
      } catch (err) {
        console.error('Failed to check status:', err);
      }
    };

    // Initial check
    checkStatus();

    // Poll every 2 seconds
    intervalId = setInterval(checkStatus, 2000);

    return () => clearInterval(intervalId);
  }, [videoId, onComplete, onError]);

  const currentIndex = STATUS_ORDER.indexOf(status);

  return (
    <div className="max-w-xl mx-auto p-3 sm:p-6">
      <div className="bg-zinc-900 rounded-xl border border-zinc-800 p-6">
        <h2 className="text-lg font-semibold mb-6 text-white">Processing Video</h2>

        <div className="space-y-4">
          {STATUS_ORDER.slice(1, -1).map((stepStatus, index) => {
            const stepIndex = index + 1;
            const isComplete = currentIndex > stepIndex;
            const isCurrent = status === stepStatus;
            const isPending = currentIndex < stepIndex;

            return (
              <div key={stepStatus} className="flex items-center gap-4">
                {/* Status indicator */}
                <div className={`
                  w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0
                  ${isComplete ? 'bg-emerald-500' : ''}
                  ${isCurrent ? 'bg-white' : ''}
                  ${isPending ? 'bg-zinc-800' : ''}
                `}>
                  {isComplete && (
                    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                  {isCurrent && (
                    <div className="w-4 h-4 border-2 border-zinc-900 border-t-transparent rounded-full animate-spin" />
                  )}
                  {isPending && (
                    <div className="w-3 h-3 bg-zinc-600 rounded-full" />
                  )}
                </div>

                {/* Label */}
                <span className={`
                  ${isComplete ? 'text-emerald-400 font-medium' : ''}
                  ${isCurrent ? 'text-white font-medium' : ''}
                  ${isPending ? 'text-zinc-500' : ''}
                `}>
                  {STATUS_LABELS[stepStatus]}
                </span>
              </div>
            );
          })}
        </div>

        {status === 'error' && errorMessage && (
          <div className="mt-6 p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
            <p className="text-red-400 font-medium">Processing failed</p>
            <p className="text-red-400/80 text-sm mt-1">{errorMessage}</p>
          </div>
        )}

        {status === 'ready' && (
          <div className="mt-6 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
            <p className="text-emerald-400 font-medium">Processing complete!</p>
            <p className="text-emerald-400/80 text-sm mt-1">Your video is ready for review.</p>
          </div>
        )}

        <div className="mt-6 text-sm text-zinc-600 text-center font-mono">
          {videoId}
        </div>
      </div>
    </div>
  );
}
