"""
Video export format definitions for different social media platforms.

This module defines output formats, aspect ratios, resolutions, and safe zones
for cropping and rendering videos for various platforms.

Usage:
    from src.video.export_formats import ExportFormat, get_format

    format = get_format(ExportFormat.TIKTOK)
    print(f"Resolution: {format.width}x{format.height}")
    print(f"Caption safe zone: {format.caption_margin_bottom}px from bottom")
"""

from dataclasses import dataclass
from enum import Enum
from typing import Tuple, Optional, Union, List


class ExportFormat(Enum):
    """Supported export formats."""
    TIKTOK = "tiktok"
    YOUTUBE_SHORTS = "youtube_shorts"
    INSTAGRAM_REELS = "instagram_reels"
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    SQUARE = "square"


@dataclass(frozen=True)
class AspectRatio:
    """Aspect ratio definition."""
    width: int
    height: int

    @property
    def value(self) -> float:
        return self.width / self.height

    @property
    def name(self) -> str:
        return f"{self.width}:{self.height}"

    def __str__(self) -> str:
        return self.name


# Common aspect ratios
ASPECT_9_16 = AspectRatio(9, 16)   # Vertical (TikTok, Reels, Shorts)
ASPECT_1_1 = AspectRatio(1, 1)     # Square
ASPECT_4_5 = AspectRatio(4, 5)     # Portrait (LinkedIn, Instagram Feed)
ASPECT_16_9 = AspectRatio(16, 9)   # Landscape (YouTube, LinkedIn)


@dataclass(frozen=True)
class FormatSpec:
    """
    Complete specification for an export format.

    Attributes:
        format: The export format enum value
        aspect_ratio: Target aspect ratio
        width: Output width in pixels
        height: Output height in pixels
        max_duration_seconds: Platform's maximum video duration
        caption_margin_bottom: Bottom margin for captions (px)
        caption_margin_sides: Side margins for captions (px)
        caption_position: Vertical position ("middle", "lower_third", "bottom")
        subject_head_position: Target vertical position for subject's head (0-1, from top)
        safe_zone_top: Top safe zone margin (px)
        safe_zone_bottom: Bottom safe zone margin (px)
        bitrate_mbps: Recommended video bitrate
        fps: Frames per second
        codec: Video codec
        audio_bitrate_kbps: Audio bitrate
    """
    format: ExportFormat
    aspect_ratio: AspectRatio
    width: int
    height: int
    max_duration_seconds: int
    caption_margin_bottom: int
    caption_margin_sides: int
    caption_position: str
    subject_head_position: float
    safe_zone_top: int
    safe_zone_bottom: int
    bitrate_mbps: float
    fps: int
    codec: str
    audio_bitrate_kbps: int

    @property
    def resolution(self) -> Tuple[int, int]:
        """Return resolution as (width, height) tuple."""
        return (self.width, self.height)

    @property
    def caption_safe_y(self) -> int:
        """Y position where captions should NOT overlap content."""
        return self.height - self.caption_margin_bottom

    def scale_for_source(self, source_width: int, source_height: int) -> Tuple[int, int]:
        """
        Calculate the scaled size to fit source within this format.

        For cropping, we scale source to fully cover the target area,
        then crop the excess.

        Args:
            source_width: Source video width
            source_height: Source video height

        Returns:
            (scaled_width, scaled_height) that covers target
        """
        source_aspect = source_width / source_height
        target_aspect = self.width / self.height

        if source_aspect > target_aspect:
            # Source is wider - scale by height
            scaled_height = self.height
            scaled_width = int(source_width * (self.height / source_height))
        else:
            # Source is taller - scale by width
            scaled_width = self.width
            scaled_height = int(source_height * (self.width / source_width))

        return (scaled_width, scaled_height)


