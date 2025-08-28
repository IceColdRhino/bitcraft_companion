"""
CodexWindow - Enhanced Tabbed Implementation

A comprehensive window for displaying codex material requirements organized by profession.
Features tabbed interface, progress summary, search functionality, and non-modal behavior.

Key principles:
- Immediate window display (no blocking)
- Progressive loading with clear status messages
- Tabbed interface for each profession
- Cross-profession search functionality
- Progress summary header showing all professions
- Normal window behavior (not always-on-top)
"""

import logging
import threading
import tkinter as tk
from tkinter import ttk
from typing import Dict, Optional, List, Any
import customtkinter as ctk
from PIL import Image

from app.ui.themes import get_color
from app.ui.styles import TreeviewStyles
from app.ui.mixins import SearchableWindowMixin


class CodexProfessionTab(ctk.CTkFrame):
    """Individual profession tab showing material requirements."""

    def __init__(self, parent, profession_name: str, codex_window=None):
        super().__init__(parent, fg_color="transparent")
        self.profession_name = profession_name
        self.materials_data = {}
        self.codex_window = codex_window

        # Sorting state (like main window tabs)
        self.sort_column = "Material"  # Default sort by material name
        self.sort_reverse = False  # Ascending by default

        self._create_widgets()

    def _create_widgets(self):
        """Create the profession-specific materials table."""
        # Add refined product status bar at the bottom first
        self.refined_status_frame = ctk.CTkFrame(
            self,
            height=32,
            fg_color=get_color("BACKGROUND_SECONDARY"),
            border_width=1,
            border_color=get_color("BORDER_DEFAULT"),
            corner_radius=8,
        )
        self.refined_status_frame.pack(side="bottom", fill="x", padx=0, pady=(0, 0))
        self.refined_status_frame.pack_propagate(False)

        # Create inner frame for proper padding
        inner_frame = ctk.CTkFrame(self.refined_status_frame, fg_color="transparent")
        inner_frame.pack(fill="x", padx=8, pady=4)

        # Store the profession name for later use in updates
        self._profession_name = self.profession_name

        self.refined_status_label = ctk.CTkLabel(
            inner_frame,
            text=f"Loading {self.profession_name.title()}...",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="normal"),
            text_color=get_color("TEXT_PRIMARY"),
        )
        self.refined_status_label.pack(side="left", padx=(8, 0))

        # Create frame for treeview and scrollbar - pack after status bar
        tree_frame = ctk.CTkFrame(self, fg_color="transparent")
        tree_frame.pack(fill="both", expand=True, padx=0, pady=(0, 10))

        # Create treeview
        columns = ("Material", "Tier", "Need", "Supply", "Progress")
        self.materials_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=20)

        # Configure columns with sorting commands (like main window)
        self.materials_tree.heading("Material", text="Material", anchor="w", command=lambda: self.sort_by("Material"))
        self.materials_tree.heading("Tier", text="Tier", anchor="center", command=lambda: self.sort_by("Tier"))
        self.materials_tree.heading("Need", text="Need", anchor="center", command=lambda: self.sort_by("Need"))
        self.materials_tree.heading("Supply", text="Supply", anchor="center", command=lambda: self.sort_by("Supply"))
        self.materials_tree.heading("Progress", text="Progress", anchor="center", command=lambda: self.sort_by("Progress"))

        self.materials_tree.column("Material", width=320, anchor="w")
        self.materials_tree.column("Tier", width=60, anchor="center")
        self.materials_tree.column("Need", width=100, anchor="center")
        self.materials_tree.column("Supply", width=100, anchor="center")
        self.materials_tree.column("Progress", width=80, anchor="center")

        # Configure treeview tags for color coding
        self.materials_tree.tag_configure("completed", foreground=get_color("STATUS_SUCCESS"))
        self.materials_tree.tag_configure("incomplete", foreground=get_color("TEXT_PRIMARY"))
        self.materials_tree.tag_configure("completed_bold", foreground=get_color("STATUS_SUCCESS"), font=("Segoe UI", 9, "bold"))
        self.materials_tree.tag_configure("incomplete_bold", foreground=get_color("TEXT_PRIMARY"), font=("Segoe UI", 9, "bold"))

        # Apply themed scrollbar styling
        style = ttk.Style()
        TreeviewStyles.apply_treeview_style(style)
        v_scrollbar_style, _ = TreeviewStyles.apply_scrollbar_style(style, "CodexMaterials")

        # Add themed scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.materials_tree.yview, style=v_scrollbar_style)
        self.materials_tree.configure(yscrollcommand=scrollbar.set)

        # Pack treeview and scrollbar
        self.materials_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Add initial loading message - use display name if we have access to parent
        display_name = self.profession_name.title()  # Fallback to title case
        self.materials_tree.insert("", "end", values=(f"Loading {display_name} materials...", "", "", "", ""))

    def sort_by(self, column: str):
        """Sort the materials by the specified column (like main window tabs)."""
        # Toggle sort direction if clicking the same column
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False

        # Re-render with current data
        self._sort_and_display_materials()

        # Update visual indicators
        self._update_sort_arrows()

    def _sort_and_display_materials(self):
        """Sort and redisplay the materials based on current sort settings."""
        if not self.materials_data:
            return

        # Convert materials dict to list for sorting
        materials_list = []
        for material_name, material_info in self.materials_data.items():
            materials_list.append(
                {
                    "material": material_name,
                    "tier": material_info.get("tier", 0),
                    "need": material_info.get("need", 0),
                    "supply": material_info.get("supply", 0),
                    "progress": material_info.get("progress", 0),
                    "is_direct_dependency": material_info.get("is_direct_dependency", False),
                }
            )

        # Map column names to data keys
        column_to_key = {"Material": "material", "Tier": "tier", "Need": "need", "Supply": "supply", "Progress": "progress"}

        sort_key = column_to_key.get(self.sort_column, "material")
        is_numeric = sort_key in ["tier", "need", "supply", "progress"]

        # Sort the materials
        try:
            materials_list.sort(key=lambda x: x[sort_key] if is_numeric else str(x[sort_key]).lower(), reverse=self.sort_reverse)
        except (KeyError, TypeError):
            # Fallback to material name if sorting fails
            materials_list.sort(key=lambda x: str(x["material"]).lower())

        # Clear and repopulate the tree
        self.materials_tree.delete(*self.materials_tree.get_children())

        for material in materials_list:
            need = material["need"]
            supply = material["supply"]
            progress = material["progress"]
            tier = material["tier"]
            material_name = material["material"]
            is_direct_dependency = material.get("is_direct_dependency", False)

            # Format progress as percentage
            progress_percent = f"{int(progress * 100)}%"

            # Determine color and style tag based on completion and direct dependency status
            if progress >= 1.0:
                tag = "completed_bold" if is_direct_dependency else "completed"
            else:
                tag = "incomplete_bold" if is_direct_dependency else "incomplete"

            # Insert the row with appropriate style tag
            self.materials_tree.insert(
                "", "end", values=(material_name, tier, f"{int(need):,}", f"{int(supply):,}", progress_percent), tags=(tag,)
            )

    def _update_sort_arrows(self):
        """Update column headers with sort direction arrows (like main window)."""
        columns = ["Material", "Tier", "Need", "Supply", "Progress"]

        for column in columns:
            # Base text
            text = column

            # Add arrow if this is the current sort column
            if self.sort_column == column:
                text += " ↓" if not self.sort_reverse else " ↑"

            # Update the heading
            anchor = "w" if column == "Material" else "center"
            self.materials_tree.heading(column, text=text, anchor=anchor, command=lambda c=column: self.sort_by(c))

    def update_materials(self, materials_data: Dict):
        """Update the materials table with new data and preserve sorting."""
        self.materials_data = materials_data

        if not materials_data:
            # Clear existing data and show appropriate message
            self.materials_tree.delete(*self.materials_tree.get_children())
            if self.profession_name == "metal":
                self.materials_tree.insert("", "end", values=("Metal template not yet available", "", "", "", ""))
            else:
                self.materials_tree.insert("", "end", values=(f"No materials found for {self.profession_name}", "", "", "", ""))
            return

        # Apply sorting to the new data and display
        self._sort_and_display_materials()

        # Update sort indicators
        self._update_sort_arrows()

    def update_refined_status(self, refined_count: int, target_tier: int, codex_required: int):
        """Update the refined product status bar with actual item name from cached refined_mats."""
        try:
            if self.codex_window and hasattr(self.codex_window, "refined_mats"):
                display_name = self.codex_window.refined_mats.get(self.profession_name)
                if not display_name:
                    # Show error instead of fallback
                    display_name = f"ERROR: No refined item for {self.profession_name}"
            else:
                display_name = f"ERROR: No refined data"

            actual_material_tier = target_tier - 1
            refined_text = f"T{actual_material_tier} {display_name}: {refined_count}/{codex_required}"
            self.refined_status_label.configure(text=refined_text)
        except Exception as e:
            logging.error(f"Error updating refined status for {self.profession_name}: {e}")
            actual_material_tier = target_tier - 1
            refined_text = f"T{actual_material_tier} Refined {self.profession_name.title()}: {refined_count}/{codex_required}"
            self.refined_status_label.configure(text=refined_text)


