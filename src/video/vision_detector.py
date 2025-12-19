"""
Vision-based subject detection using Gemini Flash 2.5 via OpenRouter.

Detects the position of a speaking subject in video frames for
intelligent cropping.

Usage:
    from src.video.vision_detector import GeminiVisionDetector, SubjectPosition

    detector = GeminiVisionDetector()
    position = detector.detect_subject(frame)
    print(f"Subject at ({position.x:.2f}, {position.y:.2f})")
"""

import os
import json
import httpx
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
from dotenv import load_dotenv

from src.video.frame_sampler import SampledFrame, SamplingResult

load_dotenv()


@dataclass
class SubjectPosition:
    """
    Detected position of a subject in a frame.

    Coordinates are normalized (0-1) with origin at top-left.
    """
    x: float              # Horizontal center of subject (0=left, 1=right)
    y: float              # Vertical center of subject (0=top, 1=bottom)
    head_y: float         # Vertical position of head (for crop alignment)
    confidence: float     # Detection confidence (0-1)
    description: str      # Description of what was detected
    timestamp: float = 0  # Video timestamp (if from video frame)

    @property
    def is_centered(self) -> bool:
        """Check if subject is roughly centered horizontally."""
        return 0.35 <= self.x <= 0.65

    @property
    def head_in_frame(self) -> bool:
        """Check if head is likely fully visible (not cut off at top)."""
        return self.head_y >= 0.1

    def distance_from(self, other: 'SubjectPosition') -> float:
        """Calculate distance from another position (for drift detection)."""
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5


@dataclass
class MovementAnalysis:
    """Analysis of subject movement across multiple frames."""
    positions: List[SubjectPosition]
    is_static: bool           # True if subject barely moves
    max_drift: float          # Maximum position change between frames
    average_position: Tuple[float, float]  # (x, y) average
    requires_tracking: bool   # True if dynamic cropping needed
    confidence: float         # Average detection confidence

    @property
    def suggested_crop_center(self) -> Tuple[float, float]:
        """Suggested crop center based on average position."""
        return self.average_position


class GeminiVisionDetector:
    """
    Subject detector using Gemini Flash 2.5 via OpenRouter.

    Uses google/gemini-2.5-flash for fast, accurate vision analysis.
    """

    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
    MODEL = "google/gemini-2.5-flash"

    DETECT_PROMPT = """Analyze this video frame and identify the main speaking subject (person).

Return ONLY a JSON object with these fields:
- "subject_detected": true/false - whether a person is visible
- "center_x": 0-1 float - horizontal center of the person (0=left edge, 1=right edge)
- "center_y": 0-1 float - vertical center of the person (0=top edge, 1=bottom edge)
- "head_y": 0-1 float - vertical position of the head/face (0=top, 1=bottom)
- "confidence": 0-1 float - how confident you are in this detection
- "description": string - brief description of what you see

Example:
{"subject_detected": true, "center_x": 0.5, "center_y": 0.45, "head_y": 0.25, "confidence": 0.95, "description": "Person speaking to camera, facing forward"}

Output ONLY the JSON, no other text."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize the vision detector.

        Args:
            api_key: OpenRouter API key (defaults to env var)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set")
        self.timeout = timeout
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        """Lazy-load HTTP client."""
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def _make_request(
        self,
        image_base64: str,
        prompt: str,
    ) -> Dict[str, Any]:
        """
        Make a request to OpenRouter API with Gemini Flash 2.5.

        Args:
            image_base64: Base64-encoded image
            prompt: Text prompt

        Returns:
            API response as dict
        """
        payload = {
            "model": self.MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ],
            "max_tokens": 500,
            "temperature": 0.1,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/adam-bower/social-media-posts",
            "X-Title": "Social Media Post Creator",
        }

        response = self.client.post(
            self.OPENROUTER_URL,
            json=payload,
            headers=headers,
        )
        response.raise_for_status()

        return response.json()

    def _parse_detection_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the API response to extract detection data."""
        try:
            content = response["choices"][0]["message"]["content"]

            # Handle markdown code blocks
            if "```" in content:
                import re
                match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
                if match:
                    content = match.group(1)

            # Try to extract JSON if there's extra text
            content = content.strip()
            if not content.startswith("{"):
                # Find the JSON object
                start = content.find("{")
                end = content.rfind("}") + 1
                if start != -1 and end > start:
                    content = content[start:end]

            return json.loads(content)
        except (KeyError, json.JSONDecodeError, IndexError) as e:
            return {
                "subject_detected": False,
                "center_x": 0.5,
                "center_y": 0.5,
                "head_y": 0.3,
                "confidence": 0.0,
                "description": f"Failed to parse response: {e}",
            }

    def detect_subject(
        self,
        frame: SampledFrame,
    ) -> SubjectPosition:
        """
        Detect the subject position in a single frame.

        Args:
            frame: SampledFrame with JPEG data

        Returns:
            SubjectPosition with detected coordinates
        """
        response = self._make_request(frame.base64, self.DETECT_PROMPT)
        data = self._parse_detection_response(response)

        if not data.get("subject_detected", False):
            return SubjectPosition(
                x=0.5,
                y=0.5,
                head_y=0.3,
                confidence=0.0,
                description="No subject detected",
                timestamp=frame.timestamp,
            )

        return SubjectPosition(
            x=data.get("center_x", 0.5),
            y=data.get("center_y", 0.5),
            head_y=data.get("head_y", 0.3),
            confidence=data.get("confidence", 0.5),
            description=data.get("description", "Subject detected"),
            timestamp=frame.timestamp,
        )

    def detect_subject_from_bytes(
        self,
        jpeg_bytes: bytes,
        timestamp: float = 0.0,
    ) -> SubjectPosition:
        """
        Detect subject from raw JPEG bytes.

        Args:
            jpeg_bytes: JPEG image data
            timestamp: Optional timestamp

        Returns:
            SubjectPosition
        """
        import base64
        image_base64 = base64.b64encode(jpeg_bytes).decode('utf-8')

        frame = SampledFrame(
            timestamp=timestamp,
            index=0,
            width=0,
            height=0,
            jpeg_bytes=jpeg_bytes,
        )

        return self.detect_subject(frame)

    def analyze_movement(
        self,
        frames: List[SampledFrame],
        static_threshold: float = 0.1,
    ) -> MovementAnalysis:
        """
        Analyze subject movement across multiple frames.

        Args:
            frames: List of SampledFrame objects
            static_threshold: Max drift to consider "static"

        Returns:
            MovementAnalysis with positions and drift info
        """
        if not frames:
            return MovementAnalysis(
                positions=[],
                is_static=True,
                max_drift=0.0,
                average_position=(0.5, 0.5),
                requires_tracking=False,
                confidence=0.0,
            )

        positions = []
        for frame in frames:
            pos = self.detect_subject(frame)
            positions.append(pos)

        if not positions:
            return MovementAnalysis(
                positions=[],
                is_static=True,
                max_drift=0.0,
                average_position=(0.5, 0.5),
                requires_tracking=False,
                confidence=0.0,
            )

        # Calculate average position
        avg_x = sum(p.x for p in positions) / len(positions)
        avg_y = sum(p.y for p in positions) / len(positions)

        # Calculate maximum drift
        max_drift = 0.0
        for i in range(1, len(positions)):
            drift = positions[i].distance_from(positions[i-1])
            max_drift = max(max_drift, drift)

        # Calculate average confidence
        avg_confidence = sum(p.confidence for p in positions) / len(positions)

        is_static = max_drift <= static_threshold
        requires_tracking = not is_static and max_drift > static_threshold * 2

        return MovementAnalysis(
            positions=positions,
            is_static=is_static,
            max_drift=max_drift,
            average_position=(avg_x, avg_y),
            requires_tracking=requires_tracking,
            confidence=avg_confidence,
        )

    def analyze_video_frames(
        self,
        sampling_result: SamplingResult,
        static_threshold: float = 0.1,
    ) -> MovementAnalysis:
        """
        Analyze movement from a SamplingResult.

        Args:
            sampling_result: Result from frame_sampler
            static_threshold: Max drift to consider static

        Returns:
            MovementAnalysis
        """
        return self.analyze_movement(
            sampling_result.frames,
            static_threshold=static_threshold,
        )

    def close(self):
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# Alias for backwards compatibility
QwenVisionDetector = GeminiVisionDetector


