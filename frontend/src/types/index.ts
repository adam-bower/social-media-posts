// API Types for Video Clipper

export type VideoStatus =
  | 'uploaded'
  | 'extracting_audio'
  | 'transcribing'
  | 'analyzing'
  | 'ready'
  | 'error';

export type ClipStatus = 'pending' | 'approved' | 'rejected' | 'rendered';

export type Platform = 'linkedin' | 'tiktok' | 'youtube_shorts' | 'instagram_reels' | 'both';

export type ExportStatus = 'pending' | 'processing' | 'completed' | 'failed';

export type SilencePreset = 'linkedin' | 'tiktok' | 'youtube_shorts' | 'podcast';

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

export interface Export {
  id: string;
  clip_id: string;
  video_id: string;
  platform: Platform;
  preset: SilencePreset;
  status: ExportStatus;
  progress: number;
  include_captions: boolean;
  output_path?: string;
  output_url?: string;
  original_duration?: number;
  edited_duration?: number;
  time_saved?: number;
  file_size_bytes?: number;
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

// VAD Analysis Types
export interface SpeechSegment {
  start: number;
  end: number;
}

export interface SilenceSegment {
  start: number;
  end: number;
}

export interface EditDecision {
  start: number;
  end: number;
  action: 'keep' | 'remove' | 'trim';
  reason: string;
  original_duration: number;
  new_duration: number;
}

export interface PresetConfig {
  vad_threshold: number;
  min_silence_ms: number;
  max_kept_silence_ms: number;
  speech_padding_ms: number;
  crossfade_ms: number;
}

export interface VADAnalysis {
  speech_segments: SpeechSegment[];
  silence_segments: SilenceSegment[];
  duration: number;
  preset: SilencePreset;
  config: PresetConfig;
}

export interface ClipPreviewMetadata {
  original_duration: number;
  edited_duration: number;
  time_saved: number;
  percent_reduction: number;
  speech_segments: SpeechSegment[];
  silence_segments: SilenceSegment[];
  edit_decisions: EditDecision[];
  preset: SilencePreset;
  config: PresetConfig;
}

// Clip Adjustment Types
export interface SilenceOverride {
  start: number;  // Silence start time (relative to clip start)
  end: number;    // Silence end time (relative to clip start)
  keep_ms: number; // How many milliseconds to keep
}

export interface ClipBoundaryAdjustment {
  start_offset: number;  // Seconds to add/subtract from start
  end_offset: number;    // Seconds to add/subtract from end
}

export interface ClipAdjustments {
  boundaries?: ClipBoundaryAdjustment;
  silence_overrides?: SilenceOverride[];
  max_kept_silence_ms?: number;  // Override preset default
}

export interface PlatformAdjustments {
  base?: ClipAdjustments;
  overrides?: Record<Platform, ClipAdjustments>;
}

export interface ExportRequest {
  platforms: Platform[];
  preset: SilencePreset;
  include_captions: boolean;
  adjustments?: PlatformAdjustments;
}

export interface ExportCreateResponse {
  message: string;
  exports: Export[];
}

export interface ExportListResponse {
  exports: Export[];
  total: number;
}