# Platform format specifications
FORMAT_SPECS = {
    ExportFormat.TIKTOK: FormatSpec(
        format=ExportFormat.TIKTOK,
        aspect_ratio=ASPECT_9_16,
        width=1080,
        height=1920,
        max_duration_seconds=180,  # 3 minutes (can be 10 min for some accounts)
        caption_margin_bottom=367,  # ~19% from bottom (UI safe zone)
        caption_margin_sides=80,
        caption_position="middle",
        subject_head_position=0.35,  # Head at 35% from top
        safe_zone_top=100,
        safe_zone_bottom=400,
        bitrate_mbps=8.0,
        fps=30,
        codec="h264",
        audio_bitrate_kbps=128,
    ),
    ExportFormat.YOUTUBE_SHORTS: FormatSpec(
        format=ExportFormat.YOUTUBE_SHORTS,
        aspect_ratio=ASPECT_9_16,
        width=1080,
        height=1920,
        max_duration_seconds=60,  # 60 seconds max
        caption_margin_bottom=367,  # Same as TikTok
        caption_margin_sides=80,
        caption_position="middle",
        subject_head_position=0.35,
        safe_zone_top=100,
        safe_zone_bottom=400,
        bitrate_mbps=8.0,
        fps=30,
        codec="h264",
        audio_bitrate_kbps=128,
    ),
    ExportFormat.INSTAGRAM_REELS: FormatSpec(
        format=ExportFormat.INSTAGRAM_REELS,
        aspect_ratio=ASPECT_9_16,
        width=1080,
        height=1920,
        max_duration_seconds=90,  # 90 seconds max
        caption_margin_bottom=350,  # Similar to TikTok
        caption_margin_sides=80,
        caption_position="middle",
        subject_head_position=0.35,
        safe_zone_top=100,
        safe_zone_bottom=380,
        bitrate_mbps=8.0,
        fps=30,
        codec="h264",
        audio_bitrate_kbps=128,
    ),
    ExportFormat.LINKEDIN: FormatSpec(
        format=ExportFormat.LINKEDIN,
        aspect_ratio=ASPECT_4_5,
        width=1080,
        height=1350,
        max_duration_seconds=600,  # 10 minutes
        caption_margin_bottom=100,  # Lower margin, less UI overlay
        caption_margin_sides=60,
        caption_position="lower_third",
        subject_head_position=0.30,  # Head at 30% from top
        safe_zone_top=60,
        safe_zone_bottom=120,
        bitrate_mbps=6.0,
        fps=30,
        codec="h264",
        audio_bitrate_kbps=128,
    ),
    ExportFormat.TWITTER: FormatSpec(
        format=ExportFormat.TWITTER,
        aspect_ratio=ASPECT_16_9,
        width=1920,
        height=1080,
        max_duration_seconds=140,  # 2:20 for most users
        caption_margin_bottom=80,
        caption_margin_sides=100,
        caption_position="bottom",
        subject_head_position=0.40,  # More centered for landscape
        safe_zone_top=60,
        safe_zone_bottom=100,
        bitrate_mbps=6.0,
        fps=30,
        codec="h264",
        audio_bitrate_kbps=128,
    ),
    ExportFormat.SQUARE: FormatSpec(
        format=ExportFormat.SQUARE,
        aspect_ratio=ASPECT_1_1,
        width=1080,
        height=1080,
        max_duration_seconds=600,  # Generic
        caption_margin_bottom=100,
        caption_margin_sides=60,
        caption_position="lower_third",
        subject_head_position=0.40,  # Center-ish for square
        safe_zone_top=60,
        safe_zone_bottom=120,
        bitrate_mbps=6.0,
        fps=30,
        codec="h264",
        audio_bitrate_kbps=128,
    ),
}


def get_format(format_name: Union[ExportFormat, str]) -> FormatSpec:
    """
    Get format specification by name or enum.

    Args:
        format_name: ExportFormat enum or string name

    Returns:
        FormatSpec for the requested format

    Raises:
        ValueError: If format not found
    """
    if isinstance(format_name, str):
        try:
            format_name = ExportFormat(format_name.lower())
        except ValueError:
            available = [f.value for f in ExportFormat]
            raise ValueError(f"Unknown format '{format_name}'. Available: {available}")

    if format_name not in FORMAT_SPECS:
        raise ValueError(f"No specification for format: {format_name}")

    return FORMAT_SPECS[format_name]


