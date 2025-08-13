#!/usr/bin/env python3
"""
Script to generate Windows version info file from pyproject.toml
"""

import re
from pathlib import Path


def generate_version_file():
    try:
        with open("pyproject.toml", "r") as f:
            content = f.read()

        # Extract version using regex
        version_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
        version = version_match.group(1) if version_match else "0.0.0"

        # Extract name
        name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
        name = name_match.group(1) if name_match else "app"

        # Extract description
        desc_match = re.search(r'description\s*=\s*["\']([^"\']*)["\']', content)
        description = desc_match.group(1) if desc_match and desc_match.group(1) else "BitCraft Companion"

    except Exception as e:
        print(f"Error reading pyproject.toml: {e}")
        version = "0.0.0"
        name = "app"
        description = "BitCraft Companion"

    # Parse version for Windows format (must be 4 numbers)
    version_parts = version.split(".")
    while len(version_parts) < 4:
        version_parts.append("0")
    version_tuple = tuple(int(part) for part in version_parts[:4])

    version_info_content = f"""# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
    # filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
    # Set not needed items to zero 0. Must be set as a tuple, not a list
    filevers={version_tuple},
    prodvers={version_tuple},
    # Contains a bitmask that specifies the valid bits 'flags'r
    mask=0x3f,
    # Contains a bitmask that specifies the Boolean attributes of the file.
    flags=0x0,
    # The operating system for which this file was designed.
    # 0x4 - NT and there is no need to change it.
    OS=0x4,
    # The general type of file.
    # 0x1 - the file is an application.
    fileType=0x1,
    # The function of the file.
    # 0x0 - the function is not defined for this fileType
    subtype=0x0,
    # Creation date and time stamp.
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'BitCraftToolBox'),
        StringStruct(u'FileDescription', u'{description}'),
        StringStruct(u'FileVersion', u'{version}'),
        StringStruct(u'InternalName', u'BitCraft_Companion'),
        StringStruct(u'LegalCopyright', u'Copyright (c) 2025'),
        StringStruct(u'OriginalFilename', u'BitCraft_Companion.exe'),
        StringStruct(u'ProductName', u'BitCraft Companion'),
        StringStruct(u'ProductVersion', u'{version}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)"""

    # Write to version_info.txt
    with open("version_info.txt", "w") as f:
        f.write(version_info_content)

    print(f"Generated version_info.txt for version {version}")
    return version


if __name__ == "__main__":
    generate_version_file()
