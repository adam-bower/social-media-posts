// API Client for Video Clipper

import type {
  Video,
  Transcript,
  ClipSuggestion,
  UploadResponse,
  ProcessingResponse,
  ClipStatus,
} from '../types';

// Use environment variable for API URL, fallback to relative path for local dev
const API_BASE = import.meta.env.VITE_API_URL || '/api';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new ApiError(response.status, error.detail || 'Request failed');
  }
  return response.json();
}

// Upload
export async function uploadVideo(file: File, userId?: string): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  if (userId) {
    formData.append('user_id', userId);
  }

  const response = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    body: formData,
  });

  return handleResponse<UploadResponse>(response);
}

// Videos
export async function getVideos(params?: {
  user_id?: string;
  status?: string;
  limit?: number;
}): Promise<Video[]> {
  const searchParams = new URLSearchParams();
  if (params?.user_id) searchParams.set('user_id', params.user_id);
  if (params?.status) searchParams.set('status', params.status);
  if (params?.limit) searchParams.set('limit', String(params.limit));

  const url = `${API_BASE}/videos${searchParams.toString() ? `?${searchParams}` : ''}`;
  const response = await fetch(url);
  return handleResponse<Video[]>(response);
}

export async function getVideo(videoId: string): Promise<Video> {
  const response = await fetch(`${API_BASE}/videos/${videoId}`);
  return handleResponse<Video>(response);
}

export async function getVideoStatus(videoId: string): Promise<{ id: string; status: string; error_message?: string }> {
  const response = await fetch(`${API_BASE}/videos/${videoId}/status`);
  return handleResponse(response);
}

export async function processVideo(videoId: string): Promise<ProcessingResponse> {
  const response = await fetch(`${API_BASE}/videos/${videoId}/process`, {
    method: 'POST',
  });
  return handleResponse<ProcessingResponse>(response);
}

// Transcripts
export async function getTranscript(videoId: string): Promise<Transcript> {
  const response = await fetch(`${API_BASE}/videos/${videoId}/transcript`);
  return handleResponse<Transcript>(response);
}

// Clips
export async function getClipSuggestions(videoId: string): Promise<ClipSuggestion[]> {
  const response = await fetch(`${API_BASE}/videos/${videoId}/suggestions`);
  return handleResponse<ClipSuggestion[]>(response);
}

export async function getClip(clipId: string): Promise<ClipSuggestion> {
  const response = await fetch(`${API_BASE}/clips/${clipId}`);
  return handleResponse<ClipSuggestion>(response);
}

export async function updateClip(
  clipId: string,
  updates: { status?: ClipStatus; start_time?: number; end_time?: number }
): Promise<{ id: string; status: string; message: string }> {
  const response = await fetch(`${API_BASE}/clips/${clipId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  });
  return handleResponse(response);
}

export async function approveClip(clipId: string): Promise<{ id: string; status: string; message: string }> {
  const response = await fetch(`${API_BASE}/clips/${clipId}/approve`, {
    method: 'POST',
  });
  return handleResponse(response);
}

export async function rejectClip(clipId: string): Promise<{ id: string; status: string; message: string }> {
  const response = await fetch(`${API_BASE}/clips/${clipId}/reject`, {
    method: 'POST',
  });
  return handleResponse(response);
}

// Delete video
export async function deleteVideo(videoId: string): Promise<{ id: string; message: string }> {
  const response = await fetch(`${API_BASE}/videos/${videoId}`, {
    method: 'DELETE',
  });
  return handleResponse(response);
}

// AI Compose clips
export async function composeClips(
  videoId: string,
  platform: string = 'linkedin',
  numClips: number = 3
): Promise<{ video_id: string; platform: string; clips_generated: number; clips: any[] }> {
  const params = new URLSearchParams({
    platform,
    num_clips: String(numClips),
  });
  const response = await fetch(`${API_BASE}/videos/${videoId}/compose-clips?${params}`, {
    method: 'POST',
  });
  return handleResponse(response);
}

// Audio
export function getAudioUrl(videoId: string): string {
  return `${API_BASE}/videos/${videoId}/audio`;
}

export function getClipPreviewUrl(
  videoId: string,
  startTime: number,
  endTime: number,
  edit: boolean = true,
  preset: string = "linkedin"
): string {
  const params = new URLSearchParams({
    start: String(startTime),
    end: String(endTime),
    edit: String(edit),
    preset: preset,
  });
  return `${API_BASE}/videos/${videoId}/clip-preview?${params}`;
}

// Export all functions
export const api = {
  uploadVideo,
  getVideos,
  getVideo,
  deleteVideo,
  getAudioUrl,
  getClipPreviewUrl,
  getVideoStatus,
  processVideo,
  getTranscript,
  getClipSuggestions,
  getClip,
  updateClip,
  approveClip,
  rejectClip,
  composeClips,
};

export default api;