def detect_subject_in_video(
    video_path: str,
    clip_start: Optional[float] = None,
    clip_end: Optional[float] = None,
) -> MovementAnalysis:
    """
    Convenience function to detect subject position in a video.

    Uses sparse sampling (5 frames) by default.

    Args:
        video_path: Path to video file
        clip_start: Optional clip start time
        clip_end: Optional clip end time

    Returns:
        MovementAnalysis with subject positions
    """
    from src.video.frame_sampler import sample_frames, SamplingMode

    result = sample_frames(
        video_path,
        mode=SamplingMode.SPARSE,
        clip_start=clip_start,
        clip_end=clip_end,
        max_dimension=720,
    )

    with GeminiVisionDetector() as detector:
        return detector.analyze_video_frames(result)


if __name__ == "__main__":
    import sys
    import glob

    print("Vision Detector - Gemini Flash 2.5 via OpenRouter")
    print("=" * 60)

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set in .env")
        sys.exit(1)

    print(f"API Key: {'*' * 10}...{api_key[-4:]}")
    print(f"Model: {GeminiVisionDetector.MODEL}")

    # Look for test video
    video_files = glob.glob("data/video/*.mp4") + glob.glob("data/video/*.MP4")

    if not video_files:
        print("\nNo video files found in data/video/")
        sys.exit(1)

    video_path = video_files[0]
    print(f"\nTesting with: {video_path}")

    try:
        print("\nSampling frames...")
        from src.video.frame_sampler import sample_frames, SamplingMode

        result = sample_frames(
            video_path,
            mode=SamplingMode.SPARSE,
            max_dimension=720,
        )
        print(f"  Extracted {len(result.frames)} frames")

        print("\nAnalyzing with Gemini Flash 2.5...")
        with GeminiVisionDetector() as detector:
            for i, frame in enumerate(result.frames):
                print(f"\n  Frame {i+1} ({frame.timestamp:.1f}s):")
                pos = detector.detect_subject(frame)
                print(f"    Position: ({pos.x:.2f}, {pos.y:.2f})")
                print(f"    Head Y: {pos.head_y:.2f}")
                print(f"    Confidence: {pos.confidence:.0%}")
                print(f"    Description: {pos.description}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
