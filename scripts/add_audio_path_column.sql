-- Add audio_path column to videos table
-- Run this in Supabase SQL Editor

ALTER TABLE videos ADD COLUMN IF NOT EXISTS audio_path TEXT;
