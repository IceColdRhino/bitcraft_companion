"""
Theme definitions for BitCraft Companion.

Provides comprehensive color schemes for different visual themes including
dark, light, high contrast, colorblind-friendly options, profession themes,
and seasonal/event themes.
"""
from typing import Dict, Any


class ThemeColors:
    """Base class for theme color definitions."""
    
    # Core UI Colors
    BACKGROUND_PRIMARY: str
    BACKGROUND_SECONDARY: str
    BACKGROUND_TERTIARY: str
    
    # Text Colors
    TEXT_PRIMARY: str
    TEXT_SECONDARY: str
    TEXT_DISABLED: str
    TEXT_ACCENT: str
    
    # Border Colors
    BORDER_DEFAULT: str
    BORDER_FOCUS: str
    BORDER_DISABLED: str
    
    # Button Colors
    BUTTON_BACKGROUND: str
    BUTTON_HOVER: str
    BUTTON_ACTIVE: str
    BUTTON_DISABLED: str
    
    # Status Colors
    STATUS_SUCCESS: str
    STATUS_WARNING: str
    STATUS_ERROR: str
    STATUS_INFO: str
    STATUS_READY: str
    STATUS_IN_PROGRESS: str
    
    # Connection Colors
    CONNECTION_CONNECTED: str
    CONNECTION_DISCONNECTED: str
    CONNECTION_CONNECTING: str
    
    # Activity Colors
    ACTIVITY_INCREASE: str
    ACTIVITY_DECREASE: str
    ACTIVITY_NEUTRAL: str
    
    # Tab Colors
    TAB_ACTIVE: str
    TAB_INACTIVE: str
    TAB_HOVER: str
    
    # TreeView Colors
    TREEVIEW_BACKGROUND: str
    TREEVIEW_FOREGROUND: str
    TREEVIEW_SELECTED: str
    TREEVIEW_HOVER: str
    TREEVIEW_ALTERNATE: str
    TREEVIEW_HEADER_BACKGROUND: str
    
    # Tooltip Colors
    TOOLTIP_BACKGROUND: str
    TOOLTIP_BORDER: str
    TOOLTIP_TEXT: str
    TOOLTIP_HEADER: str
    TOOLTIP_SUBHEADER: str


class DarkTheme(ThemeColors):
    """Dark theme - Material Design compliant styling."""
    
    # Core UI Colors - Material Design elevation system
    BACKGROUND_PRIMARY = "#121212"    # Base surface (0dp elevation)
    BACKGROUND_SECONDARY = "#1E1E1E"  # 1dp elevation overlay
    BACKGROUND_TERTIARY = "#232323"   # 2dp elevation overlay
    
    # Text Colors - Softer for reduced eye strain
    TEXT_PRIMARY = "#E0E0E0"          # Softer than pure white
    TEXT_SECONDARY = "#B0B0B0"        # Better contrast hierarchy
    TEXT_DISABLED = "#757575"         # Material Design disabled
    TEXT_ACCENT = "#235c8b"           # User's preferred blue
    
    # Border Colors
    BORDER_DEFAULT = "#404040"
    BORDER_FOCUS = "#235c8b"          # User's blue for focus
    BORDER_DISABLED = "#2a2a2a"
    
    # Button Colors - Better Material Design compliance
    BUTTON_BACKGROUND = "transparent"
    BUTTON_HOVER = "#2E2E2E"          # 3dp elevation
    BUTTON_ACTIVE = "#363636"         # 6dp elevation  
    BUTTON_DISABLED = "#2a2a2a"
    
    # Status Colors - Material Design standard colors
    STATUS_SUCCESS = "#4CAF50"        # Material Green 500
    STATUS_WARNING = "#FF9800"        # Material Orange 500
    STATUS_ERROR = "#F44336"          # Material Red 500
    STATUS_INFO = "#235c8b"           # User's blue
    STATUS_READY = "#4CAF50"          # Material Green 500
    STATUS_IN_PROGRESS = "#FF9800"    # Material Orange 500
    
    # Connection Colors
    CONNECTION_CONNECTED = "#4CAF50"   # Material Green 500
    CONNECTION_DISCONNECTED = "#F44336"  # Material Red 500
    CONNECTION_CONNECTING = "#FF9800"  # Material Orange 500
    
    # Activity Colors
    ACTIVITY_INCREASE = "#4CAF50"     # Material Green 500
    ACTIVITY_DECREASE = "#F44336"     # Material Red 500
    ACTIVITY_NEUTRAL = "#B0B0B0"      # Consistent with text secondary
    
    # Tab Colors
    TAB_ACTIVE = "#235c8b"            # User's blue
    TAB_INACTIVE = "#757575"          # Material Design secondary
    TAB_HOVER = "#2E2E2E"             # 3dp elevation
    
    # TreeView Colors - Enhanced readability
    TREEVIEW_BACKGROUND = "#1E1E1E"   # 1dp elevation
    TREEVIEW_FOREGROUND = "#E0E0E0"   # Softer text
    TREEVIEW_SELECTED = "#235c8b"     # User's blue
    TREEVIEW_HOVER = "#232323"        # 2dp elevation
    TREEVIEW_ALTERNATE = "#1A1A1A"    # Subtle alternating rows
    TREEVIEW_HEADER_BACKGROUND = "#2C2C2C"  # 6dp elevation
    
    # Tooltip Colors
    TOOLTIP_BACKGROUND = "#2C2C2C"    # 6dp elevation
    TOOLTIP_BORDER = "#404040"
    TOOLTIP_TEXT = "#E0E0E0"          # Softer text
    TOOLTIP_HEADER = "#235c8b"        # User's blue
    TOOLTIP_SUBHEADER = "#FF9800"     # Material Orange


