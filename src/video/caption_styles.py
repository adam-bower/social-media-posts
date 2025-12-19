"""
Caption styling for different social media platforms.

Defines fonts, colors, positions, and animation styles for burned-in
captions on each platform.

Usage:
    from src.video.caption_styles import get_caption_style, CaptionStyle

    style = get_caption_style(ExportFormat.TIKTOK)
    print(f"Font: {style.font_name} {style.font_size}px")
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from enum import Enum

from src.video.export_formats import ExportFormat, FormatSpec, get_format


class CaptionPosition(Enum):
    """Vertical position for captions."""
    TOP = "top"                  # Near top of screen
    CENTER = "center"            # Middle of screen
    LOWER_THIRD = "lower_third"  # Traditional lower third
    BOTTOM = "bottom"            # Near bottom


class HighlightStyle(Enum):
    """Style for word highlighting (karaoke effect)."""
    NONE = "none"              # No highlighting
    COLOR_CHANGE = "color"     # Change color of current word
    BACKGROUND = "background"  # Add background to current word
    SCALE = "scale"            # Scale up current word
    GLOW = "glow"              # Add glow effect


@dataclass(frozen=True)
class CaptionStyle:
    """
    Complete caption styling specification.

    All sizes are for 1080p output (1080x1920).
    """
    # Font settings
    font_name: str
    font_size: int
    font_bold: bool
    font_italic: bool

    # Colors (ASS format: &HAABBGGRR)
    primary_color: str         # Main text color
    secondary_color: str       # Karaoke highlight color
    outline_color: str         # Text outline color
    back_color: str            # Shadow/background color

    # Outline and shadow
    outline_width: float       # Outline thickness (0-4)
    shadow_depth: float        # Shadow offset (0-4)

    # Position
    position: CaptionPosition
    margin_left: int
    margin_right: int
    margin_vertical: int       # Distance from position edge
    alignment: int             # ASS alignment (1-9, numpad layout)

    # Animation
    highlight_style: HighlightStyle
    words_per_line: int        # Max words per caption line
    lines_per_caption: int     # Max lines visible at once

    # Timing
    fade_in_ms: int
    fade_out_ms: int

    def to_ass_style(self, name: str = "Default") -> str:
        """
        Generate ASS style definition string.

        Format: Style: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,
                OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,
                ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,
                Alignment,MarginL,MarginR,MarginV,Encoding
        """
        bold = -1 if self.font_bold else 0
        italic = -1 if self.font_italic else 0

        return (
            f"Style: {name},{self.font_name},{self.font_size},"
            f"{self.primary_color},{self.secondary_color},"
            f"{self.outline_color},{self.back_color},"
            f"{bold},{italic},0,0,"  # Bold,Italic,Underline,StrikeOut
            f"100,100,0,0,"  # ScaleX,ScaleY,Spacing,Angle
            f"1,{self.outline_width},{self.shadow_depth},"  # BorderStyle,Outline,Shadow
            f"{self.alignment},{self.margin_left},{self.margin_right},{self.margin_vertical},"
            f"1"  # Encoding (ANSI)
        )


# Platform-specific caption styles
CAPTION_STYLES = {
    ExportFormat.TIKTOK: CaptionStyle(
        font_name="Montserrat",
        font_size=72,
        font_bold=True,
        font_italic=False,
        primary_color="&H00FFFFFF",      # White
        secondary_color="&H0000FFFF",    # Yellow (for karaoke)
        outline_color="&H00000000",      # Black
        back_color="&H80000000",         # Semi-transparent black
        outline_width=3.0,
        shadow_depth=1.5,
        position=CaptionPosition.CENTER,
        margin_left=80,
        margin_right=80,
        margin_vertical=450,  # Above the safe zone
        alignment=5,          # Center-center (numpad 5)
        highlight_style=HighlightStyle.COLOR_CHANGE,
        words_per_line=5,
        lines_per_caption=2,
        fade_in_ms=0,
        fade_out_ms=100,
    ),
    ExportFormat.YOUTUBE_SHORTS: CaptionStyle(
        font_name="Montserrat",
        font_size=68,
        font_bold=True,
        font_italic=False,
        primary_color="&H00FFFFFF",
        secondary_color="&H0000FFFF",
        outline_color="&H00000000",
        back_color="&H80000000",
        outline_width=3.0,
        shadow_depth=1.5,
        position=CaptionPosition.CENTER,
        margin_left=80,
        margin_right=80,
        margin_vertical=450,
        alignment=5,
        highlight_style=HighlightStyle.COLOR_CHANGE,
        words_per_line=5,
        lines_per_caption=2,
        fade_in_ms=0,
        fade_out_ms=100,
    ),
    ExportFormat.INSTAGRAM_REELS: CaptionStyle(
        font_name="Montserrat",
        font_size=70,
        font_bold=True,
        font_italic=False,
        primary_color="&H00FFFFFF",
        secondary_color="&H0000BFFF",    # Orange-ish
        outline_color="&H00000000",
        back_color="&H80000000",
        outline_width=3.0,
        shadow_depth=1.5,
        position=CaptionPosition.CENTER,
        margin_left=80,
        margin_right=80,
        margin_vertical=430,
        alignment=5,
        highlight_style=HighlightStyle.COLOR_CHANGE,
        words_per_line=5,
        lines_per_caption=2,
        fade_in_ms=0,
        fade_out_ms=100,
    ),
    ExportFormat.LINKEDIN: CaptionStyle(
        font_name="Helvetica Neue",
        font_size=56,
        font_bold=True,
        font_italic=False,
        primary_color="&H00FFFFFF",
        secondary_color="&H00FFCC00",    # LinkedIn blue
        outline_color="&H00000000",
        back_color="&H60000000",
        outline_width=2.5,
        shadow_depth=1.0,
        position=CaptionPosition.LOWER_THIRD,
        margin_left=60,
        margin_right=60,
        margin_vertical=120,
        alignment=2,          # Bottom-center
        highlight_style=HighlightStyle.COLOR_CHANGE,
        words_per_line=7,
        lines_per_caption=2,
        fade_in_ms=50,
        fade_out_ms=50,
    ),
    ExportFormat.TWITTER: CaptionStyle(
        font_name="Inter",
        font_size=48,
        font_bold=True,
        font_italic=False,
        primary_color="&H00FFFFFF",
        secondary_color="&H00F5D300",    # Twitter blue
        outline_color="&H00000000",
        back_color="&H60000000",
        outline_width=2.0,
        shadow_depth=1.0,
        position=CaptionPosition.BOTTOM,
        margin_left=100,
        margin_right=100,
        margin_vertical=80,
        alignment=2,
        highlight_style=HighlightStyle.COLOR_CHANGE,
        words_per_line=8,
        lines_per_caption=2,
        fade_in_ms=50,
        fade_out_ms=50,
    ),
    ExportFormat.SQUARE: CaptionStyle(
        font_name="Montserrat",
        font_size=54,
        font_bold=True,
        font_italic=False,
        primary_color="&H00FFFFFF",
        secondary_color="&H0000FFFF",
        outline_color="&H00000000",
        back_color="&H70000000",
        outline_width=2.5,
        shadow_depth=1.0,
        position=CaptionPosition.LOWER_THIRD,
        margin_left=60,
        margin_right=60,
        margin_vertical=100,
        alignment=2,
        highlight_style=HighlightStyle.COLOR_CHANGE,
        words_per_line=6,
        lines_per_caption=2,
        fade_in_ms=50,
        fade_out_ms=50,
    ),
}


def get_caption_style(format_type: ExportFormat) -> CaptionStyle:
    """
    Get caption style for a specific export format.

    Args:
        format_type: Export format enum

    Returns:
        CaptionStyle for that format
    """
    if format_type not in CAPTION_STYLES:
        # Default to TikTok style
        return CAPTION_STYLES[ExportFormat.TIKTOK]
    return CAPTION_STYLES[format_type]


def scale_style_for_resolution(
    style: CaptionStyle,
    target_width: int,
    target_height: int,
    base_width: int = 1080,
    base_height: int = 1920,
) -> CaptionStyle:
    """
    Scale a caption style for a different resolution.

    Args:
        style: Original style (designed for base resolution)
        target_width: Target video width
        target_height: Target video height
        base_width: Base resolution width
        base_height: Base resolution height

    Returns:
        New CaptionStyle with scaled values
    """
    # Use the smaller scale factor to ensure captions fit
    scale_x = target_width / base_width
    scale_y = target_height / base_height
    scale = min(scale_x, scale_y)

    return CaptionStyle(
        font_name=style.font_name,
        font_size=int(style.font_size * scale),
        font_bold=style.font_bold,
        font_italic=style.font_italic,
        primary_color=style.primary_color,
        secondary_color=style.secondary_color,
        outline_color=style.outline_color,
        back_color=style.back_color,
        outline_width=style.outline_width * scale,
        shadow_depth=style.shadow_depth * scale,
        position=style.position,
        margin_left=int(style.margin_left * scale),
        margin_right=int(style.margin_right * scale),
        margin_vertical=int(style.margin_vertical * scale),
        alignment=style.alignment,
        highlight_style=style.highlight_style,
        words_per_line=style.words_per_line,
        lines_per_caption=style.lines_per_caption,
        fade_in_ms=style.fade_in_ms,
        fade_out_ms=style.fade_out_ms,
    )


def get_fallback_fonts(font_name: str) -> list:
    """
    Get fallback font list for a given font.

    Useful for systems that may not have the exact font installed.
    """
    fallbacks = {
        "Montserrat": ["Montserrat", "Arial Black", "Helvetica Bold", "sans-serif"],
        "Helvetica Neue": ["Helvetica Neue", "Helvetica", "Arial", "sans-serif"],
        "Inter": ["Inter", "Roboto", "Arial", "sans-serif"],
    }
    return fallbacks.get(font_name, [font_name, "Arial", "sans-serif"])


if __name__ == "__main__":
    print("Caption Styles - Test Mode")
    print("=" * 60)

    for fmt in ExportFormat:
        style = get_caption_style(fmt)
        format_spec = get_format(fmt)

        print(f"\n{fmt.value.upper()}")
        print(f"  Font: {style.font_name} {style.font_size}px")
        print(f"  Bold: {style.font_bold}, Italic: {style.font_italic}")
        print(f"  Colors: Primary={style.primary_color}, Highlight={style.secondary_color}")
        print(f"  Outline: {style.outline_width}, Shadow: {style.shadow_depth}")
        print(f"  Position: {style.position.value}, Alignment: {style.alignment}")
        print(f"  Margins: L={style.margin_left}, R={style.margin_right}, V={style.margin_vertical}")
        print(f"  Words/line: {style.words_per_line}, Lines: {style.lines_per_caption}")
        print(f"  Highlight: {style.highlight_style.value}")
        print(f"\n  ASS Style:")
        print(f"    {style.to_ass_style()}")
