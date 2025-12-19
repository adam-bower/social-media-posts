"""
Crop calculation for video export with intelligent subject positioning.

Calculates optimal crop regions based on detected subject position and
target export format. Includes confidence scoring for auto-approval.

Usage:
    from src.video.crop_calculator import CropCalculator, CropResult

    calculator = CropCalculator()
    result = calculator.calculate_crop(
        source_width=1920,
        source_height=1080,
        target_format=ExportFormat.TIKTOK,
        subject_position=position,
    )
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

from src.video.export_formats import (
    ExportFormat,
    FormatSpec,
    get_format,
    get_all_formats,
)
from src.video.vision_detector import SubjectPosition, MovementAnalysis


class CropConfidence(Enum):
    """Confidence levels for crop auto-approval."""
    HIGH = "high"           # Auto-approve: 85%+ detection, subject fully visible
    MEDIUM = "medium"       # Review recommended: 70-85%, minor concerns
    LOW = "low"             # Manual review required: <70% or issues
    FAILED = "failed"       # Cannot determine crop (no subject detected)


@dataclass
class CropRegion:
    """
    A calculated crop region with pixel coordinates.

    All coordinates are relative to the SCALED source (not original).
    """
    x: int                  # Left edge of crop
    y: int                  # Top edge of crop
    width: int              # Crop width
    height: int             # Crop height
    scale: float            # Scale factor applied to source
    scaled_width: int       # Source width after scaling
    scaled_height: int      # Source height after scaling

    @property
    def right(self) -> int:
        """Right edge of crop."""
        return self.x + self.width

    @property
    def bottom(self) -> int:
        """Bottom edge of crop."""
        return self.y + self.height

    @property
    def center(self) -> Tuple[int, int]:
        """Center point of crop region."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    def to_ffmpeg_crop(self) -> str:
        """
        Generate FFmpeg crop filter string.

        Format: crop=width:height:x:y
        """
        return f"crop={self.width}:{self.height}:{self.x}:{self.y}"

    def to_ffmpeg_scale_and_crop(self) -> str:
        """
        Generate FFmpeg filter chain for scale + crop.

        Returns: "scale=w:h,crop=w:h:x:y"
        """
        return f"scale={self.scaled_width}:{self.scaled_height},{self.to_ffmpeg_crop()}"


@dataclass
class CropIssue:
    """An issue detected with the crop."""
    severity: str          # "warning" or "error"
    code: str              # Machine-readable code
    message: str           # Human-readable description


@dataclass
class CropResult:
    """Result of crop calculation for a single format."""
    format: ExportFormat
    format_spec: FormatSpec
    crop: CropRegion
    subject_position: Optional[SubjectPosition]
    confidence: CropConfidence
    confidence_score: float  # 0-1 score
    issues: List[CropIssue]
    auto_approve: bool       # Whether to auto-approve this crop

    @property
    def needs_review(self) -> bool:
        """Whether this crop needs human review."""
        return not self.auto_approve

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "format": self.format.value,
            "crop": {
                "x": self.crop.x,
                "y": self.crop.y,
                "width": self.crop.width,
                "height": self.crop.height,
                "scale": self.crop.scale,
                "ffmpeg_filter": self.crop.to_ffmpeg_scale_and_crop(),
            },
            "subject_position": {
                "x": self.subject_position.x,
                "y": self.subject_position.y,
                "head_y": self.subject_position.head_y,
                "confidence": self.subject_position.confidence,
            } if self.subject_position else None,
            "confidence": self.confidence.value,
            "confidence_score": round(self.confidence_score, 3),
            "issues": [{"severity": i.severity, "code": i.code, "message": i.message} for i in self.issues],
            "auto_approve": self.auto_approve,
            "needs_review": self.needs_review,
        }


