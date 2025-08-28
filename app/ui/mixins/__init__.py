"""
UI Mixins package for BitCraft Companion.

Provides reusable mixins that can be composed with UI components
to add common functionality like search, filtering, etc.
"""

from .searchable_window_mixin import SearchableWindowMixin, SearchableTabMixin

__all__ = [
    'SearchableWindowMixin',
    'SearchableTabMixin',
]