class LightTheme(ThemeColors):
    """Vanilla Light theme - Warm, creamy, and easy on the eyes."""
    
    # Core UI Colors - Warm vanilla surface hierarchy
    BACKGROUND_PRIMARY = "#FDF6E3"    # Warm vanilla cream
    BACKGROUND_SECONDARY = "#F5F0E8"  # Slightly darker cream
    BACKGROUND_TERTIARY = "#EFEAD2"   # Deeper cream tone
    
    # Text Colors - Warm, softer contrast
    TEXT_PRIMARY = "#3D2914"          # Warm dark brown
    TEXT_SECONDARY = "#8B7355"        # Muted brown
    TEXT_DISABLED = "#B8A082"         # Light brown
    TEXT_ACCENT = "#8B4513"           # Saddle brown accent
    
    # Border Colors
    BORDER_DEFAULT = "#D4C4A8"        # Warm beige border
    BORDER_FOCUS = "#8B4513"          # Saddle brown focus
    BORDER_DISABLED = "#E8E0D0"       # Light cream border
    
    # Button Colors - Warm vanilla hierarchy
    BUTTON_BACKGROUND = "#F5F0E8"     # Warm cream
    BUTTON_HOVER = "#EFEAD2"          # Deeper cream
    BUTTON_ACTIVE = "#E8DDC7"         # Pressed cream
    BUTTON_DISABLED = "#F8F5F0"       # Very light cream
    
    # Status Colors - Warm, natural tones
    STATUS_SUCCESS = "#6B8E23"        # Olive green
    STATUS_WARNING = "#CD853F"        # Peru/sandy brown
    STATUS_ERROR = "#A0522D"          # Sienna brown
    STATUS_INFO = "#8B4513"           # Saddle brown
    STATUS_READY = "#6B8E23"          # Olive green
    STATUS_IN_PROGRESS = "#CD853F"    # Peru/sandy brown
    
    # Connection Colors
    CONNECTION_CONNECTED = "#6B8E23"   # Olive green
    CONNECTION_DISCONNECTED = "#A0522D"  # Sienna brown
    CONNECTION_CONNECTING = "#CD853F"  # Peru/sandy brown
    
    # Activity Colors
    ACTIVITY_INCREASE = "#6B8E23"     # Olive green
    ACTIVITY_DECREASE = "#A0522D"     # Sienna brown
    ACTIVITY_NEUTRAL = "#8B7355"      # Consistent with text secondary
    
    # Tab Colors
    TAB_ACTIVE = "#8B4513"            # Saddle brown
    TAB_INACTIVE = "#B8A082"          # Light brown
    TAB_HOVER = "#F0E6D2"             # Light cream hover
    
    # TreeView Colors - Warm vanilla readability
    TREEVIEW_BACKGROUND = "#FDF6E3"   # Warm vanilla
    TREEVIEW_FOREGROUND = "#3D2914"   # Warm dark brown
    TREEVIEW_SELECTED = "#8B4513"     # Saddle brown
    TREEVIEW_HOVER = "#F5F0E8"        # Warm cream
    TREEVIEW_ALTERNATE = "#FAF3E6"    # Very light cream
    TREEVIEW_HEADER_BACKGROUND = "#EFEAD2"  # Deeper cream
    
    # Tooltip Colors
    TOOLTIP_BACKGROUND = "#FDF6E3"    # Warm vanilla
    TOOLTIP_BORDER = "#D4C4A8"        # Warm beige
    TOOLTIP_TEXT = "#3D2914"          # Warm dark brown
    TOOLTIP_HEADER = "#8B4513"        # Saddle brown
    TOOLTIP_SUBHEADER = "#CD853F"     # Peru/sandy brown


