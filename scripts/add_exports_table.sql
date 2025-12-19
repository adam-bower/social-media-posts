-- Exports table for tracking video export jobs
-- Run this in Supabase SQL Editor (db.ab-civil.com)

-- Export status enum-like values:
-- pending: job created, waiting to process
-- processing: currently being rendered
-- completed: finished successfully
-- failed: export failed with error

CREATE TABLE IF NOT EXISTS exports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clip_id UUID REFERENCES clip_suggestions(id) ON DELETE CASCADE,
    video_id UUID REFERENCES videos(id) ON DELETE CASCADE,

    -- Platform and format settings
    platform TEXT NOT NULL, -- tiktok, youtube_shorts, instagram_reels, linkedin
    format_preset TEXT DEFAULT 'linkedin', -- Silence removal preset: linkedin, tiktok, podcast

    -- Export settings (from clip_exporter)
    include_captions BOOLEAN DEFAULT true,

    -- Status tracking
    status TEXT DEFAULT 'pending', -- pending, processing, completed, failed
    progress FLOAT DEFAULT 0, -- 0-100 progress percentage
    error_message TEXT,

    -- Output info (populated when complete)
    output_path TEXT,
    output_url TEXT, -- Public URL if uploaded to storage
    original_duration FLOAT,
    edited_duration FLOAT,
    time_saved FLOAT,
    file_size_bytes BIGINT,

    -- Processing info
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    render_time_seconds FLOAT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_exports_clip_id ON exports(clip_id);
CREATE INDEX IF NOT EXISTS idx_exports_video_id ON exports(video_id);
CREATE INDEX IF NOT EXISTS idx_exports_status ON exports(status);
CREATE INDEX IF NOT EXISTS idx_exports_created_at ON exports(created_at DESC);

-- Updated_at trigger
DROP TRIGGER IF EXISTS update_exports_updated_at ON exports;
CREATE TRIGGER update_exports_updated_at
    BEFORE UPDATE ON exports
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comment
COMMENT ON TABLE exports IS 'Video export jobs - each row is a clip being exported to a specific platform';
