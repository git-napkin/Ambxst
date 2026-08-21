#!/usr/bin/env python3

import atexit
import colorsys
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def cmd(*args, input=None, timeout=10):
    return subprocess.run(args, input=input, capture_output=True, timeout=timeout, check=True).stdout


def main():
    for dep in ("grim", "slurp", "magick", "wl-copy", "notify-send"):
        if shutil.which(dep) is None:
            # Check fallback for magick->convert (IM6)
            if dep == "magick" and shutil.which("convert") is not None:
                continue
            subprocess.run(
                ["notify-send", "Color Picker", f"Missing dependency: {dep}", "-u", "critical"],
                check=False,
            )
            sys.exit(1)

    try:
        coords = subprocess.run(["slurp", "-p"], capture_output=True, timeout=30, check=True).stdout.decode().strip()
    except subprocess.CalledProcessError:
        # User cancelled (ESC) or slurp failed
        sys.exit(0)
    except subprocess.TimeoutExpired:
        sys.exit(1)

    if not coords:
        sys.exit(0)

    # Validate coords format: "x,y WxH"
    if not re.match(r"^-?\d+,-?\d+ \d+x\d+$", coords):
        subprocess.run(["notify-send", "Color Picker", "Invalid region", "-u", "critical"], check=False)
        sys.exit(1)

    try:
        grim_data = subprocess.run(["grim", "-g", coords, "-t", "ppm", "-"], capture_output=True, timeout=10, check=True).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        subprocess.run(["notify-send", "Color Picker", f"Capture failed: {e}", "-u", "critical"], check=False)
        sys.exit(1)

    if not grim_data:
        sys.exit(1)

    # Determine magick command: prefer magick, fallback to convert
    magick_cmd = "magick" if shutil.which("magick") else "convert"

    try:
        if magick_cmd == "magick":
            rgb_str = subprocess.run(
                ["magick", "-", "-format", "%[fx:int(255*r)] %[fx:int(255*g)] %[fx:int(255*b)]", "info:-"],
                input=grim_data, capture_output=True, timeout=10, check=True
            ).stdout.decode()
        else:
            rgb_str = subprocess.run(
                ["convert", "-", "-format", "%[fx:int(255*r)] %[fx:int(255*g)] %[fx:int(255*b)]", "info:-"],
                input=grim_data, capture_output=True, timeout=10, check=True
            ).stdout.decode()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        subprocess.run(["notify-send", "Color Picker", f"Color extraction failed", "-u", "critical"], check=False)
        sys.exit(1)

    parts = rgb_str.strip().split()
    if len(parts) != 3:
        sys.exit(1)
    try:
        r, g, b = map(int, parts)
    except ValueError:
        sys.exit(1)

    if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
        sys.exit(1)

    hex_color = f"#{r:02X}{g:02X}{b:02X}"
    rgb_color = f"rgb({r}, {g}, {b})"

    rn, gn, bn = r / 255, g / 255, b / 255
    h, s, v = colorsys.rgb_to_hsv(rn, gn, bn)
    hsv_color = f"hsv({round(h*360)}, {round(s*100)}%, {round(v*100)}%)"

    # Secure temp file (no symlink race)
    fd, icon = tempfile.mkstemp(suffix=".png", prefix="color_picker_")
    try:
        import os
        os.close(fd)
        Path(icon).unlink(missing_ok=True)
    except Exception:
        pass
    atexit.register(lambda: icon and Path(icon).unlink(missing_ok=True))

    try:
        if magick_cmd == "magick":
            subprocess.run(["magick", "-size", "64x64", f"xc:{hex_color}", icon], check=True, timeout=5)
        else:
            subprocess.run(["convert", "-size", "64x64", f"xc:{hex_color}", icon], check=True, timeout=5)
    except Exception:
        # Non-fatal: continue without icon
        icon = ""

    icon_args = ["-i", icon] if icon and Path(icon).exists() else []

    subprocess.run(["wl-copy"], input=hex_color.encode(), check=False, timeout=5)

    proc = subprocess.Popen(
        ["notify-send", "Color Picked", f"{hex_color} copied to clipboard", *icon_args, "-a", "ColorPicker", "-u", "normal", "--action=hex=Copy HEX", "--action=rgb=Copy RGB", "--action=hsv=Copy HSV"],
        stdout=subprocess.PIPE,
    )
    try:
        out, _ = proc.communicate(timeout=30)
        action = out.decode().strip() if out else ""
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.communicate(timeout=2)
        except Exception:
            pass
        action = ""

    if action == "rgb":
        subprocess.run(["wl-copy"], input=rgb_color.encode(), check=False, timeout=5)
        subprocess.run(["notify-send", "Color Picker", f"RGB copied: {rgb_color}", *icon_args, "-u", "low"], check=False)
    elif action == "hsv":
        subprocess.run(["wl-copy"], input=hsv_color.encode(), check=False, timeout=5)
        subprocess.run(["notify-send", "Color Picker", f"HSV copied: {hsv_color}", *icon_args, "-u", "low"], check=False)
    elif action == "hex":
        subprocess.run(["wl-copy"], input=hex_color.encode(), check=False, timeout=5)
        subprocess.run(["notify-send", "Color Picker", f"HEX copied: {hex_color}", *icon_args, "-u", "low"], check=False)


if __name__ == "__main__":
    main()
