-- Video Clipper Database Schema
-- Run this in Supabase SQL Editor (db.ab-civil.com)

-- Videos table: stores uploaded video metadata
CREATE TABLE IF NOT EXISTS videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    filename TEXT NOT NULL,
    original_path TEXT NOT NULL,
    duration_seconds FLOAT,
    resolution TEXT,
    file_size_bytes BIGINT,
    status TEXT DEFAULT 'uploaded', -- uploaded, extracting_audio, transcribing, analyzing, ready, error
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Transcripts table: stores transcription results with word-level timestamps
CREATE TABLE IF NOT EXISTS transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    full_text TEXT,
    segments JSONB, -- Array of {start, end, text, confidence, words: [{word, start, end, confidence}]}
    language TEXT,
    language_probability FLOAT,
    model_used TEXT DEFAULT 'large-v3',
    processing_time_seconds FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Clip suggestions table: AI-suggested clips
CREATE TABLE IF NOT EXISTS clip_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    start_time FLOAT NOT NULL,
    end_time FLOAT NOT NULL,
    transcript_excerpt TEXT,
    platform TEXT, -- linkedin, tiktok, both
    hook_reason TEXT, -- Why this clip was suggested
    confidence_score FLOAT,
    status TEXT DEFAULT 'pending', -- pending, approved, rejected, rendered
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Rendered clips table: final rendered video clips
CREATE TABLE IF NOT EXISTS rendered_clips (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    suggestion_id UUID REFERENCES clip_suggestions(id) ON DELETE CASCADE,
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    output_path TEXT,
    storage_url TEXT, -- Supabase Storage or direct URL
    duration_seconds FLOAT,
    file_size_bytes BIGINT,
    render_time_seconds FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
CREATE INDEX IF NOT EXISTS idx_videos_created_at ON videos(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transcripts_video_id ON transcripts(video_id);
CREATE INDEX IF NOT EXISTS idx_clip_suggestions_video_id ON clip_suggestions(video_id);
CREATE INDEX IF NOT EXISTS idx_clip_suggestions_status ON clip_suggestions(status);
CREATE INDEX IF NOT EXISTS idx_rendered_clips_video_id ON rendered_clips(video_id);

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to videos table
DROP TRIGGER IF EXISTS update_videos_updated_at ON videos;
CREATE TRIGGER update_videos_updated_at
    BEFORE UPDATE ON videos
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply trigger to clip_suggestions table
DROP TRIGGER IF EXISTS update_clip_suggestions_updated_at ON clip_suggestions;
CREATE TRIGGER update_clip_suggestions_updated_at
    BEFORE UPDATE ON clip_suggestions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (adjust as needed for your Supabase setup)
-- GRANT ALL ON videos TO authenticated;
-- GRANT ALL ON transcripts TO authenticated;
-- GRANT ALL ON clip_suggestions TO authenticated;
-- GRANT ALL ON rendered_clips TO authenticated;