def get_all_formats() -> List[FormatSpec]:
    """Return all available format specifications."""
    return list(FORMAT_SPECS.values())


def get_vertical_formats() -> List[FormatSpec]:
    """Return formats with 9:16 aspect ratio (TikTok, Shorts, Reels)."""
    return [spec for spec in FORMAT_SPECS.values() if spec.aspect_ratio == ASPECT_9_16]


def calculate_crop_region(
    source_width: int,
    source_height: int,
    target_format: FormatSpec,
    subject_x: float = 0.5,
    subject_y: float = 0.4,
) -> dict:
    """
    Calculate crop region to fit source into target format, centered on subject.

    Args:
        source_width: Source video width in pixels
        source_height: Source video height in pixels
        target_format: Target FormatSpec
        subject_x: Subject's horizontal position (0-1, left to right)
        subject_y: Subject's vertical position (0-1, top to bottom)

    Returns:
        Dict with:
            - x: Crop start x position
            - y: Crop start y position
            - width: Crop width
            - height: Crop height
            - scale: Scale factor applied
    """
    source_aspect = source_width / source_height
    target_aspect = target_format.width / target_format.height

    if source_aspect > target_aspect:
        # Source is wider than target - crop sides
        # Scale source to match target height
        scale = target_format.height / source_height
        scaled_width = int(source_width * scale)
        scaled_height = target_format.height

        # Calculate crop width (same as target)
        crop_width = target_format.width
        crop_height = target_format.height

        # Center crop on subject
        subject_x_px = int(subject_x * scaled_width)
        crop_x = subject_x_px - (crop_width // 2)

        # Clamp to valid range
        crop_x = max(0, min(crop_x, scaled_width - crop_width))
        crop_y = 0
    else:
        # Source is taller than target - crop top/bottom
        # Scale source to match target width
        scale = target_format.width / source_width
        scaled_width = target_format.width
        scaled_height = int(source_height * scale)

        crop_width = target_format.width
        crop_height = target_format.height

        # Position based on target head position
        # subject_y is where subject's head is in source (0-1)
        # target head position is where we want it in output
        target_head_y = int(target_format.subject_head_position * crop_height)
        subject_y_px = int(subject_y * scaled_height)

        # Calculate crop_y to put subject's head at target position
        crop_y = subject_y_px - target_head_y

        # Clamp to valid range
        crop_y = max(0, min(crop_y, scaled_height - crop_height))
        crop_x = 0

    return {
        "x": crop_x,
        "y": crop_y,
        "width": crop_width,
        "height": crop_height,
        "scale": scale,
        "scaled_source": (int(source_width * scale), int(source_height * scale)),
    }


if __name__ == "__main__":
    print("Export Format Definitions")
    print("=" * 60)

    for fmt in get_all_formats():
        print(f"\n{fmt.format.value.upper()}")
        print(f"  Resolution: {fmt.width}x{fmt.height}")
        print(f"  Aspect Ratio: {fmt.aspect_ratio}")
        print(f"  Max Duration: {fmt.max_duration_seconds}s")
        print(f"  Caption Margin: {fmt.caption_margin_bottom}px bottom")
        print(f"  Subject Head: {fmt.subject_head_position:.0%} from top")

    print("\n" + "=" * 60)
    print("Crop calculation example (1920x1080 source -> TikTok):")
    tiktok = get_format(ExportFormat.TIKTOK)
    crop = calculate_crop_region(1920, 1080, tiktok, subject_x=0.5, subject_y=0.35)
    print(f"  Scale: {crop['scale']:.2f}x")
    print(f"  Scaled source: {crop['scaled_source']}")
    print(f"  Crop region: x={crop['x']}, y={crop['y']}, {crop['width']}x{crop['height']}")
