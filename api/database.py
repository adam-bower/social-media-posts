"""
Database client for Supabase.

Provides a simple interface for video clipper database operations.
Works both locally (via .env) and in Windmill deployment.
"""

import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


class Database:
    """Supabase database client."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        """Lazy-load Supabase client."""
        if self._client is None:
            from supabase import create_client

            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

            if not url or not key:
                # Try Windmill
                try:
                    import wmill
                    resource = wmill.get_resource("f/database/supabase")
                    url = resource["url"]
                    key = resource["service_role_key"]
                except Exception:
                    raise ValueError(
                        "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY"
                    )

            self._client = create_client(url, key)

        return self._client

    # ==================== Videos ====================

    def create_video(
        self,
        filename: str,
        original_path: str,
        user_id: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
    ) -> Dict:
        """Create a new video record."""
        data = {
            "filename": filename,
            "original_path": original_path,
            "user_id": user_id,
            "file_size_bytes": file_size_bytes,
            "status": "uploaded",
        }

        result = self.client.table("videos").insert(data).execute()
        return result.data[0] if result.data else None

    def get_video(self, video_id: str) -> Optional[Dict]:
        """Get video by ID."""
        result = self.client.table("videos").select("*").eq("id", video_id).execute()
        return result.data[0] if result.data else None

    def update_video(self, video_id: str, **kwargs) -> Optional[Dict]:
        """Update video fields."""
        kwargs["updated_at"] = datetime.utcnow().isoformat()
        result = self.client.table("videos").update(kwargs).eq("id", video_id).execute()
        return result.data[0] if result.data else None

    def update_video_status(
        self,
        video_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> Optional[Dict]:
        """Update video status."""
        data = {"status": status}
        if error_message:
            data["error_message"] = error_message
        return self.update_video(video_id, **data)

    def list_videos(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """List videos with optional filters."""
        query = self.client.table("videos").select("*")

        if user_id:
            query = query.eq("user_id", user_id)
        if status:
            query = query.eq("status", status)

        query = query.order("created_at", desc=True).limit(limit)
        result = query.execute()

        return result.data or []

    def delete_video(self, video_id: str) -> bool:
        """Delete a video and all associated data (cascades via FK)."""
        self.client.table("videos").delete().eq("id", video_id).execute()
        return True

    # ==================== Transcripts ====================

    def create_transcript(
        self,
        video_id: str,
        full_text: str,
        segments: List[Dict],
        language: str,
        language_probability: Optional[float] = None,
        model_used: str = "large-v3",
        processing_time_seconds: Optional[float] = None,
    ) -> Dict:
        """Create a transcript record."""
        data = {
            "video_id": video_id,
            "full_text": full_text,
            "segments": segments,
            "language": language,
            "language_probability": language_probability,
            "model_used": model_used,
            "processing_time_seconds": processing_time_seconds,
        }

        result = self.client.table("transcripts").insert(data).execute()
        return result.data[0] if result.data else None

    def get_transcript(self, video_id: str) -> Optional[Dict]:
        """Get transcript for a video."""
        result = (
            self.client.table("transcripts")
            .select("*")
            .eq("video_id", video_id)
            .execute()
        )
        return result.data[0] if result.data else None

    # ==================== Clip Suggestions ====================

    def create_clip_suggestion(
        self,
        video_id: str,
        start_time: float,
        end_time: float,
        platform: str,
        transcript_excerpt: Optional[str] = None,
        hook_reason: Optional[str] = None,
        confidence_score: Optional[float] = None,
        is_composed: bool = False,
        composition_segments: Optional[List[Dict]] = None,
    ) -> Dict:
        """Create a clip suggestion."""
        data = {
            "video_id": video_id,
            "start_time": start_time,
            "end_time": end_time,
            "platform": platform,
            "transcript_excerpt": transcript_excerpt,
            "hook_reason": hook_reason,
            "confidence_score": confidence_score,
            "status": "pending",
            "is_composed": is_composed,
            "composition_segments": composition_segments,
        }

        result = self.client.table("clip_suggestions").insert(data).execute()
        return result.data[0] if result.data else None

    def create_clip_suggestions_batch(
        self,
        video_id: str,
        suggestions: List[Dict],
    ) -> List[Dict]:
        """Create multiple clip suggestions at once."""
        data = []
        for s in suggestions:
            data.append({
                "video_id": video_id,
                "start_time": s["start_time"],
                "end_time": s["end_time"],
                "platform": s.get("platform", "both"),
                "transcript_excerpt": s.get("transcript_excerpt", ""),
                "hook_reason": s.get("hook_reason", ""),
                "confidence_score": s.get("confidence_score"),
                "status": "pending",
            })

        result = self.client.table("clip_suggestions").insert(data).execute()
        return result.data or []

    def get_clip_suggestions(self, video_id: str) -> List[Dict]:
        """Get all clip suggestions for a video."""
        result = (
            self.client.table("clip_suggestions")
            .select("*")
            .eq("video_id", video_id)
            .order("start_time")
            .execute()
        )
        return result.data or []

    def get_clip_suggestion(self, clip_id: str) -> Optional[Dict]:
        """Get a single clip suggestion."""
        result = (
            self.client.table("clip_suggestions")
            .select("*")
            .eq("id", clip_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def update_clip_suggestion(self, clip_id: str, **kwargs) -> Optional[Dict]:
        """Update a clip suggestion."""
        kwargs["updated_at"] = datetime.utcnow().isoformat()
        result = (
            self.client.table("clip_suggestions")
            .update(kwargs)
            .eq("id", clip_id)
            .execute()
        )
        return result.data[0] if result.data else None

    # ==================== Rendered Clips ====================

    def create_rendered_clip(
        self,
        suggestion_id: str,
        video_id: str,
        platform: str,
        output_path: Optional[str] = None,
        storage_url: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        file_size_bytes: Optional[int] = None,
        render_time_seconds: Optional[float] = None,
    ) -> Dict:
        """Create a rendered clip record."""
        data = {
            "suggestion_id": suggestion_id,
            "video_id": video_id,
            "platform": platform,
            "output_path": output_path,
            "storage_url": storage_url,
            "duration_seconds": duration_seconds,
            "file_size_bytes": file_size_bytes,
            "render_time_seconds": render_time_seconds,
        }

        result = self.client.table("rendered_clips").insert(data).execute()
        return result.data[0] if result.data else None

    def get_rendered_clips(self, video_id: str) -> List[Dict]:
        """Get all rendered clips for a video."""
        result = (
            self.client.table("rendered_clips")
            .select("*")
            .eq("video_id", video_id)
            .execute()
        )
        return result.data or []

    # ==================== Exports ====================

    def create_export(
        self,
        clip_id: str,
        video_id: str,
        platform: str,
        format_preset: str = "linkedin",
        include_captions: bool = True,
    ) -> Dict:
        """Create an export job."""
        data = {
            "clip_id": clip_id,
            "video_id": video_id,
            "platform": platform,
            "format_preset": format_preset,
            "include_captions": include_captions,
            "status": "pending",
            "progress": 0,
        }

        result = self.client.table("exports").insert(data).execute()
        return result.data[0] if result.data else None

    def get_export(self, export_id: str) -> Optional[Dict]:
        """Get export by ID."""
        result = (
            self.client.table("exports")
            .select("*")
            .eq("id", export_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def update_export(self, export_id: str, **kwargs) -> Optional[Dict]:
        """Update export fields."""
        kwargs["updated_at"] = datetime.utcnow().isoformat()
        result = (
            self.client.table("exports")
            .update(kwargs)
            .eq("id", export_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def list_exports(
        self,
        video_id: Optional[str] = None,
        clip_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """List exports with optional filters."""
        query = self.client.table("exports").select("*")

        if video_id:
            query = query.eq("video_id", video_id)
        if clip_id:
            query = query.eq("clip_id", clip_id)
        if status:
            query = query.eq("status", status)

        query = query.order("created_at", desc=True).limit(limit)
        result = query.execute()

        return result.data or []

    def get_pending_exports(self, limit: int = 10) -> List[Dict]:
        """Get pending exports for processing."""
        result = (
            self.client.table("exports")
            .select("*")
            .eq("status", "pending")
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return result.data or []


# Singleton instance
db = Database()