class CodexWindow(ctk.CTkToplevel, SearchableWindowMixin):
    """
    Enhanced codex material requirements window with tabbed interface and search.

    Features:
    - Progress summary header for all professions
    - Individual profession tabs
    - Cross-profession material search functionality
    - Normal window behavior (not modal)
    - Progressive data loading
    """

    def __init__(self, parent, data_service=None):
        """Initialize the enhanced codex window."""
        super().__init__(parent)

        self.data_service = data_service
        self.parent = parent

        # Profession tabs and data
        self.professions = ["cloth", "metal", "wood", "stone", "leather", "scholar"]

        # Display name mapping (internal name -> product name)
        self.profession_display_names = {
            "cloth": "Cloth",
            "metal": "Metal",
            "wood": "Plank",
            "stone": "Brick",
            "leather": "Leather",
            "scholar": "Journal",
        }

        self.profession_tabs: Dict[str, CodexProfessionTab] = {}
        self.tab_buttons: Dict[str, ctk.CTkButton] = {}
        self.active_profession = None
        self.all_requirements = {}
        self.target_tier = None
        self.cached_codex_requirements = None  # Cache to avoid duplicate calls
        self.cached_codex_quantity = None  # Cache extracted quantity
        self.cached_inventory = None  # Cache consolidated inventory
        self.cached_inventory_timestamp = 0  # Track when inventory was cached
        self.cached_codex_name = None  # Cache codex name
        self.refined_mats = {}  # Actual refined material names mapped to professions

        # Window configuration - NOT modal, match main window background
        self.title("Codex")
        self.geometry("900x700")
        self.minsize(700, 500)
        self.configure(fg_color=get_color("BACKGROUND_PRIMARY"))  # Match main window

        # Center the window (no transient/grab_set for normal behavior)
        self._center_window()

        # Create UI immediately (no blocking)
        self._create_widgets()

        # Show loading overlay immediately - BEFORE any data operations
        self._show_loading_overlay()

        # Bring window to front without making it always-on-top
        self.lift()
        self.focus()

        # Start loading data progressively after UI is fully rendered
        self.after(50, self._start_data_loading)

        logging.info("Enhanced CodexWindow opened (immediate display, non-modal)")

    def _center_window(self):
        """Center the window on the parent."""
        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (900 // 2)
        y = (self.winfo_screenheight() // 2) - (700 // 2)
        self.geometry(f"900x700+{x}+{y}")

    def _create_widgets(self):
        """Create the enhanced UI following main window design patterns."""
        # Configure grid layout like main window
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)  # Tab content area expands

        # Row 0: Tier Progress Header (like claim_info header)
        self._create_tier_progress_header()

        # Row 1: Profession Progress Summary (compact)
        self._create_profession_progress_summary()

        # Row 2: Tab buttons frame (like main window)
        self.tab_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.tab_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 5))
        self._create_tab_buttons()

        # Row 3: Search frame (like main window)
        self.search_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.search_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(5, 8))

        # Row 4: Tab content area (like main window - 8px bottom padding as requested)
        self.tab_content_area = ctk.CTkFrame(self, fg_color="transparent")
        self.tab_content_area.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self.tab_content_area.grid_columnconfigure(0, weight=1)
        self.tab_content_area.grid_rowconfigure(0, weight=1)

        self._create_profession_tabs()
        self._create_loading_overlay()

    def _create_tier_progress_header(self):
        """Create simplified tier progress header with close button (Row 0)."""
        tier_frame = ctk.CTkFrame(
            self,
            fg_color=get_color("BACKGROUND_SECONDARY"),
            border_width=1,
            border_color=get_color("BORDER_DEFAULT"),
            corner_radius=8,
        )
        tier_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        tier_frame.grid_columnconfigure(0, weight=1)

        # Main content with close button layout
        content_frame = ctk.CTkFrame(tier_frame, fg_color="transparent")
        content_frame.pack(fill="x", padx=15, pady=12)

        # Tier progress label (left side)
        self.tier_progress_label = ctk.CTkLabel(
            content_frame,
            text="Loading tier information...",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=get_color("TEXT_PRIMARY"),
        )
        self.tier_progress_label.pack(side="left")


        # Close button (top right, like main window quit button)
        close_button = ctk.CTkButton(
            content_frame,
            text="Close",
            width=70,
            height=32,
            font=ctk.CTkFont(size=12),
            command=self.destroy,
            fg_color=get_color("STATUS_ERROR"),
            hover_color=get_color("STATUS_ERROR"),
            text_color=get_color("TEXT_PRIMARY"),
            corner_radius=8,
        )
        close_button.pack(side="right")

        # Progress bar below header text with minimal padding
        progress_container = ctk.CTkFrame(tier_frame, fg_color="transparent")
        progress_container.pack(fill="x", padx=15, pady=(0, 8))  # Very low padding

        self.tier_progress_bar = ctk.CTkProgressBar(progress_container, width=250)
        self.tier_progress_bar.set(0)
        self.tier_progress_bar.pack(anchor="w")  # Left aligned like main window elements

    def _create_profession_progress_summary(self):
        """Create compact profession progress summary like claim info header sections (Row 1)."""
        progress_frame = ctk.CTkFrame(
            self,
            fg_color=get_color("BACKGROUND_SECONDARY"),
            border_width=1,
            border_color=get_color("BORDER_DEFAULT"),
            corner_radius=8,
        )
        progress_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(5, 5))
        progress_frame.grid_columnconfigure(0, weight=1)

        # Single row layout for all professions - like claim info sections
        professions_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        professions_frame.pack(fill="x", padx=15, pady=12)

        self.profession_progress_labels = {}

        # Horizontal layout - all 5 professions as sections
        for i, profession in enumerate(self.professions):
            prof_section = ctk.CTkFrame(professions_frame, fg_color="transparent")
            prof_section.pack(side="left", fill="x", expand=True, padx=(15 if i > 0 else 0, 0))

            # Profession name (header) - use display name
            display_name = self.profession_display_names.get(profession, profession.title())
            prof_label = ctk.CTkLabel(
                prof_section,
                text=display_name,  # Product names: Cloth, Ingot, Plank, Brick, Leather, Journal
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=get_color("TEXT_PRIMARY"),
            )
            prof_label.pack(anchor="center")

            # Progress as x/y (%) - like treasury/supplies format
            progress_label = ctk.CTkLabel(
                prof_section, text="0/0 (0%)", font=ctk.CTkFont(size=10), text_color=get_color("TEXT_SECONDARY")
            )
            progress_label.pack(anchor="center", pady=(2, 0))

            self.profession_progress_labels[profession] = progress_label

    def _create_tab_buttons(self):
        """Create profession tab buttons."""
        for i, profession in enumerate(self.professions):
            display_name = self.profession_display_names.get(profession, profession.title())
            btn = ctk.CTkButton(
                self.tab_frame,
                text=display_name,
                width=120,
                height=38,
                corner_radius=10,
                border_width=2,
                border_color=get_color("BORDER_DEFAULT"),
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=get_color("BUTTON_BACKGROUND"),
                hover_color=get_color("BUTTON_HOVER"),
                text_color=get_color("TEXT_PRIMARY"),
                command=lambda p=profession: self._show_profession_tab(p),
            )
            btn.grid(row=0, column=i, padx=(0 if i == 0 else 4, 0), pady=(0, 2), sticky="w")
            self.tab_buttons[profession] = btn

    def _create_profession_tabs(self):
        """Create individual profession tabs."""
        for profession in self.professions:
            tab = CodexProfessionTab(self.tab_content_area, profession, codex_window=self)
            tab.grid(row=0, column=0, sticky="nsew")
            self.profession_tabs[profession] = tab

        # Configure grid weight
        self.tab_content_area.grid_rowconfigure(0, weight=1)
        self.tab_content_area.grid_columnconfigure(0, weight=1)

        # Show first tab by default
        if self.professions:
            self._show_profession_tab(self.professions[0])

    def _show_profession_tab(self, profession: str):
        """Show the specified profession tab."""
        if self.active_profession == profession:
            return

        # Switch search context to preserve per-tab search state
        self._switch_search_context(profession)

        # Update button states
        for prof, btn in self.tab_buttons.items():
            if prof == profession:
                btn.configure(fg_color=get_color("TEXT_ACCENT"), border_color=get_color("TEXT_ACCENT"))
            else:
                btn.configure(fg_color=get_color("BUTTON_BACKGROUND"), border_color=get_color("BORDER_DEFAULT"))

        # Show the selected tab
        for prof, tab in self.profession_tabs.items():
            if prof == profession:
                tab.tkraise()
            else:
                tab.lower()

        logging.info(f"Switched to {profession} profession tab")

    def _update_progress_summary(self):
        """Update the progress summary for all professions."""
        for profession in self.professions:
            completed = 0
            total = 0

            if profession in self.all_requirements:
                materials = self.all_requirements[profession]
                total = len(materials)
                if materials:
                    completed = sum(1 for mat in materials.values() if mat.get("progress", 0) >= 1.0)

            # Calculate percentage
            percentage = int((completed / total * 100)) if total > 0 else 0

            # Update label with x/y (%) format like claim info
            self.profession_progress_labels[profession].configure(text=f"{completed}/{total} ({percentage}%)")

    def _start_data_loading(self):
        """Start non-blocking progressive data loading."""
        # Show loading overlay first
        self._show_loading_overlay()

        # Use incremental loading on main thread with small delays to avoid blocking
        self.after(100, self._check_services_and_continue)

    def _check_services_and_continue(self):
        """Check if services are available and continue loading."""
        try:
            # Check if we have a data service and codex service
            if not self.data_service:
                self._show_error_and_hide_loading("No data service available")
                return

            if not hasattr(self.data_service, "codex_service") or not self.data_service.codex_service:
                self._show_error_and_hide_loading("Codex service not available")
                return

            # Continue with template loading
            self.after(50, self._load_templates_and_continue)

        except Exception as e:
            logging.error(f"Error checking services: {e}")
            self._show_error_and_hide_loading(f"Error checking services: {e}")

    def _load_templates_and_continue(self):
        """Load templates and continue with data loading."""
        try:
            codex_service = self.data_service.codex_service

            # Check if templates are loaded
            if not codex_service.are_templates_loaded():
                # Try to load templates in background thread to avoid blocking
                loading_thread = threading.Thread(target=self._load_templates_async, daemon=True)
                loading_thread.start()
            else:
                # Templates already loaded, continue immediately
                self.after(50, self._continue_with_claim_info)

        except Exception as e:
            logging.error(f"Error loading templates: {e}")
            self._show_error_and_hide_loading(f"Error loading templates: {e}")

    def _load_templates_async(self):
        """Load templates in background thread."""
        try:
            codex_service = self.data_service.codex_service
            if codex_service.load_templates_sync():
                # Templates loaded successfully, continue on main thread
                self.after(10, self._continue_with_claim_info)
            else:
                # Failed to load templates
                self.after(10, lambda: self._show_error_and_hide_loading("Failed to load codex templates"))
        except Exception as e:
            logging.error(f"Error in async template loading: {e}")
            self.after(10, lambda: self._show_error_and_hide_loading(f"Error loading templates: {e}"))

    def _continue_with_claim_info(self):
        """Continue loading with claim information."""
        try:
            # Get claim information
            claim_info = self._get_claim_info()

            # Update claim header
            if claim_info:
                self._update_claim_header(claim_info)

            # Load material requirements
            self.after(50, lambda: self._load_all_profession_requirements_and_finish(claim_info))

        except Exception as e:
            logging.error(f"Error getting claim info: {e}")
            self._show_error_and_hide_loading(f"Error getting claim info: {e}")

    def _show_error_and_hide_loading(self, message: str):
        """Show error message and hide loading overlay."""
        self._hide_loading_overlay()
        self._show_error(message)

    def _load_all_profession_requirements_and_finish(self, claim_info):
        """Load profession requirements in background thread to avoid blocking."""
        # Start background calculation
        calc_thread = threading.Thread(target=self._calculate_requirements_async, args=(claim_info,), daemon=True)
        calc_thread.start()

    def _calculate_requirements_async(self, claim_info):
        """Calculate requirements in background thread."""
        try:
            codex_service = self.data_service.codex_service

            # This now uses caching and is much faster - pass self for refined product calculations
            requirements = codex_service.calculate_tier_requirements(codex_window=self)

            # Schedule UI update on main thread
            self.after(10, lambda: self._update_ui_with_requirements(requirements))

        except Exception as e:
            logging.error(f"Error calculating requirements: {e}")
            # Provide specific error message based on the failure type
            error_message = self._get_user_friendly_error_message(str(e))
            self.after(10, lambda: self._show_error_and_hide_loading(error_message))

    def _update_ui_with_requirements(self, requirements):
        """Update UI with calculated requirements (runs on main thread)."""
        try:
            if not requirements:
                self._show_error_and_hide_loading("No material requirements found")
                return

            # Store requirements for progress calculation
            self.all_requirements = requirements

            # Update each profession tab and refined status
            total_materials = 0
            for profession in self.professions:
                if profession in requirements:
                    profession_materials = requirements[profession]
                    self.profession_tabs[profession].update_materials(profession_materials)
                    total_materials += len(profession_materials)
                else:
                    # No materials for this profession
                    self.profession_tabs[profession].update_materials({})

                # Update refined product status
                refined_count = self._get_refined_product_count(profession, self.target_tier)
                codex_required = self._get_cached_codex_quantity()
                self.profession_tabs[profession].update_refined_status(refined_count, self.target_tier, codex_required)

            # Update progress summary
            self._update_progress_summary()

            # Initialize search functionality now that data is loaded
            self._setup_search_after_data_load()

            logging.info(f"Loaded {total_materials} material requirements across {len(requirements)} professions")

            # Hide loading overlay after successful data load
            self._hide_loading_overlay()

        except Exception as e:
            logging.error(f"Error updating UI with requirements: {e}")
            self._show_error_and_hide_loading(f"Error updating UI: {e}")

    def _get_claim_info(self):
        """Get current claim information using real claim tech data."""
        try:
            codex_service = self.data_service.codex_service if hasattr(self.data_service, "codex_service") else None

            # Get real tier data from codex service with graceful degradation
            if not codex_service:
                logging.warning("No codex service available, using default tier values")
                current_tier = 4
                target_tier = 5
            else:
                current_tier = codex_service.get_current_claim_tier()
                target_tier = codex_service.get_target_tier()

            # Get claim name
            claim_name = "Unknown Claim"
            if hasattr(self.data_service, "claim_manager") and self.data_service.claim_manager:
                current_claim = self.data_service.claim_manager.get_current_claim()
                if current_claim:
                    claim_name = current_claim.get("name", "Unknown Claim")

            return {"name": claim_name, "tier": current_tier, "target_tier": target_tier}

        except Exception as e:
            logging.debug(f"Error getting claim info: {e}")
            return {"name": "Unknown Claim", "tier": 4, "target_tier": 5}

    def _update_claim_header(self, claim_info):
        """Update the claim information header with tier progress at top."""
        if claim_info:
            tier_names = {
                1: "Beginners",
                2: "Novice",
                3: "Essential",
                4: "Proficient",
                5: "Advanced",
                6: "Comprehensive",
                7: "Flawless",
                8: "Magnificent",
                9: "Pristine",
                10: "Ornate",
            }

            current_tier = claim_info["tier"]
            target_tier = claim_info["target_tier"]
            target_codex = tier_names.get(target_tier, f"T{target_tier}")

            # Store target tier for use in other methods
            self.target_tier = target_tier
            self.cached_codex_requirements = None  # Clear cache when tier changes
            self.cached_codex_quantity = None  # Clear quantity cache when tier changes
            self.cached_codex_name = None  # Clear codex name cache when tier changes
            # Inventory cache doesn't need clearing on tier change

            logging.debug(f"Codex calculation: current_tier={current_tier}, target_tier={target_tier}")

            # Get codex requirements from codex service
            codex_requirements = {}
            try:
                if hasattr(self.data_service, "codex_service") and self.data_service.codex_service:
                    codex_requirements = self._get_cached_codex_requirements()
            except Exception as e:
                logging.debug(f"Error getting codex requirements: {e}")

            # Calculate codex count and progress
            supplies_cost = codex_requirements.get("supplies_cost", max(0, (target_tier - 2) * 5000))
            # Get actual codex count from input array (not calculated from supplies)
            codex_required = self._get_cached_codex_quantity()
            codex_current = self._get_completed_codex_count(target_tier)

            # Update tier progress header (top) with actual codex name
            codex_name = self._get_codex_name()
            tier_progress_text = f"Next Tier: {target_tier} | {codex_name} Required: {codex_current}/{codex_required}"
            self.tier_progress_label.configure(text=tier_progress_text)

            # Update tier progress bar
            progress = codex_current / codex_required if codex_required > 0 else 0
            self.tier_progress_bar.set(progress)

    def _extract_codex_quantity_from_requirements(self, requirements: Dict, target_tier: int) -> int:
        """
        Extract actual codex quantity from claim_tech_desc input array.

        Raises exceptions instead of returning fallback values to make failures explicit.

        Args:
            requirements: codex requirements dict containing input array
            target_tier: target tier for calculation

        Returns:
            Actual codex quantity required
        """
        if "error" in requirements:
            logging.error(f"Requirements dict contains error: {requirements['error']}")
            raise RuntimeError(f"Requirements dict contains error: {requirements['error']}")

        input_array = requirements.get("input", [])

        if not input_array or len(input_array) == 0:
            logging.error(f"Empty or missing input array for tier {target_tier}")
            raise RuntimeError(f"Empty or missing input array for tier {target_tier}")

        first_entry = input_array[0]

        if not isinstance(first_entry, (list, tuple)) or len(first_entry) < 2:
            logging.error(f"Malformed input array entry for tier {target_tier}")
            raise RuntimeError(f"First entry malformed - expected list/tuple with 2+ elements")

        codex_quantity = first_entry[1]

        if not isinstance(codex_quantity, int) or codex_quantity <= 0:
            logging.error(f"Invalid codex quantity {codex_quantity} for tier {target_tier}")
            raise RuntimeError(f"Invalid codex quantity {codex_quantity}")

        logging.debug(f"Tier {target_tier} requires {codex_quantity} codex items")
        return codex_quantity

    def _get_cached_codex_requirements(self) -> Dict:
        """Get cached codex requirements, fetching once if needed."""
        if self.cached_codex_requirements is None:
            logging.info(f"Fetching codex requirements for tier {self.target_tier}")
            self.cached_codex_requirements = self.data_service.codex_service.get_codex_requirements_for_tier(self.target_tier)
        return self.cached_codex_requirements

    def _get_cached_codex_quantity(self) -> int:
        """Get cached codex quantity, extracting once if needed."""
        if self.cached_codex_quantity is None:
            logging.info(f"Extracting codex quantity for tier {self.target_tier}")
            requirements = self._get_cached_codex_requirements()
            self.cached_codex_quantity = self._extract_codex_quantity_from_requirements(requirements, self.target_tier)
        return self.cached_codex_quantity

    def _get_cached_inventory(self) -> Dict:
        """Get cached consolidated inventory, refreshing if older than 30 seconds."""
        import time

        current_time = time.time()

        # Refresh cache if older than 30 seconds
        if self.cached_inventory is None or (current_time - self.cached_inventory_timestamp) > 30:
            self.cached_inventory = self.data_service.get_consolidated_inventory()
            self.cached_inventory_timestamp = current_time
            if self.cached_inventory:
                logging.debug(f"Refreshed inventory cache: {len(self.cached_inventory)} items")

        return self.cached_inventory or {}

    def _get_codex_name(self) -> str:
        """Get the actual codex name for the target tier, no fallbacks."""
        if self.cached_codex_name is None:
            logging.info(f"Looking up codex name for tier {self.target_tier}")

            # Get codex requirements to find the actual required codex ID
            codex_requirements = self._get_cached_codex_requirements()
            input_array = codex_requirements.get("input", [])

            if not input_array or len(input_array) == 0 or len(input_array[0]) < 1:
                logging.error(f"No codex item ID found for tier {self.target_tier}")
                raise RuntimeError(f"No codex item ID found for tier {self.target_tier}")

            codex_item_id = input_array[0][0]  # Get actual codex item ID

            # Find ItemLookupService
            item_lookup_service = None
            for processor in self.data_service.processors:
                if hasattr(processor, "services") and processor.services:
                    item_lookup_service = processor.services.get("item_lookup_service")
                    if item_lookup_service:
                        break

            if not item_lookup_service:
                logging.error("ItemLookupService not available for codex name lookup")
                raise RuntimeError("ItemLookupService not available for codex name lookup")

            # Look up the actual codex item by ID
            codex_item = item_lookup_service.lookup_item_by_id(codex_item_id, "item_desc")
            if not codex_item:
                logging.error(f"Codex item ID {codex_item_id} not found in item database")
                raise RuntimeError(f"Codex item ID {codex_item_id} not found in item database")

            actual_codex_name = codex_item.get("name", "")
            if not actual_codex_name:
                logging.error(f"No name found for codex item ID {codex_item_id}")
                raise RuntimeError(f"No name found for codex item ID {codex_item_id}")

            self.cached_codex_name = actual_codex_name
            logging.debug(f"Found codex name: {actual_codex_name} (ID: {codex_item_id})")

        return self.cached_codex_name

    def _get_user_friendly_error_message(self, error_str: str) -> str:
        """
        Convert technical error messages to user-friendly messages.

        Args:
            error_str: Technical error message from exception

        Returns:
            User-friendly error message
        """
        if "No claim available for tier lookup" in error_str:
            return "Error: No claim data available. Please ensure you're connected to a claim."
        elif "ClaimsProcessor not found" in error_str:
            return "Error: Claim data not synchronized. Please wait for data to load or reconnect."
        elif "No claim tech data found for claim" in error_str:
            return "Error: Claim tech data not available. You may not have access to this claim's tech data."
        elif "ReferenceDataProcessor not found" in error_str:
            return "Error: Reference data not loaded. Please wait for data synchronization to complete."
        elif "Could not find tier" in error_str and "data" in error_str:
            return "Error: Tier data not available. This may be a new tier that hasn't been synchronized yet."
        elif "Empty or missing input array" in error_str:
            return "Error: Codex data incomplete. Reference data may be corrupted or outdated."
        elif "Invalid codex quantity" in error_str:
            return "Error: Invalid codex requirements found. Reference data may be corrupted."
        elif "No codex_window provided" in error_str:
            return "Error: Internal calculation error. Please try reopening the codex window."
        else:
            return f"Error: {error_str}"

    def _get_completed_codex_count(self, target_tier: int) -> int:
        """
        Get the number of completed codexes from claim inventory using actual item ID.

        Args:
            target_tier: Target tier to look for codex items

        Returns:
            Number of completed codex items in inventory
        """
        try:
            consolidated_inventory = self._get_cached_inventory()
            if not consolidated_inventory:
                return 0

            codex_count = 0

            try:
                # Get codex requirements to find the actual required codex ID
                codex_requirements = self._get_cached_codex_requirements()
                input_array = codex_requirements.get("input", [])

                if input_array and len(input_array) > 0 and len(input_array[0]) >= 1:
                    codex_item_id = input_array[0][0]  # Get actual codex item ID

                    # Use ItemLookupService to get the real item name
                    item_lookup_service = None
                    for processor in self.data_service.processors:
                        if hasattr(processor, "services") and processor.services:
                            item_lookup_service = processor.services.get("item_lookup_service")
                            if item_lookup_service:
                                break

                    if item_lookup_service:
                        # Look up the actual codex item by ID
                        codex_item = item_lookup_service.lookup_item_by_id(codex_item_id, "item_desc")
                        if codex_item:
                            actual_codex_name = codex_item.get("name", "")
                            if actual_codex_name:
                                # Search for the exact codex name in inventory
                                item_data = consolidated_inventory.get(actual_codex_name)
                                if item_data and isinstance(item_data, dict):
                                    codex_count = item_data.get("total_quantity", 0)
                                    logging.debug(f"Found {codex_count} {actual_codex_name} in inventory (ID: {codex_item_id})")
                                    return codex_count
                                else:
                                    logging.debug(f"Codex item {actual_codex_name} not found in inventory")
                            else:
                                logging.debug(f"No name found for codex item ID {codex_item_id}")
                        else:
                            logging.debug(f"Codex item ID {codex_item_id} not found in item lookup")
                    else:
                        logging.debug("ItemLookupService not available for codex lookup")
                else:
                    logging.debug(f"No codex input data found for tier {target_tier}")

            except Exception as e:
                logging.debug(f"Error looking up actual codex name: {e}")

            return codex_count

        except Exception as e:
            logging.error(f"Error getting completed codex count: {e}")
            return 0

    def _get_refined_product_count(self, profession: str, target_tier: int) -> int:
        """
        Get the number of refined products for a profession from inventory.

        Args:
            profession: Profession name (cloth, metal, wood, stone, leather)
            target_tier: Target tier to look for refined materials

        Returns:
            Number of refined products available in inventory
        """
        try:
            consolidated_inventory = self._get_cached_inventory()
            if not consolidated_inventory:
                return 0

            # Get the actual refined item name using recursive chain
            refined_count = 0
            actual_item_name = self._get_refined_item_name(profession, target_tier)

            # Search for exact item name in inventory
            item_data = consolidated_inventory.get(actual_item_name)
            if item_data and isinstance(item_data, dict):
                refined_count = item_data.get("total_quantity", 0)
                logging.debug(f"Found {refined_count} {actual_item_name} for {profession} (exact match)")
            else:
                logging.debug(f"Refined item {actual_item_name} not found in inventory for {profession}")

            return refined_count

        except Exception as e:
            logging.error(f"Error getting refined product count for {profession}: {e}")
            return 0

    def _init_refined_mats(self, target_tier: int):
        """
        Build and cache refined item names for all professions by only iterating codex recipe and each research recipe.
        """
        self.refined_mats = {p: None for p in self.professions}
        refined_tag_map = {
            "cloth": "Cloth",
            "stone": "Brick",
            "metal": "Ingot",
            "wood": "Plank",
            "leather": "Leather",
            "scholar": "Journal",
        }
        try:
            item_lookup_service = None
            reference_processor = None
            for processor in self.data_service.processors:
                if hasattr(processor, "services") and processor.services:
                    item_lookup_service = processor.services.get("item_lookup_service")
                if type(processor).__name__ == "ReferenceDataProcessor":
                    reference_processor = processor
                if item_lookup_service and reference_processor:
                    break
            if not item_lookup_service or not reference_processor:
                logging.error("Required services not available for refined item lookup")
                return

            crafting_recipes = reference_processor.get_reference_items("crafting_recipe_desc")
            codex_requirements = self._get_cached_codex_requirements()
            input_array = codex_requirements.get("input", [])

            # Find codex id
            codex_id = None
            for entry in input_array:
                if not isinstance(entry, list) or len(entry) < 1:
                    continue
                item_id = entry[0]
                item = item_lookup_service.lookup_item_by_id(item_id, "item_desc")
                if not item:
                    continue
                item_tag = item.get("tag", "")
                if item_tag == "Codex":
                    codex_id = item_id
                    break
            if not codex_id:
                logging.error(f"Codex not found for tier {target_tier}")
                return

            # Find codex recipe (single lookup)
            codex_recipe = None
            for recipe in crafting_recipes:
                crafted_stacks = getattr(recipe, "crafted_item_stacks", [])
                for crafted_entry in crafted_stacks:
                    if isinstance(crafted_entry, list) and len(crafted_entry) > 0 and crafted_entry[0] == codex_id:
                        codex_recipe = recipe
                        break
                if codex_recipe:
                    break
            if not codex_recipe:
                logging.error(f"No recipe found with crafted_item_stacks containing Codex ID {codex_id}")
                return

            # Build crafted_item_id -> recipe lookup for O(1) access
            crafted_id_to_recipe = {}
            for recipe in crafting_recipes:
                crafted_stacks = getattr(recipe, "crafted_item_stacks", [])
                for crafted_entry in crafted_stacks:
                    if isinstance(crafted_entry, list) and len(crafted_entry) > 0:
                        crafted_id_to_recipe[crafted_entry[0]] = recipe

            # Iterate research items in codex_recipe's consumed_item_stacks
            consumed_stacks = getattr(codex_recipe, "consumed_item_stacks", [])
            for consumed_entry in consumed_stacks:
                if not isinstance(consumed_entry, list) or len(consumed_entry) < 1:
                    continue
                research_id = consumed_entry[0]
                research_item = item_lookup_service.lookup_item_by_id(research_id, "item_desc")
                if not research_item:
                    continue
                research_tag = research_item.get("tag", "")
                # Map research tag to profession
                profession = None
                for p in self.professions:
                    expected_research_tag = f"{p.title()} Research" if p != "scholar" else "Journal"
                    if research_tag == expected_research_tag:
                        profession = p
                        break
                if not profession:
                    continue
                # Direct lookup for research recipe
                research_recipe = crafted_id_to_recipe.get(research_id)
                if not research_recipe:
                    continue
                research_inputs = getattr(research_recipe, "consumed_item_stacks", [])
                # Assign scholar's mat using the journal id from the second array in research_inputs, only once
                if self.refined_mats["scholar"] is None and len(research_inputs) > 1:
                    journal_id = research_inputs[1][0]
                    journal_item = item_lookup_service.lookup_item_by_id(journal_id, "item_desc")
                    if journal_item:
                        journal_name = journal_item.get("name", "")
                        journal_tag = journal_item.get("tag", "")
                        if journal_tag == refined_tag_map["scholar"]:
                            self.refined_mats["scholar"] = journal_name
                # Assign other professions using the first item of each array
                for input_item in research_inputs:
                    if not isinstance(input_item, list) or len(input_item) < 1:
                        continue
                    refined_id = input_item[0]
                    refined_item = item_lookup_service.lookup_item_by_id(refined_id, "item_desc")
                    if not refined_item:
                        continue
                    refined_name = refined_item.get("name", "")
                    refined_tag = refined_item.get("tag", "")
                    expected_refined_tag = refined_tag_map.get(profession, f"Refined {profession.title()}")
                    if refined_tag == f"Refined {expected_refined_tag}":
                        self.refined_mats[profession] = refined_name
                        break
        except Exception as e:
            logging.error(f"Error initializing refined mats: {e}")

    def _get_refined_item_name(self, profession: str, target_tier: int) -> str:
        """
        Return the cached refined item name for the profession and tier, initializing if needed.
        """
        if not hasattr(self, "refined_mats") or not self.refined_mats:
            self._init_refined_mats(target_tier)
        name = self.refined_mats.get(profession)
        if name:
            return name
        # No fallback - return empty string to expose issues
        logging.error(f"No refined item name found for {profession} T{target_tier} - check template generation")
        return ""

    def _show_error(self, message):
        """Show an error message in the window."""
        # Clear all profession tabs and show error
        for profession in self.professions:
            tab = self.profession_tabs[profession]
            tab.materials_tree.delete(*tab.materials_tree.get_children())
            tab.materials_tree.insert("", "end", values=(message, "", "", "", ""))

        # Reset progress labels
        for profession in self.professions:
            self.profession_progress_labels[profession].configure(text="0/0 (0%)")

        logging.error(f"Enhanced CodexWindow error: {message}")

    def _create_loading_overlay(self):
        """Create loading overlay with loading image."""
        # Create overlay frame that covers the entire window
        self.loading_overlay = ctk.CTkFrame(self, fg_color=get_color("BACKGROUND_PRIMARY"), corner_radius=0)

        # Create loading content frame
        loading_content = ctk.CTkFrame(self.loading_overlay, fg_color="transparent")
        loading_content.pack(expand=True, fill="both")
        loading_content.grid_columnconfigure(0, weight=1)
        loading_content.grid_rowconfigure(0, weight=1)

        # Center container for loading image and text
        center_frame = ctk.CTkFrame(loading_content, fg_color="transparent")
        center_frame.grid(row=0, column=0, sticky="")

        try:
            # Load and display loading image
            from pathlib import Path
            import os

            loading_image_path = Path(__file__).parent.parent / "images" / "loading.png"
            logging.info(f"Attempting to load loading image from: {loading_image_path}")
            logging.info(f"Image path exists: {loading_image_path.exists()}")
            logging.info(f"Absolute path: {loading_image_path.resolve()}")

            if loading_image_path.exists():
                # Test image loading
                img = Image.open(loading_image_path)
                logging.info(f"Successfully loaded image: {img.size}, mode: {img.mode}")

                loading_image = ctk.CTkImage(light_image=img, dark_image=img, size=(192, 192))

                self.loading_image_label = ctk.CTkLabel(center_frame, image=loading_image, text="")
                self.loading_image_label.pack(pady=(0, 20))

                # Keep a reference to prevent garbage collection
                self._loading_image_ref = loading_image

                logging.info("Loading image displayed successfully")
            else:
                logging.warning(f"Loading image not found: {loading_image_path}")

                # Fallback: show text-based loading indicator
                self.loading_image_label = ctk.CTkLabel(
                    center_frame,
                    text="⟳",  # Unicode loading symbol
                    font=ctk.CTkFont(size=48),
                    text_color=get_color("TEXT_ACCENT"),
                )
                self.loading_image_label.pack(pady=(0, 20))

        except Exception as e:
            logging.error(f"Error loading loading image: {e}")

            # Fallback: show text-based loading indicator
            self.loading_image_label = ctk.CTkLabel(
                center_frame, text="⟳", font=ctk.CTkFont(size=48), text_color=get_color("TEXT_ACCENT")  # Unicode loading symbol
            )
            self.loading_image_label.pack(pady=(0, 20))

        # Loading text
        loading_text = ctk.CTkLabel(
            center_frame,
            text="Loading Codex Data...",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=get_color("TEXT_PRIMARY"),
        )
        loading_text.pack(pady=(0, 10))

        # Sub-text
        loading_subtext = ctk.CTkLabel(
            center_frame,
            text="Calculating material requirements for all professions",
            font=ctk.CTkFont(size=12),
            text_color=get_color("TEXT_SECONDARY"),
        )
        loading_subtext.pack()

        # Initially hidden
        self.loading_overlay_visible = False

    def _show_loading_overlay(self):
        """Show the loading overlay."""
        if not self.loading_overlay_visible:
            self.loading_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.loading_overlay.tkraise()
            self.loading_overlay_visible = True

    def _hide_loading_overlay(self):
        """Hide the loading overlay."""
        if self.loading_overlay_visible:
            self.loading_overlay.place_forget()
            self.loading_overlay_visible = False

    def _setup_search_after_data_load(self):
        """Set up search functionality after data is loaded."""
        try:
            # Check if search is already set up to prevent duplicate initialization
            if hasattr(self, 'search_bar') and self.search_bar:
                return
                
            # Configure search frame like main window
            self.search_frame.grid_columnconfigure(0, weight=1)

            # Set up search functionality with profession-specific window ID
            self._setup_search(
                self.search_frame,
                placeholder_text=self._get_profession_search_placeholder(),
                show_save_load=True,
                show_clear=True,
                window_id=self._get_current_profession_window_id(),  # Use profession-specific ID
            )

            # Register all profession tabs with search state manager
            if hasattr(self, "search_state_manager"):
                for profession in self.professions:
                    profession_window_id = f"codex_{profession}"
                    self.search_state_manager.register_window(profession_window_id)

            # Pack the search bar component like main window
            if hasattr(self, "search_bar"):
                self.search_bar.pack(fill="x")

            logging.info("Search functionality initialized successfully")
        except Exception as e:
            logging.error(f"Error setting up search: {e}")

    def _get_current_profession_window_id(self) -> str:
        """Get window ID for current active profession."""
        if self.active_profession:
            return f"codex_{self.active_profession}"
        return "codex_cloth"  # Default to cloth tab during initialization

    def _get_profession_search_placeholder(self) -> str:
        """Get profession-specific search placeholder text."""
        if self.active_profession:
            display_name = self.profession_display_names.get(self.active_profession, self.active_profession.title())
            return f"Search {display_name} materials... (e.g., material=stone tier>3 need<100)"
        return "Search materials... (e.g., material=stone tier>3 need<100)"

    def _switch_search_context(self, new_profession: str):
        """Switch search context to a new profession, preserving per-tab search state."""
        if not hasattr(self, "search_bar") or not hasattr(self, "search_state_manager"):
            return

        try:
            # Save current search state for the old profession
            if self.active_profession:
                old_window_id = f"codex_{self.active_profession}"
                current_search = self.search_bar.get_search_text()
                self.search_state_manager.save_search_state(old_window_id, current_search)

            # Update active profession
            self.active_profession = new_profession

            # Switch to new profession's search context
            new_window_id = f"codex_{new_profession}"
            self.window_id = new_window_id

            # Restore search state for new profession
            saved_search = self.search_state_manager.restore_search_state(new_window_id)
            if saved_search:
                self.search_bar.set_search_text(saved_search)
            else:
                self.search_bar.clear_search()

            # Update placeholder text
            self.search_bar.set_placeholder_text(self._get_profession_search_placeholder())

            # Trigger search update
            self._apply_search_filter()

            logging.debug(f"Switched search context to {new_profession} (ID: {new_window_id})")

        except Exception as e:
            logging.error(f"Error switching search context to {new_profession}: {e}")

    def update_data(self, inventory_data):
        """
        Handle live inventory updates - recalculate requirements when inventory changes.

        Args:
            inventory_data: New inventory data (dict or any data structure)
        """
        try:
            # Only update if we have loaded data and a codex service
            if not hasattr(self, "data_service") or not self.data_service:
                return

            if not hasattr(self.data_service, "codex_service") or not self.data_service.codex_service:
                return

            # Only update if we have requirements data loaded
            if not hasattr(self, "all_requirements") or not self.all_requirements:
                return

            # Invalidate codex service caches since inventory changed
            self.data_service.codex_service.invalidate_cache()

            # Debounce updates to avoid excessive recalculation
            if hasattr(self, "_update_timer"):
                self.after_cancel(self._update_timer)

            # Schedule update after short delay
            self._update_timer = self.after(500, self._perform_live_update)

            logging.debug("Scheduled live codex update due to inventory change")

        except Exception as e:
            logging.error(f"Error in codex live update: {e}")

    def _perform_live_update(self):
        """Perform the actual live update of requirements."""
        try:
            # Clear the update timer
            if hasattr(self, "_update_timer"):
                del self._update_timer

            # Recalculate requirements with fresh inventory data
            codex_service = self.data_service.codex_service
            updated_requirements = codex_service.calculate_tier_requirements()

            # Update UI with new requirements
            self.all_requirements = updated_requirements

            # Update each profession tab with new data
            for profession, materials in updated_requirements.items():
                if profession in self.profession_tabs:
                    self.profession_tabs[profession].update_materials(materials)

            # Update progress summary
            self._update_progress_summary()

            # Reapply current search filter
            if hasattr(self, "search_bar"):
                self._apply_search_filter()

            logging.debug("Completed live codex update")

        except Exception as e:
            logging.error(f"Error performing live codex update: {e}")

    # SearchableWindowMixin implementation
    def _get_searchable_data(self) -> List[Dict[str, Any]]:
        """
        Return all material data across all professions for search filtering.

        Returns:
            List of dictionaries representing searchable materials
        """
        searchable_materials = []

        # Check if we have requirements data
        if not hasattr(self, "all_requirements") or not self.all_requirements:
            return searchable_materials

        try:
            for profession, materials in self.all_requirements.items():
                if not isinstance(materials, dict):
                    continue

                for material_name, material_info in materials.items():
                    if not isinstance(material_info, dict):
                        continue

                    searchable_material = {
                        "material": material_name,
                        "name": material_name,  # Alias for material
                        "profession": profession,
                        "tier": material_info.get("tier", 0),
                        "need": material_info.get("need", 0),
                        "supply": material_info.get("supply", 0),
                        "progress": material_info.get("progress", 0),
                    }
                    searchable_materials.append(searchable_material)
        except Exception as e:
            logging.error(f"Error preparing searchable data: {e}")

        return searchable_materials

    def _update_ui_with_filtered_data(self, filtered_data: List[Dict[str, Any]]):
        """
        Update the UI to show only materials that match the search filter.

        Args:
            filtered_data: List of materials that match the search query
        """
        try:
            # Group filtered data by profession
            profession_materials = {}
            for material_data in filtered_data:
                profession = material_data["profession"]
                if profession not in profession_materials:
                    profession_materials[profession] = {}

                material_name = material_data["material"]
                profession_materials[profession][material_name] = {
                    "tier": material_data["tier"],
                    "need": material_data["need"],
                    "supply": material_data["supply"],
                    "progress": material_data["progress"],
                }

            # Get current search text from the search bar
            current_search_text = ""
            if hasattr(self, "search_bar"):
                current_search_text = self.search_bar.get_search_text()

            # Update each profession tab with filtered data (preserves sorting)
            for profession in self.professions:
                if profession in profession_materials:
                    # Update with filtered data - sorting will be preserved
                    self.profession_tabs[profession].update_materials(profession_materials[profession])
                else:
                    # No matching materials for this profession
                    if current_search_text:
                        # Show "no results" message if there's an active search
                        tab = self.profession_tabs[profession]
                        tab.materials_data = {}  # Clear data
                        tab.materials_tree.delete(*tab.materials_tree.get_children())
                        display_name = self.profession_display_names.get(profession, profession.title())
                        tab.materials_tree.insert(
                            "", "end", values=(f"No materials match search for {display_name}", "", "", "", "")
                        )
                    else:
                        # Show all materials if no search - sorting will be preserved
                        original_materials = self.all_requirements.get(profession, {})
                        self.profession_tabs[profession].update_materials(original_materials)

            # Update progress summary - always use total materials for accurate progress
            self._update_search_progress_summary(profession_materials)

        except Exception as e:
            logging.error(f"Error updating UI with filtered data: {e}")

    def _update_search_progress_summary(self, profession_materials: Dict[str, Dict]):
        """
        Update progress summary - ALWAYS use total materials for progress calculation.
        Progress percentages should reflect actual completion, not search filter results.

        Args:
            profession_materials: Filtered materials grouped by profession (for display only)
        """
        # IMPORTANT: Always use all_requirements for progress calculation
        # Progress should reflect actual completion status, not search filters
        for profession in self.professions:
            completed = 0
            total = 0

            # Always use total materials for progress calculation
            if profession in self.all_requirements:
                materials = self.all_requirements[profession]
                total = len(materials)
                if materials:
                    completed = sum(1 for mat in materials.values() if mat.get("progress", 0) >= 1.0)

            # Calculate percentage based on total materials, not filtered ones
            percentage = int((completed / total * 100)) if total > 0 else 0

            # Update label with x/y (%) format - this reflects TRUE progress
            self.profession_progress_labels[profession].configure(text=f"{completed}/{total} ({percentage}%)")

    def clear_for_claim_switch(self):
        """Clear codex window data during claim switching."""
        try:
            # Clear all profession tabs
            for profession in self.professions:
                tab = self.profession_tabs[profession]
                tab.materials_data = {}
                tab.materials_tree.delete(*tab.materials_tree.get_children())
                display_name = self.profession_display_names.get(profession, profession.title())
                tab.materials_tree.insert("", "end", values=(f"Switching claims...", "", "", "", ""))
                
            # Clear progress labels
            for profession in self.professions:
                self.profession_progress_labels[profession].configure(text="0/0 (0%)")
            
            # Clear cached data
            self.all_requirements = {}
            self.cached_inventory = None
            self.last_inventory_check = 0
            
            logging.info("Codex window cleared for claim switch")
            
        except Exception as e:
            logging.error(f"Error clearing codex window for claim switch: {e}")

    def handle_claim_switch_complete(self, claim_id: str, claim_name: str):
        """Handle successful claim switch completion."""
        try:
            # Invalidate codex service caches
            if hasattr(self.data_service, 'codex_service'):
                self.data_service.codex_service.invalidate_cache()
                
            # Clear cascading calculator cache
            if hasattr(self.data_service.codex_service, '_cascading_calculator'):
                self.data_service.codex_service._cascading_calculator.clear_cache()
                
            logging.info(f"Codex caches invalidated for claim switch to {claim_name}")
            
            # Force recalculation with new claim data
            self._recalculate_all_requirements()
            
        except Exception as e:
            logging.error(f"Error handling claim switch in codex window: {e}")

    def _recalculate_all_requirements(self):
        """Force complete recalculation of codex requirements."""
        try:
            # Clear all cached data
            self.all_requirements = {}
            self.cached_inventory = None
            self.last_inventory_check = 0
            
            # Initialize retry counter
            self._recalc_retry_count = 0
            
            # Schedule recalculation after a short delay to let services stabilize
            self.after(500, self._delayed_recalculation)
            
            logging.info("Scheduled codex requirements recalculation after claim switch")
            
        except Exception as e:
            logging.error(f"Error scheduling codex requirements recalculation: {e}")

    def _delayed_recalculation(self):
        """Perform the actual recalculation after services have stabilized."""
        try:
            # Limit retry attempts to prevent infinite loops
            if not hasattr(self, '_recalc_retry_count'):
                self._recalc_retry_count = 0
                
            if self._recalc_retry_count >= 5:
                logging.warning("Max retry attempts reached for codex recalculation, proceeding anyway")
                self._start_data_loading()
                return
            
            # Check if we have the required services
            if not hasattr(self.data_service, 'codex_service') or not self.data_service.codex_service:
                logging.warning(f"CodexService not available for recalculation, retrying in 1s (attempt {self._recalc_retry_count + 1}/5)")
                self._recalc_retry_count += 1
                self.after(1000, self._delayed_recalculation)
                return
            
            # All services ready, start data loading
            self._start_data_loading()
            
            logging.info("Codex requirements recalculation started")
            
        except Exception as e:
            logging.error(f"Error in delayed codex recalculation: {e}")
            # If still failing, just clear the tabs to avoid hanging
            for profession in self.professions:
                tab = self.profession_tabs[profession]
                tab.materials_data = {}
                tab.materials_tree.delete(*tab.materials_tree.get_children())
                display_name = self.profession_display_names.get(profession, profession.title())
                tab.materials_tree.insert("", "end", values=(f"Error loading {display_name} data", "", "", "", ""))

    def clear_for_claim_switch(self):
        """Clear codex window data during claim switch."""
        try:
            logging.info("Clearing codex window for claim switch")
            
            # Clear all tab data
            for profession in self.professions:
                tab = self.profession_tabs[profession]
                tab.materials_data = {}
                tab.materials_tree.delete(*tab.materials_tree.get_children())
                tab.materials_tree.insert("", "end", values=("Switching claims...", "", "", "", ""))
            
            # Clear cached data
            self.all_requirements = {}
            self.cached_codex_requirements = None
            self.cached_codex_quantity = None
            self.cached_codex_name = None
            self.cached_inventory = None
            self.cached_inventory_time = 0
            
        except Exception as e:
            logging.error(f"Error clearing codex window for claim switch: {e}")

    def handle_claim_switch_complete(self, claim_id, claim_name):
        """Handle completion of claim switch."""
        try:
            logging.info(f"Codex window handling claim switch completion to {claim_name} (ID: {claim_id})")
            
            # Initialize retry counter
            self._recalc_retry_count = 0
            
            # Schedule recalculation after brief delay for services to stabilize
            self.after(500, self._delayed_recalculation)
            
        except Exception as e:
            logging.error(f"Error handling claim switch completion in codex window: {e}")