# Halloween Theme (seasonal example)
class HalloweenTheme(ThemeColors):
    """Halloween theme - spooky autumn colors with festive flair."""
    
    # Core UI Colors - Autumn/Halloween palette
    BACKGROUND_PRIMARY = "#1A0F08"       # Dark burnt orange/brown
    BACKGROUND_SECONDARY = "#2D1810"     # Darker autumn brown
    BACKGROUND_TERTIARY = "#3D2318"      # Lighter autumn brown
    
    # Text Colors - Warm autumn tones
    TEXT_PRIMARY = "#F4E4D1"             # Warm cream
    TEXT_SECONDARY = "#D4A574"           # Warm amber
    TEXT_DISABLED = "#8B6B3F"            # Muted amber
    TEXT_ACCENT = "#FF8C00"              # Halloween orange
    
    # Border Colors
    BORDER_DEFAULT = "#5D3A1F"           # Dark autumn brown
    BORDER_FOCUS = "#FF8C00"             # Halloween orange
    BORDER_DISABLED = "#3D2318"          # Muted brown
    
    # Button Colors
    BUTTON_BACKGROUND = "transparent"
    BUTTON_HOVER = "#3D2318"             # Autumn brown
    BUTTON_ACTIVE = "#5D3A1F"            # Darker brown
    BUTTON_DISABLED = "#2D1810"          # Dark brown
    
    # Status Colors - Halloween themed
    STATUS_SUCCESS = "#8FBC8F"           # Forest green
    STATUS_WARNING = "#FF8C00"           # Halloween orange  
    STATUS_ERROR = "#DC143C"             # Crimson red
    STATUS_INFO = "#DDA0DD"              # Mystical purple
    STATUS_READY = "#8FBC8F"             # Forest green
    STATUS_IN_PROGRESS = "#FF8C00"       # Halloween orange
    
    # Connection Colors
    CONNECTION_CONNECTED = "#8FBC8F"     # Forest green
    CONNECTION_DISCONNECTED = "#DC143C"  # Crimson red
    CONNECTION_CONNECTING = "#FF8C00"    # Halloween orange
    
    # Activity Colors
    ACTIVITY_INCREASE = "#8FBC8F"        # Forest green
    ACTIVITY_DECREASE = "#DC143C"        # Crimson red
    ACTIVITY_NEUTRAL = "#D4A574"         # Warm amber
    
    # Tab Colors
    TAB_ACTIVE = "#FF8C00"               # Halloween orange
    TAB_INACTIVE = "#8B6B3F"             # Muted amber
    TAB_HOVER = "#3D2318"                # Autumn brown
    
    # TreeView Colors
    TREEVIEW_BACKGROUND = "#2D1810"      # Dark autumn brown
    TREEVIEW_FOREGROUND = "#F4E4D1"      # Warm cream
    TREEVIEW_SELECTED = "#FF8C00"        # Halloween orange
    TREEVIEW_HOVER = "#3D2318"           # Autumn brown
    TREEVIEW_ALTERNATE = "#241611"       # Darker alternating rows
    TREEVIEW_HEADER_BACKGROUND = "#5D3A1F"  # Dark autumn brown
    
    # Tooltip Colors
    TOOLTIP_BACKGROUND = "#5D3A1F"       # Dark autumn brown
    TOOLTIP_BORDER = "#8B6B3F"           # Muted amber
    TOOLTIP_TEXT = "#F4E4D1"             # Warm cream
    TOOLTIP_HEADER = "#FF8C00"           # Halloween orange
    TOOLTIP_SUBHEADER = "#DDA0DD"        # Mystical purple


