"""
Theme definitions for BitCraft Companion.

Provides comprehensive color schemes for different visual themes including
dark, light, high contrast, and colorblind-friendly options.
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
    """Light theme - Clean and accessible styling."""
    
    # Core UI Colors - Clean surface hierarchy
    BACKGROUND_PRIMARY = "#FFFFFF"    # Pure white base
    BACKGROUND_SECONDARY = "#F5F5F5"  # Surface elevation
    BACKGROUND_TERTIARY = "#EEEEEE"   # Higher elevation
    
    # Text Colors - High contrast for accessibility
    TEXT_PRIMARY = "#212121"          # Material Design dark
    TEXT_SECONDARY = "#757575"        # Material Design secondary
    TEXT_DISABLED = "#BDBDBD"         # Material Design disabled
    TEXT_ACCENT = "#1A4971"           # Darker blue for contrast
    
    # Border Colors
    BORDER_DEFAULT = "#CCCCCC"
    BORDER_FOCUS = "#1A4971"          # Darker blue for contrast
    BORDER_DISABLED = "#E0E0E0"
    
    # Button Colors - Better visual hierarchy
    BUTTON_BACKGROUND = "#F5F5F5"
    BUTTON_HOVER = "#EEEEEE"          # Consistent with tertiary
    BUTTON_ACTIVE = "#E0E0E0"         # Pressed state
    BUTTON_DISABLED = "#F8F8F8"       # Subtle disabled state
    
    # Status Colors - Accessible contrast ratios
    STATUS_SUCCESS = "#388E3C"        # Darker green for contrast
    STATUS_WARNING = "#F57C00"        # Darker orange for contrast
    STATUS_ERROR = "#D32F2F"          # Darker red for contrast
    STATUS_INFO = "#1A4971"           # Darker blue for contrast
    STATUS_READY = "#388E3C"          # Darker green for contrast
    STATUS_IN_PROGRESS = "#F57C00"    # Darker orange for contrast
    
    # Connection Colors
    CONNECTION_CONNECTED = "#388E3C"   # Darker green for contrast
    CONNECTION_DISCONNECTED = "#D32F2F"  # Darker red for contrast
    CONNECTION_CONNECTING = "#F57C00"  # Darker orange for contrast
    
    # Activity Colors
    ACTIVITY_INCREASE = "#388E3C"     # Darker green for contrast
    ACTIVITY_DECREASE = "#D32F2F"     # Darker red for contrast
    ACTIVITY_NEUTRAL = "#757575"      # Consistent with text secondary
    
    # Tab Colors
    TAB_ACTIVE = "#1A4971"            # Darker blue for contrast
    TAB_INACTIVE = "#BDBDBD"          # Lighter for better contrast on light backgrounds
    TAB_HOVER = "#E3F2FD"             # Light blue hover state
    
    # TreeView Colors - Enhanced readability
    TREEVIEW_BACKGROUND = "#FFFFFF"   # Pure white
    TREEVIEW_FOREGROUND = "#212121"   # Material Design dark
    TREEVIEW_SELECTED = "#1A4971"     # Darker blue for contrast
    TREEVIEW_HOVER = "#F5F5F5"        # Consistent with secondary
    TREEVIEW_ALTERNATE = "#FAFAFA"    # Subtle alternating rows
    TREEVIEW_HEADER_BACKGROUND = "#E8E8E8"  # Clear header distinction
    
    # Tooltip Colors
    TOOLTIP_BACKGROUND = "#FFFFFF"    # Pure white
    TOOLTIP_BORDER = "#CCCCCC"
    TOOLTIP_TEXT = "#212121"          # Material Design dark
    TOOLTIP_HEADER = "#1A4971"        # Darker blue for contrast
    TOOLTIP_SUBHEADER = "#F57C00"     # Darker orange for contrast


# Theme Registry
AVAILABLE_THEMES: Dict[str, Dict[str, Any]] = {
    "dark": {
        "name": "Dark",
        "description": "",
        "colors": DarkTheme,
        "is_default": True
    },
    "light": {
        "name": "Light", 
        "description": "",
        "colors": LightTheme,
        "is_default": False
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