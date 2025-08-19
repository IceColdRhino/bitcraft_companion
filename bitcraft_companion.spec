# -*- mode: python ; coding: utf-8 -*-

import os
import time
import re
from pathlib import Path

# Get the project directory
project_dir = Path(os.getcwd())

# Read version from pyproject.toml using regex
try:
    with open(project_dir / 'pyproject.toml', 'r') as f:
        content = f.read()
    version_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
    VERSION = version_match.group(1) if version_match else "0.0.0"
except Exception as e:
    print(f"Warning: Could not read version from pyproject.toml: {e}")
    VERSION = "0.0.0"

BUILD_DATE = time.strftime("%Y%m%d")

# Generate versioned executable name (without date)
versioned_name = f'BitCraft_Companion-v{VERSION}'

print(f"Building BitCraft Companion v{VERSION} ({BUILD_DATE})")

a = Analysis(
    ['app/main.py'],  # Entry point
    pathex=[str(project_dir / 'app')],  # Add app directory to Python path
    binaries=[],
    datas=[
        # Include images folder for loading overlays and other UI assets
        ('app/ui/images', 'app/ui/images'),
    ],
    hiddenimports=[
        # CustomTkinter and its dependencies
        'customtkinter',
        'tkinter',
        'tkinter.ttk',
        'PIL',
        'PIL._tkinter_finder',
        # WebSocket dependencies
        'websockets',
        'websockets.sync',
        'websockets.sync.client',
        # Other dependencies
        'keyring',
        'keyring.backends',
        'keyring.backends.Windows',
        'requests',
        'json',
        'threading',
        'logging',
        'datetime',
        'enum',
        'dotenv',
        're',
        'os',
        'abc',
        'typing',
        
        # Core modules 
        'app.core.data_service',
        'app.core.message_router', 
        'app.core.data_paths',
        
        # Processors 
        'app.core.processors.base_processor',
        'app.core.processors.inventory_processor',
        'app.core.processors.crafting_processor',
        'app.core.processors.active_crafting_processor',
        'app.core.processors.tasks_processor',
        'app.core.processors.claims_processor',
        'app.core.processors.reference_data_processor',
        
        # Core Utils
        'app.core.utils.item_lookup_service',
        
        # Services 
        'app.services.inventory_service',
        'app.services.passive_crafting_service',
        'app.services.active_crafting_service',
        'app.services.traveler_tasks_service',
        'app.services.claim_service',
        'app.services.claim_members_service',
        'app.services.notification_service',
        
        # UI Components 
        'app.ui.main_window',
        'app.ui.components.claim_info_header',
        'app.ui.components.filter_popup',
        'app.ui.components.export_utils',
        'app.ui.components.settings_window',
        'app.ui.components.notification_window',
        'app.ui.components.loading_overlay',
        'app.ui.styles.treeview_styles',
        'app.ui.tabs.claim_inventory_tab',
        'app.ui.tabs.passive_crafting_tab', 
        'app.ui.tabs.active_crafting_tab',
        'app.ui.tabs.traveler_tasks_tab',
        
        # Client 
        'app.client.bitcraft_client',
        'app.client.query_service',
        
        # Models 
        'app.models.player',
        'app.models.claim',
        'app.models.claim_member',
        'app.models.object_dataclasses',
        
        # Additional dependencies 
        'openpyxl',
        'openpyxl.styles',
        'openpyxl.utils',
        'openpyxl.workbook',
        'openpyxl.worksheet',
        'sqlite3',
        'pathlib',
        'shutil',
        'queue',
        'time',
        'sys',
        'uuid',
        'tkinter.filedialog',
        'tkinter.messagebox',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary packages to reduce size
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'IPython',
        'jupyter',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=versioned_name,  # Versioned name of the executable
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Compress with UPX if available
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True if you want a console window for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add path to .ico file if you have an icon
    version_file='version_info.txt',  # Add version file for Windows properties
)