# Christmas Theme (holiday)
class ChristmasTheme(ThemeColors):
    """Christmas theme - Festive red and green with gold accents."""
    
    # Core UI Colors - Christmas palette
    BACKGROUND_PRIMARY = "#0F2818"       # Deep forest green
    BACKGROUND_SECONDARY = "#1B3D2F"     # Medium forest green
    BACKGROUND_TERTIARY = "#2F5F47"      # Lighter forest green
    
    # Text Colors - Festive and readable
    TEXT_PRIMARY = "#F5F5DC"             # Beige/cream
    TEXT_SECONDARY = "#FFD700"           # Gold
    TEXT_DISABLED = "#8B7355"            # Muted brown
    TEXT_ACCENT = "#DC143C"              # Crimson red
    
    # Border Colors
    BORDER_DEFAULT = "#5A8B5A"           # Forest green
    BORDER_FOCUS = "#DC143C"             # Crimson red
    BORDER_DISABLED = "#3D5F3D"          # Dark green
    
    # Button Colors
    BUTTON_BACKGROUND = "transparent"
    BUTTON_HOVER = "#2F5F47"             # Light forest green
    BUTTON_ACTIVE = "#5A8B5A"            # Medium green
    BUTTON_DISABLED = "#1B3D2F"          # Dark green
    
    # Status Colors - Christmas themed
    STATUS_SUCCESS = "#228B22"           # Forest green
    STATUS_WARNING = "#FFD700"           # Gold
    STATUS_ERROR = "#DC143C"             # Crimson red
    STATUS_INFO = "#4169E1"              # Royal blue
    STATUS_READY = "#228B22"             # Forest green
    STATUS_IN_PROGRESS = "#FFD700"       # Gold
    
    # Connection Colors
    CONNECTION_CONNECTED = "#228B22"     # Forest green
    CONNECTION_DISCONNECTED = "#DC143C"  # Crimson red
    CONNECTION_CONNECTING = "#FFD700"    # Gold
    
    # Activity Colors
    ACTIVITY_INCREASE = "#228B22"        # Forest green
    ACTIVITY_DECREASE = "#DC143C"        # Crimson red
    ACTIVITY_NEUTRAL = "#FFD700"         # Gold
    
    # Tab Colors
    TAB_ACTIVE = "#DC143C"               # Crimson red
    TAB_INACTIVE = "#8B7355"             # Muted brown
    TAB_HOVER = "#2F5F47"                # Light forest green
    
    # TreeView Colors
    TREEVIEW_BACKGROUND = "#1B3D2F"      # Medium forest green
    TREEVIEW_FOREGROUND = "#F5F5DC"      # Beige/cream
    TREEVIEW_SELECTED = "#DC143C"        # Crimson red
    TREEVIEW_HOVER = "#2F5F47"           # Light forest green
    TREEVIEW_ALTERNATE = "#173529"       # Darker green
    TREEVIEW_HEADER_BACKGROUND = "#5A8B5A"  # Medium green
    
    # Tooltip Colors
    TOOLTIP_BACKGROUND = "#5A8B5A"       # Medium green
    TOOLTIP_BORDER = "#8B7355"           # Muted brown
    TOOLTIP_TEXT = "#F5F5DC"             # Beige/cream
    TOOLTIP_HEADER = "#DC143C"           # Crimson red
    TOOLTIP_SUBHEADER = "#FFD700"        # Gold


# Ocean Theme (nature-inspired)
class OceanTheme(ThemeColors):
    """Ocean theme - Calming blues and sea-inspired colors."""
    
    # Core UI Colors - Ocean depths
    BACKGROUND_PRIMARY = "#0C1821"       # Deep ocean blue
    BACKGROUND_SECONDARY = "#1E3A8A"     # Medium ocean blue
    BACKGROUND_TERTIARY = "#3B82F6"      # Light ocean blue
    
    # Text Colors - Sea foam and coral
    TEXT_PRIMARY = "#F0F8FF"             # Alice blue
    TEXT_SECONDARY = "#87CEEB"           # Sky blue
    TEXT_DISABLED = "#6B7280"            # Gray-blue
    TEXT_ACCENT = "#00CED1"              # Dark turquoise
    
    # Border Colors
    BORDER_DEFAULT = "#374151"           # Slate gray
    BORDER_FOCUS = "#00CED1"             # Dark turquoise
    BORDER_DISABLED = "#1F2937"          # Dark gray
    
    # Button Colors
    BUTTON_BACKGROUND = "transparent"
    BUTTON_HOVER = "#3B82F6"             # Light ocean blue
    BUTTON_ACTIVE = "#2563EB"            # Blue
    BUTTON_DISABLED = "#1E3A8A"          # Medium ocean blue
    
    # Status Colors - Ocean themed
    STATUS_SUCCESS = "#10B981"           # Emerald (sea green)
    STATUS_WARNING = "#F59E0B"           # Amber (sunset)
    STATUS_ERROR = "#EF4444"             # Red (coral)
    STATUS_INFO = "#3B82F6"              # Blue (ocean)
    STATUS_READY = "#10B981"             # Emerald
    STATUS_IN_PROGRESS = "#F59E0B"       # Amber
    
    # Connection Colors
    CONNECTION_CONNECTED = "#10B981"     # Emerald
    CONNECTION_DISCONNECTED = "#EF4444"  # Red
    CONNECTION_CONNECTING = "#F59E0B"    # Amber
    
    # Activity Colors
    ACTIVITY_INCREASE = "#10B981"        # Emerald
    ACTIVITY_DECREASE = "#EF4444"        # Red
    ACTIVITY_NEUTRAL = "#87CEEB"         # Sky blue
    
    # Tab Colors
    TAB_ACTIVE = "#00CED1"               # Dark turquoise
    TAB_INACTIVE = "#6B7280"             # Gray-blue
    TAB_HOVER = "#3B82F6"                # Light ocean blue
    
    # TreeView Colors
    TREEVIEW_BACKGROUND = "#1E3A8A"      # Medium ocean blue
    TREEVIEW_FOREGROUND = "#F0F8FF"      # Alice blue
    TREEVIEW_SELECTED = "#00CED1"        # Dark turquoise
    TREEVIEW_HOVER = "#3B82F6"           # Light ocean blue
    TREEVIEW_ALTERNATE = "#1E40AF"       # Darker blue
    TREEVIEW_HEADER_BACKGROUND = "#374151"  # Slate gray
    
    # Tooltip Colors
    TOOLTIP_BACKGROUND = "#374151"       # Slate gray
    TOOLTIP_BORDER = "#6B7280"           # Gray-blue
    TOOLTIP_TEXT = "#F0F8FF"             # Alice blue
    TOOLTIP_HEADER = "#00CED1"           # Dark turquoise
    TOOLTIP_SUBHEADER = "#87CEEB"        # Sky blue


