#!/usr/bin/env python3
"""
Lockscreen Wallpaper Frame Extractor for Ambxst[+]
Extracts first frame from video/GIF wallpapers for lockscreen background.
Only processes video and GIF files - skips regular images.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

# Supported extensions for processing
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi", ".mkv"}
GIF_EXTENSIONS = {".gif"}


class LockscreenWallpaperGenerator:
    def __init__(self, wallpaper_path: str, data_path: str):
        self.current_wallpaper = Path(wallpaper_path).expanduser()
        self.data_path = Path(data_path)
        self.lockscreen_dir: Optional[Path] = None

    def validate_wallpaper(self) -> bool:
        """Validate wallpaper exists."""
        try:
            # Resolve to avoid symlink tricks; ensure file
            self.current_wallpaper = self.current_wallpaper.resolve()
            self.data_path = self.data_path.expanduser().resolve()
        except Exception:
            pass
        if not self.current_wallpaper.exists() or not self.current_wallpaper.is_file():
            print(f"ERROR: Wallpaper not found: {self.current_wallpaper}")
            return False
        # Size guard
        try:
            if self.current_wallpaper.stat().st_size > 500 * 1024 * 1024:
                print("ERROR: Wallpaper too large (>500MB)")
                return False
        except Exception:
            pass

        # Setup lockscreen directory in QuickShell data path (with symlink guard)
        self.lockscreen_dir = (self.data_path / "lockscreen")
        if self.lockscreen_dir.is_symlink():
            print(f"ERROR: Lockscreen dir is symlink, refusing: {self.lockscreen_dir}")
            return False
        # Ensure data_path itself not symlink-escaped
        try:
            self.lockscreen_dir.mkdir(parents=True, exist_ok=True)
            if self.lockscreen_dir.resolve().parent != self.data_path.resolve() and self.lockscreen_dir.resolve() != (self.data_path.resolve() / "lockscreen").resolve():
                print("ERROR: Lockscreen dir escape detected")
                return False
        except Exception as e:
            print(f"ERROR: Cannot create lockscreen dir: {e}")
            return False
        # Secure perms
        try:
            self.lockscreen_dir.chmod(0o700)
        except Exception:
            pass

        print(f"✓ Current wallpaper: {self.current_wallpaper.name}")
        print(f"✓ Lockscreen cache: {self.lockscreen_dir}")
        return True

    def is_video_or_gif(self) -> bool:
        """Check if current wallpaper is a video or GIF."""
        ext = self.current_wallpaper.suffix.lower()
        return ext in VIDEO_EXTENSIONS or ext in GIF_EXTENSIONS

    def get_output_path(self) -> Path:
        """Get output path for lockscreen wallpaper."""
        if self.lockscreen_dir is None:
            raise RuntimeError("Lockscreen directory not initialized")

        # Create output filename: original_name.extension.jpg
        output_name = self.current_wallpaper.name + ".jpg"
        return self.lockscreen_dir / output_name

    def clean_lockscreen_dir(self) -> None:
        """Remove all existing files in lockscreen directory (safe)."""
        if self.lockscreen_dir is None:
            return
        # Re-validate not symlink and inside data_path
        if self.lockscreen_dir.is_symlink():
            print("WARNING: Lockscreen dir is symlink, skipping clean")
            return
        try:
            if self.lockscreen_dir.resolve().parent != self.data_path.resolve():
                print("WARNING: Lockscreen dir outside data_path, skipping clean")
                return
        except Exception:
            return
        try:
            for file in self.lockscreen_dir.iterdir():
                try:
                    if file.is_file() or file.is_symlink():
                        file.unlink()
                        print(f"✓ Removed old file: {file.name}")
                    elif file.is_dir():
                        import shutil
                        shutil.rmtree(file)
                        print(f"✓ Removed old dir: {file.name}")
                except Exception as e:
                    print(f"WARNING: Failed to remove {file}: {e}")
        except Exception as e:
            print(f"WARNING: Failed to clean directory: {e}")

    def extract_first_frame(self) -> Tuple[bool, str]:
        """Extract first frame from video/GIF using FFmpeg."""
        output_path = self.get_output_path()

        # Early ffmpeg check
        import shutil
        if shutil.which("ffmpeg") is None:
            return False, "ffmpeg not found"

        try:
            # FFmpeg command to extract first frame (use -- to handle leading dash filenames)
            # ffmpeg doesn't support --, so use ./ prefix for relative paths with dash
            wp = str(self.current_wallpaper)
            out = str(output_path)
            # Ensure leading dash not interpreted as option by prefixing ./
            if os.path.basename(wp).startswith("-"):
                wp = os.path.join(os.path.dirname(wp), "./" + os.path.basename(wp))
            if os.path.basename(out).startswith("-"):
                out = os.path.join(os.path.dirname(out), "./" + os.path.basename(out))
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                wp,
                "-vframes",
                "1",  # Extract only first frame
                "-q:v",
                "2",  # High quality
                "-f",
                "image2",  # Force image format
                out,
            ]

            print(f"⚡ Extracting first frame...")

            # Run FFmpeg
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and output_path.exists():
                print(f"✅ Frame saved: {output_path.name}")
                return True, "Success"
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                return False, error_msg

        except subprocess.TimeoutExpired:
            return False, "Timeout"
        except Exception as e:
            return False, str(e)

    def run(self) -> int:
        """Main execution function."""
        print("🔒 Ambxst[+] Lockscreen Wallpaper Generator")
        print("=" * 40)

        # Validate wallpaper
        if not self.validate_wallpaper():
            return 1

        # Check if wallpaper is video or GIF
        if not self.is_video_or_gif():
            ext = self.current_wallpaper.suffix.lower()
            print(f"ℹ️  Wallpaper is a regular image ({ext})")
            print("ℹ️  No processing needed - use wallpaper directly")
            # Clean stale video cache so lockscreen doesn't show old frame
            self.clean_lockscreen_dir()
            return 0

        # Clean existing files
        self.clean_lockscreen_dir()

        # Extract first frame
        success, message = self.extract_first_frame()

        if success:
            print("🎉 Lockscreen wallpaper ready!")
            return 0
        else:
            print(f"❌ Failed to extract frame: {message}")
            return 1


def main():
    """Entry point."""
    if len(sys.argv) != 3:
        print("Usage: python3 lockscreen_wallpaper.py <wallpaper_path> <data_path>")
        print(
            "Example: python3 lockscreen_wallpaper.py /path/to/video.mp4 ~/.local/share/quickshell"
        )
        return 1

    wallpaper_path = sys.argv[1]
    data_path = sys.argv[2]
    generator = LockscreenWallpaperGenerator(wallpaper_path, data_path)
    return generator.run()


if __name__ == "__main__":
    sys.exit(main())