@dataclass
class MultiFormatCropResult:
    """Crop results for multiple formats."""
    source_width: int
    source_height: int
    results: Dict[ExportFormat, CropResult]
    movement_analysis: Optional[MovementAnalysis]

    def get_result(self, format: ExportFormat) -> Optional[CropResult]:
        """Get result for a specific format."""
        return self.results.get(format)

    @property
    def all_auto_approved(self) -> bool:
        """Check if all formats are auto-approved."""
        return all(r.auto_approve for r in self.results.values())

    @property
    def formats_needing_review(self) -> List[ExportFormat]:
        """Get list of formats that need review."""
        return [f for f, r in self.results.items() if r.needs_review]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "source": {
                "width": self.source_width,
                "height": self.source_height,
            },
            "movement": {
                "is_static": self.movement_analysis.is_static,
                "max_drift": self.movement_analysis.max_drift,
                "requires_tracking": self.movement_analysis.requires_tracking,
            } if self.movement_analysis else None,
            "results": {f.value: r.to_dict() for f, r in self.results.items()},
            "all_auto_approved": self.all_auto_approved,
            "formats_needing_review": [f.value for f in self.formats_needing_review],
        }


class CropCalculator:
    """
    Calculates optimal crop regions for video export.

    Handles subject positioning and confidence scoring.
    """

    # Thresholds for auto-approval
    HIGH_CONFIDENCE_THRESHOLD = 0.85
    MEDIUM_CONFIDENCE_THRESHOLD = 0.70

    # Subject positioning tolerances
    HEAD_TOP_MARGIN = 0.05      # Minimum margin above head (5%)
    HEAD_BOTTOM_MARGIN = 0.15   # Minimum space below head
    SIDE_MARGIN = 0.10          # Minimum margin on sides (10%)

    def __init__(self):
        pass

    def calculate_crop(
        self,
        source_width: int,
        source_height: int,
        target_format: ExportFormat,
        subject_position: Optional[SubjectPosition] = None,
    ) -> CropResult:
        """
        Calculate optimal crop for a single format.

        Args:
            source_width: Source video width
            source_height: Source video height
            target_format: Target export format
            subject_position: Detected subject position (optional)

        Returns:
            CropResult with calculated crop and confidence
        """
        format_spec = get_format(target_format)
        issues: List[CropIssue] = []

        # Calculate base crop region
        crop = self._calculate_base_crop(
            source_width,
            source_height,
            format_spec,
            subject_position,
        )

        # Validate and adjust crop
        if subject_position:
            crop, validation_issues = self._validate_subject_in_crop(
                crop,
                format_spec,
                subject_position,
            )
            issues.extend(validation_issues)

        # Calculate confidence score
        confidence_score = self._calculate_confidence(
            subject_position,
            crop,
            format_spec,
            issues,
        )

        # Determine confidence level
        if not subject_position or subject_position.confidence < 0.3:
            confidence = CropConfidence.FAILED
        elif confidence_score >= self.HIGH_CONFIDENCE_THRESHOLD:
            confidence = CropConfidence.HIGH
        elif confidence_score >= self.MEDIUM_CONFIDENCE_THRESHOLD:
            confidence = CropConfidence.MEDIUM
        else:
            confidence = CropConfidence.LOW

        # Determine auto-approval
        auto_approve = (
            confidence == CropConfidence.HIGH and
            not any(i.severity == "error" for i in issues)
        )

        return CropResult(
            format=target_format,
            format_spec=format_spec,
            crop=crop,
            subject_position=subject_position,
            confidence=confidence,
            confidence_score=confidence_score,
            issues=issues,
            auto_approve=auto_approve,
        )

    def calculate_all_crops(
        self,
        source_width: int,
        source_height: int,
        subject_position: Optional[SubjectPosition] = None,
        movement_analysis: Optional[MovementAnalysis] = None,
        formats: Optional[List[ExportFormat]] = None,
    ) -> MultiFormatCropResult:
        """
        Calculate crops for multiple formats.

        Args:
            source_width: Source video width
            source_height: Source video height
            subject_position: Detected subject position
            movement_analysis: Movement analysis from multiple frames
            formats: Specific formats to calculate (None = all)

        Returns:
            MultiFormatCropResult with all crop calculations
        """
        # Use average position if movement analysis provided
        if movement_analysis and not subject_position:
            avg_x, avg_y = movement_analysis.average_position
            avg_confidence = movement_analysis.confidence
            subject_position = SubjectPosition(
                x=avg_x,
                y=avg_y,
                head_y=avg_y - 0.1,  # Estimate head above center
                confidence=avg_confidence,
                description="Average position from movement analysis",
            )

        # Calculate for each format
        target_formats = formats or list(ExportFormat)
        results = {}

        for fmt in target_formats:
            result = self.calculate_crop(
                source_width,
                source_height,
                fmt,
                subject_position,
            )
            results[fmt] = result

        return MultiFormatCropResult(
            source_width=source_width,
            source_height=source_height,
            results=results,
            movement_analysis=movement_analysis,
        )

    def _calculate_base_crop(
        self,
        source_width: int,
        source_height: int,
        format_spec: FormatSpec,
        subject_position: Optional[SubjectPosition],
    ) -> CropRegion:
        """Calculate base crop region before validation."""
        source_aspect = source_width / source_height
        target_aspect = format_spec.width / format_spec.height

        if source_aspect > target_aspect:
            # Source is wider than target - scale by height, crop sides
            scale = format_spec.height / source_height
            scaled_width = int(source_width * scale)
            scaled_height = format_spec.height

            crop_width = format_spec.width
            crop_height = format_spec.height

            # Position crop based on subject
            if subject_position:
                subject_x_px = int(subject_position.x * scaled_width)
                crop_x = subject_x_px - (crop_width // 2)
            else:
                crop_x = (scaled_width - crop_width) // 2  # Center

            # Clamp to valid range
            crop_x = max(0, min(crop_x, scaled_width - crop_width))
            crop_y = 0

        else:
            # Source is taller or same aspect - scale by width, crop top/bottom
            scale = format_spec.width / source_width
            scaled_width = format_spec.width
            scaled_height = int(source_height * scale)

            crop_width = format_spec.width
            crop_height = format_spec.height

            # Position based on subject's head position
            if subject_position:
                # Target: head at format_spec.subject_head_position
                target_head_y = int(format_spec.subject_head_position * crop_height)
                subject_head_y_px = int(subject_position.head_y * scaled_height)

                # Calculate crop_y to align head with target position
                crop_y = subject_head_y_px - target_head_y
            else:
                # Default: center crop
                crop_y = (scaled_height - crop_height) // 2

            # Clamp to valid range
            crop_y = max(0, min(crop_y, scaled_height - crop_height))
            crop_x = 0

        return CropRegion(
            x=crop_x,
            y=crop_y,
            width=crop_width,
            height=crop_height,
            scale=scale,
            scaled_width=scaled_width,
            scaled_height=scaled_height,
        )

    def _validate_subject_in_crop(
        self,
        crop: CropRegion,
        format_spec: FormatSpec,
        subject_position: SubjectPosition,
    ) -> Tuple[CropRegion, List[CropIssue]]:
        """
        Validate that subject is properly positioned in crop.

        Returns adjusted crop and list of issues.
        """
        issues: List[CropIssue] = []

        # Convert subject position to pixel coordinates in scaled space
        subject_x_px = int(subject_position.x * crop.scaled_width)
        subject_y_px = int(subject_position.y * crop.scaled_height)
        head_y_px = int(subject_position.head_y * crop.scaled_height)

        # Check if head has enough top margin
        head_in_crop_y = head_y_px - crop.y
        min_top_margin = int(self.HEAD_TOP_MARGIN * crop.height)

        if head_in_crop_y < min_top_margin:
            issues.append(CropIssue(
                severity="warning",
                code="head_too_high",
                message=f"Head may be cut off at top (head at {head_in_crop_y}px, min margin {min_top_margin}px)",
            ))

        # Check if subject is too close to bottom
        subject_in_crop_y = subject_y_px - crop.y
        max_bottom = crop.height - format_spec.caption_margin_bottom - 50  # Leave room for captions

        if subject_in_crop_y > max_bottom:
            issues.append(CropIssue(
                severity="warning",
                code="subject_too_low",
                message="Subject may overlap with caption area",
            ))

        # Check horizontal margins
        subject_in_crop_x = subject_x_px - crop.x
        min_side_margin = int(self.SIDE_MARGIN * crop.width)

        if subject_in_crop_x < min_side_margin:
            issues.append(CropIssue(
                severity="warning",
                code="subject_near_left",
                message="Subject close to left edge",
            ))
        elif subject_in_crop_x > crop.width - min_side_margin:
            issues.append(CropIssue(
                severity="warning",
                code="subject_near_right",
                message="Subject close to right edge",
            ))

        # Check if subject is outside crop entirely
        if subject_x_px < crop.x or subject_x_px > crop.right:
            issues.append(CropIssue(
                severity="error",
                code="subject_outside_crop_x",
                message="Subject is outside crop area horizontally",
            ))

        if subject_y_px < crop.y or subject_y_px > crop.bottom:
            issues.append(CropIssue(
                severity="error",
                code="subject_outside_crop_y",
                message="Subject is outside crop area vertically",
            ))

        return crop, issues

    def _calculate_confidence(
        self,
        subject_position: Optional[SubjectPosition],
        crop: CropRegion,
        format_spec: FormatSpec,
        issues: List[CropIssue],
    ) -> float:
        """Calculate overall confidence score (0-1)."""
        if not subject_position:
            return 0.0

        # Start with subject detection confidence
        score = subject_position.confidence

        # Reduce for each issue
        for issue in issues:
            if issue.severity == "error":
                score *= 0.5  # Major reduction for errors
            elif issue.severity == "warning":
                score *= 0.9  # Minor reduction for warnings

        # Bonus for subject being well-centered
        if subject_position.is_centered:
            score = min(1.0, score * 1.05)

        # Bonus for head being well-positioned
        if subject_position.head_in_frame:
            score = min(1.0, score * 1.03)

        return max(0.0, min(1.0, score))


def calculate_crop_for_video(
    video_path: str,
    formats: Optional[List[ExportFormat]] = None,
    clip_start: Optional[float] = None,
    clip_end: Optional[float] = None,
) -> MultiFormatCropResult:
    """
    Calculate crops for a video file.

    Convenience function that handles frame sampling and detection.

    Args:
        video_path: Path to video file
        formats: Specific formats to calculate
        clip_start: Optional clip start time
        clip_end: Optional clip end time

    Returns:
        MultiFormatCropResult
    """
    from src.video.frame_sampler import sample_frames, SamplingMode, get_video_info
    from src.video.vision_detector import QwenVisionDetector

    # Get video info
    info = get_video_info(video_path)
    source_width = info["width"]
    source_height = info["height"]

    # Sample frames
    result = sample_frames(
        video_path,
        mode=SamplingMode.SPARSE,
        clip_start=clip_start,
        clip_end=clip_end,
        max_dimension=720,
    )

    # Analyze with vision detector
    with QwenVisionDetector() as detector:
        movement = detector.analyze_video_frames(result)

    # Calculate crops
    calculator = CropCalculator()
    return calculator.calculate_all_crops(
        source_width=source_width,
        source_height=source_height,
        movement_analysis=movement,
        formats=formats,
    )


if __name__ == "__main__":
    import json

    print("Crop Calculator - Test Mode")
    print("=" * 60)

    # Test with simulated subject position
    calculator = CropCalculator()

    # Simulate a centered subject
    subject = SubjectPosition(
        x=0.5,
        y=0.45,
        head_y=0.30,
        confidence=0.92,
        description="Person speaking to camera",
    )

    print("\nSource: 1920x1080 (16:9)")
    print(f"Subject: x={subject.x}, y={subject.y}, head_y={subject.head_y}")
    print(f"Detection confidence: {subject.confidence:.0%}")

    # Calculate for all formats
    result = calculator.calculate_all_crops(
        source_width=1920,
        source_height=1080,
        subject_position=subject,
    )

    print(f"\nAll auto-approved: {result.all_auto_approved}")
    print(f"Formats needing review: {[f.value for f in result.formats_needing_review]}")

    for fmt, crop_result in result.results.items():
        print(f"\n{fmt.value.upper()}")
        print(f"  Target: {crop_result.format_spec.width}x{crop_result.format_spec.height}")
        print(f"  Crop: {crop_result.crop.width}x{crop_result.crop.height} at ({crop_result.crop.x}, {crop_result.crop.y})")
        print(f"  Scale: {crop_result.crop.scale:.2f}x")
        print(f"  Confidence: {crop_result.confidence.value} ({crop_result.confidence_score:.0%})")
        print(f"  Auto-approve: {crop_result.auto_approve}")
        if crop_result.issues:
            print(f"  Issues: {[i.message for i in crop_result.issues]}")
        print(f"  FFmpeg: {crop_result.crop.to_ffmpeg_scale_and_crop()}")