# Forest Theme (nature-inspired)
class ForestTheme(ThemeColors):
    """Forest theme - Natural greens and earth tones."""
    
    # Core UI Colors - Forest depths
    BACKGROUND_PRIMARY = "#1A2E1A"       # Dark forest green
    BACKGROUND_SECONDARY = "#2D5016"     # Medium forest green
    BACKGROUND_TERTIARY = "#4F7942"      # Light forest green
    
    # Text Colors - Natural tones
    TEXT_PRIMARY = "#F5F5DC"             # Beige
    TEXT_SECONDARY = "#DEB887"           # Burlywood
    TEXT_DISABLED = "#8FBC8F"            # Dark sea green
    TEXT_ACCENT = "#32CD32"              # Lime green
    
    # Border Colors
    BORDER_DEFAULT = "#556B2F"           # Dark olive green
    BORDER_FOCUS = "#32CD32"             # Lime green
    BORDER_DISABLED = "#2E4E2E"          # Dark green
    
    # Button Colors
    BUTTON_BACKGROUND = "transparent"
    BUTTON_HOVER = "#4F7942"             # Light forest green
    BUTTON_ACTIVE = "#6B8E23"            # Olive drab
    BUTTON_DISABLED = "#2D5016"          # Medium forest green
    
    # Status Colors - Nature themed
    STATUS_SUCCESS = "#228B22"           # Forest green
    STATUS_WARNING = "#DAA520"           # Goldenrod
    STATUS_ERROR = "#B22222"             # Fire brick
    STATUS_INFO = "#4682B4"              # Steel blue
    STATUS_READY = "#228B22"             # Forest green
    STATUS_IN_PROGRESS = "#DAA520"       # Goldenrod
    
    # Connection Colors
    CONNECTION_CONNECTED = "#228B22"     # Forest green
    CONNECTION_DISCONNECTED = "#B22222"  # Fire brick
    CONNECTION_CONNECTING = "#DAA520"    # Goldenrod
    
    # Activity Colors
    ACTIVITY_INCREASE = "#228B22"        # Forest green
    ACTIVITY_DECREASE = "#B22222"        # Fire brick
    ACTIVITY_NEUTRAL = "#DEB887"         # Burlywood
    
    # Tab Colors
    TAB_ACTIVE = "#32CD32"               # Lime green
    TAB_INACTIVE = "#8FBC8F"             # Dark sea green
    TAB_HOVER = "#4F7942"                # Light forest green
    
    # TreeView Colors
    TREEVIEW_BACKGROUND = "#2D5016"      # Medium forest green
    TREEVIEW_FOREGROUND = "#F5F5DC"      # Beige
    TREEVIEW_SELECTED = "#32CD32"        # Lime green
    TREEVIEW_HOVER = "#4F7942"           # Light forest green
    TREEVIEW_ALTERNATE = "#1E3A1E"       # Darker green
    TREEVIEW_HEADER_BACKGROUND = "#556B2F"  # Dark olive green
    
    # Tooltip Colors
    TOOLTIP_BACKGROUND = "#556B2F"       # Dark olive green
    TOOLTIP_BORDER = "#8FBC8F"           # Dark sea green
    TOOLTIP_TEXT = "#F5F5DC"             # Beige
    TOOLTIP_HEADER = "#32CD32"           # Lime green
    TOOLTIP_SUBHEADER = "#DAA520"        # Goldenrod


