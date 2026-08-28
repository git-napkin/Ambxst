#!/usr/bin/env python3
"""Scan a desktop directory and print JSON items (folders, .desktop files, others).

Replaces the old QML path of `ls` plus one `cat` per .desktop file.
"""

import json
import os
import sys


def _desktop_name_icon(path, fallback_name):
    name = fallback_name
    icon = "application-x-executable"
    try:
        with open(path, errors="replace") as f:
            for line in f:
                if line.startswith("Name="):
                    name = line[5:].strip()
                elif line.startswith("Icon="):
                    icon = line[5:].strip()
    except OSError:
        pass
    return name, icon


def scan(desktop_dir):
    items = []
    try:
        names = sorted(os.listdir(desktop_dir))
    except OSError:
        return items

    for name in names:
        if name.startswith("."):
            continue
        path = os.path.join(desktop_dir, name)
        if os.path.isdir(path):
            items.append({
                "name": name,
                "path": path,
                "type": "folder",
                "icon": "folder",
                "isDesktopFile": False,
                "sortOrder": 0,
            })
        elif name.endswith(".desktop"):
            disp, icon = _desktop_name_icon(path, name[:-8])
            items.append({
                "name": disp,
                "path": path,
                "type": "application",
                "icon": icon,
                "isDesktopFile": True,
                "sortOrder": 1,
            })
        else:
            items.append({
                "name": name,
                "path": path,
                "type": None,
                "icon": None,
                "isDesktopFile": False,
                "sortOrder": 2,
            })
    return items


def main():
    if len(sys.argv) != 2:
        print("Usage: desktop_scan.py <desktop_dir>", file=sys.stderr)
        return 1
    json.dump(scan(sys.argv[1]), sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
