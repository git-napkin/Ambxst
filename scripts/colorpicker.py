#!/usr/bin/env python3

import atexit
import colorsys
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


def cmd(*args, input=None, timeout=10):
    return subprocess.run(args, input=input, capture_output=True, timeout=timeout, check=True).stdout


def notify_shell(payload):
    pipe = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "ambxst+_ipc.pipe")
    body = dict(payload)
    body["v"] = "notify"
    data = (json.dumps(body) + "\n").encode("utf-8")
    fd = None
    try:
        st = os.stat(pipe)
        if not stat.S_ISFIFO(st.st_mode):
            return False
        fd = os.open(pipe, os.O_WRONLY | os.O_NONBLOCK)
        written = 0
        while written < len(data):
            n = os.write(fd, data[written:])
            if n == 0:
                return False
            written += n
        return True
    except OSError:
        return False
    finally:
        if fd is not None:
            os.close(fd)


def notify_fallback(summary, body, urgency="normal", extra=None):
    args = ["notify-send", summary, body, "-u", urgency, "-a", "ColorPicker"]
    if extra:
        args.extend(extra)
    subprocess.run(args, check=False)


def main():
    for dep in ("grim", "slurp", "magick", "wl-copy"):
        if shutil.which(dep) is None:
            # Check fallback for magick->convert (IM6)
            if dep == "magick" and shutil.which("convert") is not None:
                continue
            notify_fallback("Color Picker", f"Missing dependency: {dep}", "critical")
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
        notify_fallback("Color Picker", "Invalid region", "critical")
        sys.exit(1)

    try:
        grim_data = subprocess.run(["grim", "-g", coords, "-t", "ppm", "-"], capture_output=True, timeout=10, check=True).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        notify_fallback("Color Picker", f"Capture failed: {e}", "critical")
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
        notify_fallback("Color Picker", "Color extraction failed", "critical")
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

    payload = {
        "summary": "Color Picked",
        "body": f"{hex_color} copied to clipboard",
        "appName": "ColorPicker",
        "image": icon if icon and Path(icon).exists() else "",
        "actions": [
            {"identifier": "hex", "text": "Copy HEX", "clipboard": hex_color},
            {"identifier": "rgb", "text": "Copy RGB", "clipboard": rgb_color},
            {"identifier": "hsv", "text": "Copy HSV", "clipboard": hsv_color},
        ],
    }
    if notify_shell(payload):
        return

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
        notify_fallback("Color Picker", f"RGB copied: {rgb_color}", "low")
    elif action == "hsv":
        subprocess.run(["wl-copy"], input=hsv_color.encode(), check=False, timeout=5)
        notify_fallback("Color Picker", f"HSV copied: {hsv_color}", "low")
    elif action == "hex":
        subprocess.run(["wl-copy"], input=hex_color.encode(), check=False, timeout=5)
        notify_fallback("Color Picker", f"HEX copied: {hex_color}", "low")


if __name__ == "__main__":
    main()