# High Contrast Theme (accessibility)
class HighContrastTheme(ThemeColors):
    """High Contrast theme - Maximum accessibility and readability."""
    
    # Core UI Colors - Pure contrast
    BACKGROUND_PRIMARY = "#000000"       # Pure black
    BACKGROUND_SECONDARY = "#1A1A1A"     # Very dark gray
    BACKGROUND_TERTIARY = "#333333"      # Dark gray
    
    # Text Colors - Maximum contrast
    TEXT_PRIMARY = "#FFFFFF"             # Pure white
    TEXT_SECONDARY = "#FFFF00"           # Bright yellow
    TEXT_DISABLED = "#808080"            # Medium gray
    TEXT_ACCENT = "#00FFFF"              # Cyan
    
    # Border Colors
    BORDER_DEFAULT = "#FFFFFF"           # White borders
    BORDER_FOCUS = "#00FFFF"             # Cyan focus
    BORDER_DISABLED = "#808080"          # Gray disabled
    
    # Button Colors
    BUTTON_BACKGROUND = "#000000"        # Black background
    BUTTON_HOVER = "#333333"             # Dark gray hover
    BUTTON_ACTIVE = "#666666"            # Medium gray active
    BUTTON_DISABLED = "#1A1A1A"          # Very dark gray
    
    # Status Colors - High contrast
    STATUS_SUCCESS = "#00FF00"           # Bright green
    STATUS_WARNING = "#FFFF00"           # Bright yellow
    STATUS_ERROR = "#FF0000"             # Bright red
    STATUS_INFO = "#00FFFF"              # Cyan
    STATUS_READY = "#00FF00"             # Bright green
    STATUS_IN_PROGRESS = "#FFFF00"       # Bright yellow
    
    # Connection Colors
    CONNECTION_CONNECTED = "#00FF00"     # Bright green
    CONNECTION_DISCONNECTED = "#FF0000"  # Bright red
    CONNECTION_CONNECTING = "#FFFF00"    # Bright yellow
    
    # Activity Colors
    ACTIVITY_INCREASE = "#00FF00"        # Bright green
    ACTIVITY_DECREASE = "#FF0000"        # Bright red
    ACTIVITY_NEUTRAL = "#FFFFFF"         # White
    
    # Tab Colors
    TAB_ACTIVE = "#00FFFF"               # Cyan
    TAB_INACTIVE = "#808080"             # Medium gray
    TAB_HOVER = "#333333"                # Dark gray
    
    # TreeView Colors
    TREEVIEW_BACKGROUND = "#000000"      # Pure black
    TREEVIEW_FOREGROUND = "#FFFFFF"      # Pure white
    TREEVIEW_SELECTED = "#00FFFF"        # Cyan
    TREEVIEW_HOVER = "#333333"           # Dark gray
    TREEVIEW_ALTERNATE = "#0D0D0D"       # Very dark gray
    TREEVIEW_HEADER_BACKGROUND = "#666666"  # Medium gray
    
    # Tooltip Colors
    TOOLTIP_BACKGROUND = "#000000"       # Pure black
    TOOLTIP_BORDER = "#FFFFFF"           # White border
    TOOLTIP_TEXT = "#FFFFFF"             # Pure white
    TOOLTIP_HEADER = "#00FFFF"           # Cyan
    TOOLTIP_SUBHEADER = "#FFFF00"        # Bright yellow


# Sepia Theme (warm, vintage)
class SepiaTheme(ThemeColors):
    """Sepia theme - Warm, vintage, easy on the eyes."""
    
    # Core UI Colors - Sepia tones
    BACKGROUND_PRIMARY = "#2F1B14"       # Dark sepia
    BACKGROUND_SECONDARY = "#5D2F1E"     # Medium sepia
    BACKGROUND_TERTIARY = "#8B4513"      # Saddle brown
    
    # Text Colors - Warm vintage
    TEXT_PRIMARY = "#F5DEB3"             # Wheat
    TEXT_SECONDARY = "#DEB887"           # Burlywood
    TEXT_DISABLED = "#CD853F"            # Peru
    TEXT_ACCENT = "#DAA520"              # Goldenrod
    
    # Border Colors
    BORDER_DEFAULT = "#A0522D"           # Sienna
    BORDER_FOCUS = "#DAA520"             # Goldenrod
    BORDER_DISABLED = "#696969"          # Dim gray
    
    # Button Colors
    BUTTON_BACKGROUND = "transparent"
    BUTTON_HOVER = "#8B4513"             # Saddle brown
    BUTTON_ACTIVE = "#A0522D"            # Sienna
    BUTTON_DISABLED = "#5D2F1E"          # Medium sepia
    
    # Status Colors - Warm sepia
    STATUS_SUCCESS = "#6B8E23"           # Olive drab
    STATUS_WARNING = "#DAA520"           # Goldenrod
    STATUS_ERROR = "#A0522D"             # Sienna
    STATUS_INFO = "#4682B4"              # Steel blue
    STATUS_READY = "#6B8E23"             # Olive drab
    STATUS_IN_PROGRESS = "#DAA520"       # Goldenrod
    
    # Connection Colors
    CONNECTION_CONNECTED = "#6B8E23"     # Olive drab
    CONNECTION_DISCONNECTED = "#A0522D"  # Sienna
    CONNECTION_CONNECTING = "#DAA520"    # Goldenrod
    
    # Activity Colors
    ACTIVITY_INCREASE = "#6B8E23"        # Olive drab
    ACTIVITY_DECREASE = "#A0522D"        # Sienna
    ACTIVITY_NEUTRAL = "#DEB887"         # Burlywood
    
    # Tab Colors
    TAB_ACTIVE = "#DAA520"               # Goldenrod
    TAB_INACTIVE = "#CD853F"             # Peru
    TAB_HOVER = "#8B4513"                # Saddle brown
    
    # TreeView Colors
    TREEVIEW_BACKGROUND = "#5D2F1E"      # Medium sepia
    TREEVIEW_FOREGROUND = "#F5DEB3"      # Wheat
    TREEVIEW_SELECTED = "#DAA520"        # Goldenrod
    TREEVIEW_HOVER = "#8B4513"           # Saddle brown
    TREEVIEW_ALTERNATE = "#4A251B"       # Darker sepia
    TREEVIEW_HEADER_BACKGROUND = "#A0522D"  # Sienna
    
    # Tooltip Colors
    TOOLTIP_BACKGROUND = "#A0522D"       # Sienna
    TOOLTIP_BORDER = "#CD853F"           # Peru
    TOOLTIP_TEXT = "#F5DEB3"             # Wheat
    TOOLTIP_HEADER = "#DAA520"           # Goldenrod
    TOOLTIP_SUBHEADER = "#DEB887"        # Burlywood


