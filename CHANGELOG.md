# Changelog
All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.36]
### Added
- Added Codex!
- Implement claim switch handling in CodexWindow and MainWindow for improved user experience
- Enhance cascading inventory calculations with tier-based filtering and consolidated inventory support
- Enhance search functionality with text change detection to optimize filtering in crafting tabs
- Update refined status display and implement codex name retrieval for improved clarity
- Implement caching for codex requirements and inventory to optimize performance and reduce redundant calls
- Enhance CodexProfessionTab with bold tags for completed and incomplete materials based on direct dependency status
- Update version to 0.2.35 and enhance data inclusion in bitcraft_companion.spec

### Refactored
- Simplify comments for claim service updates and improve shutdown process in main window
- Improve code consistency and readability in test_saved_search_service.py
- Clean up code formatting and improve readability in CodexService
- Simplify CodexService documentation and improve inventory hash generation logic

## [0.2.34]
### Added
- New custom sounds for notifications (credit to Blizzard for job's done sound from Warcraft II).
- Silent notifications.
- Test each notification type.
- Enhanced notification settings with sound customization.
  - Refactored SettingsWindow to include sound options for notifications.
  - Added methods to handle sound selection and testing for passive crafts, active crafts, and stamina recharged notifications.
  - Integrated notification service to fetch available sound options and display names.
  - Updated settings loading and saving to support new sound settings.
  - Added new sound files: `jobs_done.mp3`, `notification.wav`, `piano.wav`, `confirmation.wav`, and `mystic_chimes.wav`.
  - Updated application specification to include sounds directory and pygame dependency.

## [0.2.33]
### Added
- **Stamina Processing and Notifications**: Implemented comprehensive stamina tracking system.
  - Tracks stamina across active, resting, and idle statuses for all relevant entities.
  - Real-time updates and display of current stamina state in the UI.
  - Notifications for full stamina.

## [0.2.32]
### Added
- Enhance search parser to support multi-value OR/AND operations for more flexible filtering
- Update logging level in inventory tabs for improved diagnostics

### Improved
- Performance and optimization in inventory and crafting tabs

## [0.2.31]
### Added
- Improved theme engine with several options

### Fixed
- Inaccurate supply depletion values

## [0.2.30]
### Added
- Implemented ReferenceCacheService for local caching of reference data.
- Methods for caching, retrieving, validating, and clearing reference data with version tracking and TTL.
- MainWindow caching optimizations, including cached button styles and keyword examples for improved UI responsiveness.
- Background processing for filtering and sorting in ClaimInventoryTab to efficiently handle large datasets.
- Callbacks for background task completion and error handling to ensure a smooth user experience.

## [0.2.28]
### Added
- Improved save and load for searches
- Comprehensive tests for SavedSearchService

### Fixed
- Item overwrites due to conflicting IDs (for real this time!)

### Refactored
- Simplified reference data handling in InventoryProcessor
- Removed unused item type determination methods
- Simplified reference data handling in InventoryProcessor

## [0.2.27]
### Added
- **Enhanced Search with Keywords & Comparison Operators**: Revolutionary search system with keyword-based filtering across all tabs
  - **Keywords**: `item=`, `tier=`, `quantity=`/`qty=`, `tag=`, `container=`, `building=`, `crafter=`, `traveler=`, `status=`
  - **Comparison Operators**: `=`, `>`, `<`, `>=`, `<=`, `!=` for both string and numeric fields
  - **Multiple Conditions**: Support multiple conditions per field with AND logic (e.g., `item=log item!=package qty<500`)
  - **Examples**: `item=plank tier>3 qty<100`, `container=carving`, `building!=workshop`, `tier>2 tier<6`
  - **Smart Field Detection**: Automatically handles numeric vs string comparisons
  - **Backward Compatible**: Regular search terms still work alongside keywords
  - **Tab-Specific Placeholders**: Contextual search examples for each tab
  - **Container Search**: Special handling for searching within container dictionaries
  - **Traveler Tasks**: Enhanced nested search showing parent travelers when child operations match

## [0.2.26]
### Added
- QoL: Escape key keybind to clear search text

## [0.2.25]
### Fixed
- Enhance inventory processing with preferred item source resolution to prevent inventory overwrites

## [0.2.23]
### Added
- Theme-aware styling and centralized theme management via ThemeManager
- Dynamic theme support in MainWindow, ClaimInfoHeader, FilterPopup, and SettingsWindow
- Improved search bar functionality (supports ctrl+delete and ctrl+backspace)
- Refactored TreeviewStyles for consistent dynamic colors
- Activity logging service with inventory change tracking, player attribution, timestamps, color indicators, and background log rotation
- ActivityWindow for viewing recent inventory changes, with dynamic search placeholder and quick access button in ClaimInfoHeader

### Changed
- Consistent window title in ActivityWindow

## [0.2.22]
### Added
- Implement comprehensive data refresh and retry mechanism for task updates
- Add PassiveCraftingTab and refactor TravelerTasksTab for consistent styling
- Implement notification bundling for passive crafting notifications
- Add `timestamp_micros` property to PassiveCraftState for enhanced timestamp handling

### Changed
- Moved reference queries to their own function for improved performance and compartmentalization
- Reorganize import statements for improved clarity and consistency
- Clean up imports and enhance code organization in UI components
- Update class docstring format in ClaimService for consistency
- Remove redundant import statements and enhance data loading in processors

### Removed
- Remove obsolete database file from the project

## [0.2.21]
### Changed
- Refactored service instantiation patches and adjusted user ID assignment for refactored architecture 
- Updated logging configuration to use INFO level and consistent log file name 
- Simplified tile cost data initialization in ClaimInfoHeader and removed loading method 
- Removed ClaimMember and Player classes 
- Removed TravelerTasksService class and its associated methods for handling traveler tasks data processing and real-time updates 

### Added
- Enhanced DataService and MessageRouter with improved logging and validation features 
- Enhanced ItemLookupService to support building and recipe lookups 
- Refactored processors to utilize dataclasses for improved data handling 
- Added additional one-time subscription queries to QueryService 

### Fixed
- Improved logging messages for WebSocket and keyring operations 

## [0.2.20]
### Added
* Comprehensive tests for UI tab sorting logic
* Player state transaction processing and subscription context handling for traveler task
* Update login failure message to provide clearer instructions for users
* Update subscription queries to include traveler task timers for improved data retrieval

### Improved
* Player state update handling with source tracking and initial subscription logic
* Enhance task refresh timer logic for improved state handling and user feedback
* Improve column sorting. Now mixed value columns sort logically
* Refactor item lookup logic to use shared item lookup service across processors
* Refactor task refresh expiration logic for improved logging and state management
* Improve traveler task timer reliability at start up
* Fixed child jobs breaking into sub-jobs in the passive crafting tab

### Fixed 
* Traveler task timer showing incorrect timer at launch when tasks refresh while Companion is closed

## [0.2.18] 
### Improved
* Traveler tasks expiration handling with proper None initialization and countdown logic

### Fixed
* Traveler tasks no longer writing to real player_data.json during tests by implementing proper path mocking
* Traveler tasks show correct time at launch

### Technical
* Better separation of test and production environments

## [0.2.17]
### Changed
* Removed redundant test job from CI workflow for improved efficiency
* Enhanced CI workflows with better dependency installation and testing processes

## [0.2.16]
### Added
* Comprehensive tests and GitHub Actions CI/CD pipeline for automated testing
* Enhanced WebSocket connection handling with comprehensive diagnostics and retry logic
* Current active crafting data storage for improved progress tracking in ActiveCraftingProcessor
* Enhanced logging across various components for improved traceability and debugging

### Improved
* WebSocket connection stability with retry mechanisms and Python version-specific handling
* Crafting notifications to only alert for passive crafts belonging to the current player
* Data handling by removing redundant subscription query methods from various services
* Progress tracking by streamlining processor management and removing redundant logic
* Python version requirement updated to >=3.10 for better compatibility

### Removed
* ClaimMembersService class and associated caching logic for simplified architecture
* Redundant progress tracking logic from DataService
* Redundant subscription query methods from various services

### Technical
* Enhanced WebSocket diagnostics with connection testing and error handling
* Improved error logging and debugging capabilities
* Streamlined data processing architecture
* Better separation of concerns in service layer

## [0.2.14]
### Added
* Comprehensive test suite for data processing, export functionality, timers, UI components, and error handling
* Enhanced WebSocket message logging with detailed transaction updates
* Smart item lookup functionality with compound keys to prevent ID collisions
* Preferred source handling for item lookup operations

### Improved
* Message routing system with enhanced logging for transaction updates and processor cache clearing
* Task transaction processing with better insert/delete handling and validation
* Inventory item lookup using compound keys to handle ID collisions across different data sources
* MainWindow logging for better debugging of message processing
* Item lookup functionality with compound keys and intelligent source selection

### Technical
* Implemented compound key system for reliable item identification
* Enhanced processor cache clearing mechanisms
* Improved transaction update handling throughout the application
* Better error handling and validation in task processing

## [0.2.13]
### Changed
* Omit banks from inventory tab

## [0.2.12]
### Added
* Settings persistence in player_data.json with robust error handling
* Enhanced notification settings structure for better organization

### Improved
* Crafting processors notification handling and item tracking
* Active crafting notifications with better bundling and timing
* Settings loading and saving with proper fallback mechanisms
* Error handling throughout settings management system

## [0.2.11]
### Fixed
* Notification timing. Now they trigger when the tasks is READY not when you claim the item.
* Notifications now bundle items to prevent notification spam for each item.

## [0.2.10]
### Added
* Settings menu
* Notifications
* Move export and refresh claim to settings

## [0.2.9]
### Fixed
* Traveler tasks no longer clear at login

### Improved
* Progress tracking in Active Tasks converted to Remaining Effort. The value counts down until craft is completed.

## [0.2.7]
### Patch
* When exporting claim inventory, break out containers into their own rows for improved processing

## [0.2.6]
### Fixed
* Build path references
* Traveler task timeout reset failure

## [0.2.5]
### Improvements
* Vastly improved network performance
* Vastly improved data loading
* Vastly improved claim switching performance
* Data presentation in passive and active crafting tabs

### Added
* Real time countdowns for passive crafting
* Real time countdown for traveler task resets
* Logout and Quit buttons in main window
* Accept help value in active crafting
* Claim supply depletion value

### Fixed
* Re-added data export
* Scrollbar colors now use the correct color when disabled

## [0.1.11]
### Fixed
- Resolved issue where certain items were not appearing in the claim inventory

### Refactored
- Migrated reference data storage from JSON files to a database for improved performance and scalability

### Known Issues
- Inventory overlay reappears unexpectedly after being closed when processing the inventory list
- Updated overlays automatically move to the foreground

## [0.1.10]
### Added
- **Missing Regions**: Added support for additional regions to improve compatibility and coverage.

## [0.1.9]
### Fix
- **WebSocket Optimization**: Switched from `Subscribe` to `OneOffQuery` to prevent multiple simultaneous WebSocket connections 
and reduce resource usage.
- **Overlay Update Reliability**: Fixed an issue where overlays were not updating properly, ensuring inventory and passive crafting overlays now refresh as expected.
- **Overlay Table In-Place Updates**: Fixed overlay tables so they now update in place without requiring a full redraw, eliminating flickering and ensuring smoother refreshes.


### Change
- **Reduced Overlay Refresh Intervals**: Lowered the refresh intervals for inventory and passive crafting overlays for more 
- **Status Bar Consistency**: Standardized the display of "Last Update" datetimes across all status bars for a uniform user experience.

### Add
- **Tooltip for Auto Refresh Toggle**: Added informative tooltip to the auto refresh toggle for improved user guidance.

## [0.1.7]
### Added
- **Passive Crafting Timers**
- **Unified UI**

### Removed
- **Cleaned up unused imports**

## [0.1.6]

### Added
- **Expandable Rows (Phase 2: Advanced Features)**
  - Immediate dropdown arrows for expandable items
  - Tree structure support with proper hierarchical display
  
- **Inventory Window Enhancements**
  - Items with multiple containers now expand to show individual container quantities
  - Container names properly aligned in the Containers column
  - Single container items display actual container name instead of "1×📦"
  
- **Passive Crafting Window Enhancements**
  - Items with multiple refineries expand to show individual refinery quantities
  - Per-refinery quantity tracking (child row quantities add up to parent total)
  - Support for multiple crafters when applicable
  - Enhanced data structure for accurate refinery-specific information

- **Visual Design Improvements**
  - Lighter background (#3a3a3a) for child rows to distinguish from parent rows
  - Clean appearance with no bullet points in expanded rows
  - Left-aligned container names for better readability
  - Consistent tag-based styling across both windows

### Technical Improvements
- **Immediate Child Population**: Child rows are populated immediately when tree is created
- **Efficient Data Structure**: Per-refinery quantity tracking in the service layer
- **Robust Expand/Collapse**: Simple show/hide logic without complex dummy child management
- **Enhanced Service Layer**: Modified `passive_crafting_service.py` to include detailed refinery information

## [0.1.5]

- **Wiki Integration**
  - Right-click context menu on inventory and passive crafting items
  - "Go to Wiki" option that opens the BitCraft wiki (https://bitcraft.wiki.gg) page for the selected item
  - Automatic URL formatting for wiki links (e.g., "Rough Tree Bark" → "Rough_Tree_Bark")

## [0.1.4]

### Added
- **Real-time Search Functionality**
  - Added comprehensive search bars to both inventory and passive crafting windows
  - Real-time filtering across item names and tags as you type
  - Clear search button for easy reset functionality
  - Search persists across data refreshes while maintaining user context


- **Passive Crafting Monitor**
  - Complete passive crafting status window with real-time updates
  - Recipe tracking and progress monitoring
  - Search functionality for crafting operations
  - Always on top window option for gameplay convenience

- **Data Export Features**
  - Save inventory data to CSV, JSON, or text formats
  - Comprehensive export with metadata and timestamps
  - Multiple file format support for different use cases

- **Enhanced User Interface**
  - Optimized spacing and padding throughout the interface
  - Always on top window toggle for better gameplay integration
  - Improved responsive design with proper grid weight configuration
  - Status indicators with data freshness timestamps

### Fixed
- **Critical Bug Fixes**
  - Fixed "Unknown Item" display issue in passive crafting window
  - Resolved reference data loading problems causing missing item names
  - Fixed grid row configuration issues causing layout problems
  - Corrected import statements and syntax errors in passive crafting module

- **UI/UX Improvements**
  - Fixed excessive spacing in search and filter areas
  - Improved timestamp management to preserve data freshness indicators
  - Enhanced error handling and logging for search operations
  - Optimized grid layouts for better responsiveness

### Changed
- **Enhanced Documentation**
  - Updated README.md with comprehensive feature descriptions
  - Added detailed usage instructions for new search functionality
  - Documented installation options for both executable and source
  - Added troubleshooting section for Windows security scanning

- **Code Quality Improvements**
  - Refactored `apply_filters_and_sort()` method for better search integration
  - Enhanced reference data loading mechanisms
  - Improved error handling throughout the application
  - Better separation of concerns in window management


### Known Issues
- **Windows Security Scanning**
  - PyInstaller executables may trigger Windows Defender scanning
  - This is normal behavior for compiled Python applications
  - Solutions: Add exclusions to Windows Defender or run from source during development

- **Performance Considerations**
  - Large inventories may take longer to load and filter
  - Search operations are optimized for real-time filtering
  - Auto-refresh can be disabled for better performance on slower systems

---

## Future Roadmap

### Planned Features
  - Desktop notifications for completed crafting
  - Low inventory alerts
  - Travelers' task monitoring 
  - Claim supplies 

