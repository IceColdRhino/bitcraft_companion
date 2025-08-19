"""
Centralized Treeview styling for BitCraft Companion tabs.

Provides consistent theme-aware styling for all Treeview components across tabs,
eliminating code duplication and ensuring visual consistency.
"""

from tkinter import ttk
from app.ui.themes import get_color


class TreeviewStyles:
    """Centralized Treeview styling utility for consistent UI theming."""
    
    @classmethod
    def get_colors(cls):
        """Get theme-aware colors for TreeView styling."""
        return {
            'background': get_color('TREEVIEW_BACKGROUND'),
            'foreground': get_color('TREEVIEW_FOREGROUND'), 
            'field_background': get_color('TREEVIEW_BACKGROUND'),
            'selected_background': get_color('TREEVIEW_SELECTED'),
            'header_background': get_color('TREEVIEW_HEADER_BACKGROUND'),
            'header_foreground': get_color('TEXT_PRIMARY'),
            'header_active': get_color('TREEVIEW_SELECTED'),
            'scrollbar_background': get_color('BACKGROUND_SECONDARY'),
            'scrollbar_trough': get_color('BACKGROUND_TERTIARY'),
            'scrollbar_arrow': get_color('TEXT_DISABLED'),
            'menu_background': get_color('BACKGROUND_SECONDARY'),
            'menu_foreground': get_color('TEXT_PRIMARY'),
            'menu_active': get_color('TREEVIEW_SELECTED'),
            'child_row_background': get_color('TREEVIEW_ALTERNATE'),
            'empty_foreground': get_color('TEXT_DISABLED')
        }
    
    @classmethod
    def apply_treeview_style(cls, style: ttk.Style):
        """Apply standard Treeview styling with current theme colors."""
        style.theme_use("default")
        colors = cls.get_colors()
        
        # Configure main Treeview
        style.configure(
            "Treeview",
            background=colors['background'],
            foreground=colors['foreground'],
            fieldbackground=colors['field_background'],
            borderwidth=1,
            bordercolor=colors['header_background'],
            rowheight=28,
            relief="solid",
        )
        style.map("Treeview", background=[("selected", colors['selected_background'])])
        
        # Configure headers
        style.configure(
            "Treeview.Heading",
            background=colors['header_background'],
            foreground=colors['header_foreground'],
            font=("Segoe UI", 10, "bold"),
            padding=(6, 4),
            relief="solid",
            borderwidth=1,
            bordercolor=colors['background'],
        )
        style.map("Treeview.Heading", background=[("active", colors['header_active'])])
    
    @classmethod
    def apply_scrollbar_style(cls, style: ttk.Style, tab_name: str):
        """
        Apply custom scrollbar styling with unique style names.
        
        Args:
            style: ttk.Style instance
            tab_name: Name of the tab (e.g., "ActiveCrafting", "PassiveCrafting")
        
        Returns:
            tuple: (vertical_style_name, horizontal_style_name)
        """
        v_style = f"{tab_name}.Vertical.TScrollbar"
        h_style = f"{tab_name}.Horizontal.TScrollbar"
        
        colors = cls.get_colors()
        
        # Configure vertical scrollbar
        style.configure(
            v_style,
            background=colors['scrollbar_background'],
            borderwidth=0,
            arrowcolor=colors['scrollbar_arrow'],
            troughcolor=colors['scrollbar_trough'],
            darkcolor=colors['scrollbar_background'],
            lightcolor=colors['scrollbar_background'],
            width=12,
        )
        
        # Configure horizontal scrollbar
        style.configure(
            h_style,
            background=colors['scrollbar_background'],
            borderwidth=0,
            arrowcolor=colors['scrollbar_arrow'],
            troughcolor=colors['scrollbar_trough'],
            darkcolor=colors['scrollbar_background'],
            lightcolor=colors['scrollbar_background'],
            height=12,
        )
        
        # Configure state-specific scrollbar colors for both orientations
        scrollbar_state_map = {
            'background': [
                ("active", colors['scrollbar_background']),
                ("pressed", colors['scrollbar_background']),
                ("disabled", colors['scrollbar_background']),
                ("!active", colors['scrollbar_background'])
            ],
            'troughcolor': [
                ("active", colors['scrollbar_trough']),
                ("pressed", colors['scrollbar_trough']),
                ("disabled", colors['scrollbar_trough']),
                ("!active", colors['scrollbar_trough'])
            ],
            'arrowcolor': [
                ("active", colors['scrollbar_arrow']),
                ("pressed", colors['scrollbar_arrow']),
                ("disabled", colors['scrollbar_arrow']),
                ("!active", colors['scrollbar_arrow'])
            ]
        }
        
        style.map(v_style, **scrollbar_state_map)
        style.map(h_style, **scrollbar_state_map)
        
        return v_style, h_style
    
    @classmethod
    def get_menu_style_config(cls):
        """Get consistent menu styling configuration."""
        colors = cls.get_colors()
        return {
            'tearoff': 0,
            'background': colors['menu_background'],
            'foreground': colors['menu_foreground'],
            'activebackground': colors['menu_active']
        }
    
    @classmethod
    def configure_tree_tags(cls, tree: ttk.Treeview):
        """Configure common tree tags with consistent styling."""
        colors = cls.get_colors()
        tree.tag_configure(
            "child", 
            background=colors['child_row_background']
        )
        tree.tag_configure(
            "empty", 
            background=colors['background'], 
            foreground=colors['empty_foreground']
        )
        tree.tag_configure(
            "incomplete", 
            background=colors['background'], 
            foreground=colors['foreground']
        )
        tree.tag_configure(
            "partial", 
            background=colors['background'], 
            foreground=colors['foreground']
        )