# Valentine's Theme (holiday)
class ValentineTheme(ThemeColors):
    """Valentine's theme - Romantic pinks and reds with elegant touches."""
    
    # Core UI Colors - Valentine palette
    BACKGROUND_PRIMARY = "#2D1B2E"       # Deep purple-pink
    BACKGROUND_SECONDARY = "#4A1E2F"     # Dark rose
    BACKGROUND_TERTIARY = "#8B2635"      # Dark red
    
    # Text Colors - Romantic
    TEXT_PRIMARY = "#FFF0F5"             # Lavender blush
    TEXT_SECONDARY = "#FFB6C1"           # Light pink
    TEXT_DISABLED = "#BC8F8F"            # Rosy brown
    TEXT_ACCENT = "#FF1493"              # Deep pink
    
    # Border Colors
    BORDER_DEFAULT = "#CD5C5C"           # Indian red
    BORDER_FOCUS = "#FF1493"             # Deep pink
    BORDER_DISABLED = "#8B2635"          # Dark red
    
    # Button Colors
    BUTTON_BACKGROUND = "transparent"
    BUTTON_HOVER = "#8B2635"             # Dark red
    BUTTON_ACTIVE = "#CD5C5C"            # Indian red
    BUTTON_DISABLED = "#4A1E2F"          # Dark rose
    
    # Status Colors - Valentine themed
    STATUS_SUCCESS = "#FF69B4"           # Hot pink
    STATUS_WARNING = "#FFD700"           # Gold
    STATUS_ERROR = "#DC143C"             # Crimson
    STATUS_INFO = "#DA70D6"              # Orchid
    STATUS_READY = "#FF69B4"             # Hot pink
    STATUS_IN_PROGRESS = "#FFD700"       # Gold
    
    # Connection Colors
    CONNECTION_CONNECTED = "#FF69B4"     # Hot pink
    CONNECTION_DISCONNECTED = "#DC143C"  # Crimson
    CONNECTION_CONNECTING = "#FFD700"    # Gold
    
    # Activity Colors
    ACTIVITY_INCREASE = "#FF69B4"        # Hot pink
    ACTIVITY_DECREASE = "#DC143C"        # Crimson
    ACTIVITY_NEUTRAL = "#FFB6C1"         # Light pink
    
    # Tab Colors
    TAB_ACTIVE = "#FF1493"               # Deep pink
    TAB_INACTIVE = "#BC8F8F"             # Rosy brown
    TAB_HOVER = "#8B2635"                # Dark red
    
    # TreeView Colors
    TREEVIEW_BACKGROUND = "#4A1E2F"      # Dark rose
    TREEVIEW_FOREGROUND = "#FFF0F5"      # Lavender blush
    TREEVIEW_SELECTED = "#FF1493"        # Deep pink
    TREEVIEW_HOVER = "#8B2635"           # Dark red
    TREEVIEW_ALTERNATE = "#3D1729"       # Darker rose
    TREEVIEW_HEADER_BACKGROUND = "#CD5C5C"  # Indian red
    
    # Tooltip Colors
    TOOLTIP_BACKGROUND = "#CD5C5C"       # Indian red
    TOOLTIP_BORDER = "#BC8F8F"           # Rosy brown
    TOOLTIP_TEXT = "#FFF0F5"             # Lavender blush
    TOOLTIP_HEADER = "#FF1493"           # Deep pink
    TOOLTIP_SUBHEADER = "#FFB6C1"        # Light pink


