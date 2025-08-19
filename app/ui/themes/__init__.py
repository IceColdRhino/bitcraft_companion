"""
Theme system for BitCraft Companion.

Provides theme management, color definitions, and dynamic theme switching
capabilities for improved user experience and accessibility.
"""

from .theme_manager import (
    get_theme_manager,
    get_color,
    set_theme,
    register_theme_callback,
    ThemeManager
)

from .theme_definitions import (
    AVAILABLE_THEMES,
    get_theme_names,
    get_theme_info,
    get_default_theme,
    DarkTheme,
    LightTheme,
    HalloweenTheme,
    ThemeColors
)

__all__ = [
    # Theme Manager
    'get_theme_manager',
    'get_color', 
    'set_theme',
    'register_theme_callback',
    'ThemeManager',
    
    # Theme Definitions
    'AVAILABLE_THEMES',
    'get_theme_names',
    'get_theme_info', 
    'get_default_theme',
    'DarkTheme',
    'LightTheme',
    'HalloweenTheme',
    'ThemeColors'
]