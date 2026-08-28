#!/usr/bin/env python3
"""Camera enumeration and in-use detection.

Lists /dev/video* (names from /sys/class/video4linux) and detects open cameras
by matching /proc/*/fd device numbers. Prints one JSON object per line.

With an interval argument (seconds), loops so the QML service can keep one
interpreter alive instead of paying startup on every poll.
"""

import json
import os
import sys
import time

VIDEO4LINUX = "/sys/class/video4linux"


def _camera_name(node):
    v4l_name = None
    try:
        if os.path.islink(node):
            real = os.path.realpath(node)
            if os.path.basename(real).startswith("video"):
                v4l_name = os.path.basename(real)
    except OSError:
        pass
    if v4l_name and os.path.isdir(os.path.join(VIDEO4LINUX, v4l_name)):
        name_file = os.path.join(VIDEO4LINUX, v4l_name, "name")
        try:
            with open(name_file, "r", errors="replace") as f:
                return f.read().strip()
        except OSError:
            return v4l_name
    return os.path.basename(node)


def _list_cameras():
    cameras = []
    try:
        for entry in sorted(os.listdir("/dev")):
            if not entry.startswith("video"):
                continue
            node = os.path.join("/dev", entry)
            if not os.path.exists(node):
                continue
            cameras.append({"name": _camera_name(node), "node": node})
    except OSError:
        pass
    return cameras


def _open_camera_users(cameras):
    if not cameras:
        return []
    dev_numbers = set()
    for cam in cameras:
        try:
            dev_numbers.add(os.stat(cam["node"]).st_rdev)
        except OSError:
            continue
    if not dev_numbers:
        return []

    users = []
    try:
        entries = os.listdir("/proc")
    except OSError:
        return users

    for entry in entries:
        if not entry.isdigit():
            continue
        fd_dir = os.path.join("/proc", entry, "fd")
        try:
            fds = os.listdir(fd_dir)
        except OSError:
            continue
        for fd in fds:
            try:
                st = os.stat(os.path.join(fd_dir, fd))
            except OSError:
                continue
            if st.st_rdev in dev_numbers:
                users.append(entry)
                break
    return users


def _proc_name(pid):
    try:
        with open(os.path.join("/proc", pid, "comm"), "r") as f:
            return f.read().strip()
    except OSError:
        return "?"


def emit():
    cameras = _list_cameras()
    users = _open_camera_users(cameras)
    json.dump(
        {
            "cameras": cameras,
            "inUse": len(users) > 0,
            "users": [{"pid": pid, "name": _proc_name(pid)} for pid in users],
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
    sys.stdout.flush()


def main():
    interval = None
    if len(sys.argv) > 1:
        try:
            interval = float(sys.argv[1])
        except ValueError:
            interval = None

    if interval and interval > 0:
        while True:
            emit()
            time.sleep(interval)
    else:
        emit()


if __name__ == "__main__":
    main()