# Theme Registry with Enhanced Metadata
AVAILABLE_THEMES: Dict[str, Dict[str, Any]] = {
    "dark": {
        "name": "Dark",
        "display_name": "Dark Mode",
        "description": "Material Design compliant dark theme for reduced eye strain",
        "category": "core",
        "author": "BitCraft Companion",
        "version": "1.0",
        "colors": DarkTheme,
        "accessibility": {
            "high_contrast": False,
            "colorblind_friendly": True,
            "reduced_motion": True
        },
        "is_default": True,
        "requires_restart": False
    },
    "light": {
        "name": "Light",
        "display_name": "Light Mode", 
        "description": "Clean and accessible light theme with high contrast ratios",
        "category": "core",
        "author": "BitCraft Companion",
        "version": "1.0",
        "colors": LightTheme,
        "accessibility": {
            "high_contrast": True,
            "colorblind_friendly": True,
            "reduced_motion": True
        },
        "is_default": False,
        "requires_restart": False
    },
    "halloween": {
        "name": "Halloween",
        "display_name": "Halloween",
        "description": "Spooky autumn theme with pumpkins and festive decorations",
        "category": "seasonal",
        "author": "BitCraft Companion",
        "version": "1.0",
        "colors": HalloweenTheme,
        "accessibility": {
            "high_contrast": False,
            "colorblind_friendly": False,
            "reduced_motion": True
        },
        "is_default": False,
        "requires_restart": False,
        "seasonal": {
            "start_date": "10-01",  # October 1st
            "end_date": "11-07",    # November 7th
            "auto_enable": False
        }
    },
    "christmas": {
        "name": "Christmas",
        "display_name": "Christmas",
        "description": "Festive holiday theme with warm reds, greens, and golden accents",
        "category": "seasonal",
        "author": "BitCraft Companion",
        "version": "1.0",
        "colors": ChristmasTheme,
        "accessibility": {
            "high_contrast": False,
            "colorblind_friendly": False,
            "reduced_motion": True
        },
        "is_default": False,
        "requires_restart": False,
        "seasonal": {
            "start_date": "12-01",  # December 1st
            "end_date": "01-07",    # January 7th
            "auto_enable": False
        }
    },
    "ocean": {
        "name": "Ocean",
        "display_name": "Ocean",
        "description": "Calming ocean-inspired theme with blues and turquoise",
        "category": "nature",
        "author": "BitCraft Companion",
        "version": "1.0",
        "colors": OceanTheme,
        "accessibility": {
            "high_contrast": False,
            "colorblind_friendly": True,
            "reduced_motion": True
        },
        "is_default": False,
        "requires_restart": False
    },
    "forest": {
        "name": "Forest",
        "display_name": "Forest",
        "description": "Natural forest theme with greens and earth tones",
        "category": "nature",
        "author": "BitCraft Companion",
        "version": "1.0",
        "colors": ForestTheme,
        "accessibility": {
            "high_contrast": False,
            "colorblind_friendly": True,
            "reduced_motion": True
        },
        "is_default": False,
        "requires_restart": False
    },
    "high_contrast": {
        "name": "HighContrast",
        "display_name": "High Contrast",
        "description": "Maximum contrast theme for enhanced accessibility",
        "category": "accessibility",
        "author": "BitCraft Companion",
        "version": "1.0",
        "colors": HighContrastTheme,
        "accessibility": {
            "high_contrast": True,
            "colorblind_friendly": True,
            "reduced_motion": True
        },
        "is_default": False,
        "requires_restart": False
    },
    "sepia": {
        "name": "Sepia",
        "display_name": "Sepia",
        "description": "Warm vintage sepia-toned theme easy on the eyes",
        "category": "classic",
        "author": "BitCraft Companion",
        "version": "1.0",
        "colors": SepiaTheme,
        "accessibility": {
            "high_contrast": False,
            "colorblind_friendly": True,
            "reduced_motion": True
        },
        "is_default": False,
        "requires_restart": False
    },
    "valentine": {
        "name": "Valentine",
        "display_name": "Valentine",
        "description": "Romantic pink and red theme for Valentine's Day",
        "category": "seasonal",
        "author": "BitCraft Companion",
        "version": "1.0",
        "colors": ValentineTheme,
        "accessibility": {
            "high_contrast": False,
            "colorblind_friendly": False,
            "reduced_motion": True
        },
        "is_default": False,
        "requires_restart": False,
        "seasonal": {
            "start_date": "02-01",  # February 1st
            "end_date": "02-20",    # February 20th
            "auto_enable": False
        }
    }
}


def get_theme_names() -> list:
    """Get list of available theme names."""
    return list(AVAILABLE_THEMES.keys())


def get_theme_info(theme_name: str) -> Dict[str, Any]:
    """Get theme information by name."""
    return AVAILABLE_THEMES.get(theme_name, AVAILABLE_THEMES["dark"])


def get_default_theme() -> str:
    """Get the default theme name."""
    for theme_name, theme_info in AVAILABLE_THEMES.items():
        if theme_info.get("is_default", False):
            return theme_name
    return "dark"  # Fallback