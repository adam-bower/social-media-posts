// API Types for Video Clipper

export type VideoStatus =
  | 'uploaded'
  | 'extracting_audio'
  | 'transcribing'
  | 'analyzing'
  | 'ready'
  | 'error';

export type ClipStatus = 'pending' | 'approved' | 'rejected' | 'rendered';

export type Platform = 'linkedin' | 'tiktok' | 'both';

export interface Video {
  id: string;
  filename: string;
  user_id?: string;
  original_path: string;
  duration_seconds?: number;
  resolution?: string;
  file_size_bytes?: number;
  status: VideoStatus;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface TranscriptWord {
  word: string;
  start: number;
  end: number;
  confidence: number;
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
  confidence?: number;
  words?: TranscriptWord[];
}

export interface Transcript {
  id: string;
  video_id: string;
  full_text: string;
  segments: TranscriptSegment[];
  language: string;
  language_probability?: number;
  model_used: string;
  processing_time_seconds?: number;
  created_at: string;
}

export interface ClipSuggestion {
  id: string;
  video_id: string;
  start_time: number;
  end_time: number;
  duration?: number;
  transcript_excerpt?: string;
  platform: Platform;
  hook_reason?: string;
  confidence_score?: number;
  status: ClipStatus;
  created_at: string;
}

export interface UploadResponse {
  id: string;
  filename: string;
  file_size_bytes: number;
  status: string;
  message: string;
}

export interface ProcessingResponse {
  id: string;
  status: string;
  message: string;
}
