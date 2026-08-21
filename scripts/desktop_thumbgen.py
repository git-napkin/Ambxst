#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple

VIDEO_EXTENSIONS = {'.mp4', '.webm', '.mov', '.avi', '.mkv', '.gif'}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff', '.bmp'}

THUMBNAIL_SIZE = "64x64"

class DesktopThumbnailGenerator:
    def __init__(self, desktop_path: str, cache_dir: str):
        self.desktop_path = Path(desktop_path).expanduser()
        self.cache_dir = Path(cache_dir)
        self.files_to_process = {'videos': [], 'images': []}
        self.total_files = 0
        self.processed_count = 0
        self.lock = threading.Lock()

    def setup_cache_dir(self) -> bool:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            print(f"✓ Cache dir: {self.cache_dir}")
            return True
        except Exception as e:
            print(f"ERROR creating cache dir: {e}")
            return False

    def find_files(self) -> Tuple[List[Path], List[Path]]:
        videos = []
        images = []

        if not self.desktop_path.exists():
            print(f"ERROR: Desktop path not found: {self.desktop_path}")
            return [], []

        # Validate not symlink escape and not hidden leakage
        try:
            resolved = self.desktop_path.resolve()
        except Exception:
            resolved = self.desktop_path

        try:
            for file_path in self.desktop_path.iterdir():
                # Skip symlinks to avoid traversal outside desktop dir
                if file_path.is_symlink():
                    continue
                if file_path.name.startswith("."):
                    continue
                if file_path.is_file():
                    ext = file_path.suffix.lower()
                    if ext in VIDEO_EXTENSIONS:
                        videos.append(file_path)
                    elif ext in IMAGE_EXTENSIONS:
                        images.append(file_path)
                        
            videos.sort()
            images.sort()
            
            print(f"✓ Found {len(videos)} videos, {len(images)} images")
            return videos, images
            
        except Exception as e:
            print(f"ERROR scanning directory: {e}")
            return [], []
    
    def get_thumbnail_path(self, file_path: Path) -> Path:
        # Use .name + ".jpg" to avoid replace() bug (replaces all occurrences)
        # e.g. "a.png.png".replace(".png","") -> "a" wrong; here we want "a.png.png.jpg"
        thumbnail_name = file_path.name + ".jpg"
        return self.cache_dir / thumbnail_name
    
    def needs_thumbnail(self, file_path: Path) -> bool:
        thumbnail_path = self.get_thumbnail_path(file_path)
        
        if not thumbnail_path.exists():
            return True
            
        try:
            file_mtime = file_path.stat().st_mtime
            thumbnail_mtime = thumbnail_path.stat().st_mtime
            return file_mtime > thumbnail_mtime
        except Exception:
            return True
    
    def generate_video_thumbnail(self, video_path: Path) -> Tuple[bool, str]:
        thumbnail_path = self.get_thumbnail_path(video_path)
        # Guard leading dash filenames
        wp = str(video_path)
        out = str(thumbnail_path)
        if os.path.basename(wp).startswith("-"):
            wp = os.path.join(os.path.dirname(wp) or ".", "./" + os.path.basename(wp))
        if os.path.basename(out).startswith("-"):
            out = os.path.join(os.path.dirname(out) or ".", "./" + os.path.basename(out))
        # Ensure parent dir
        try:
            Path(out).parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        try:
            cmd = [
                'ffmpeg', '-y',
                '-i', wp,
                '-ss', '00:00:01',
                '-vframes', '1',
                '-vf', f'scale=64:64:force_original_aspect_ratio=increase,crop=64:64',
                '-q:v', '2',
                '-f', 'image2',
                out
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0 and thumbnail_path.exists():
                return True, "Success"
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            return False, "Timeout"
        except Exception as e:
            return False, str(e)
    
    def generate_image_thumbnail(self, image_path: Path) -> Tuple[bool, str]:
        thumbnail_path = self.get_thumbnail_path(image_path)
        ip = str(image_path)
        out = str(thumbnail_path)
        if os.path.basename(ip).startswith("-"):
            ip = os.path.join(os.path.dirname(ip) or ".", "./" + os.path.basename(ip))
        if os.path.basename(out).startswith("-"):
            out = os.path.join(os.path.dirname(out) or ".", "./" + os.path.basename(out))
        try:
            Path(out).parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        try:
            # Use magick if available, fallback to convert
            import shutil
            conv = "magick" if shutil.which("magick") else "convert"
            base = [conv] if conv == "magick" else ["convert"]
            # For magick, need: magick <input> ... <output>
            cmd = base + [ip, '-resize', '64x64^', '-gravity', 'center', '-extent', '64x64', '-quality', '85', out]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0 and thumbnail_path.exists():
                return True, "Success"
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            return False, "Timeout"
        except Exception as e:
            return False, str(e)
    
    def generate_single_thumbnail(self, file_path: Path, file_type: str) -> Tuple[bool, str]:
        try:
            if file_type == 'video':
                success, message = self.generate_video_thumbnail(file_path)
            elif file_type == 'image':
                success, message = self.generate_image_thumbnail(file_path)
            else:
                return False, f"Unknown file type: {file_type}"
            
            with self.lock:
                self.processed_count += 1
                progress = (self.processed_count / self.total_files) * 100
                status = "✓" if success else "✗"
                print(f"[{self.processed_count}/{self.total_files}] {status} {file_path.name} ({progress:.1f}%)")
            
            return success, message
            
        except Exception as e:
            return False, str(e)
    
    def process_files(self, max_workers: int = 4) -> None:
        all_files = []
        
        for file_path in self.files_to_process['videos']:
            all_files.append((file_path, 'video'))
        for file_path in self.files_to_process['images']:
            all_files.append((file_path, 'image'))
        
        if not all_files:
            print("✓ All thumbnails are up to date")
            return
            
        print(f"⚡ Processing {len(all_files)} files with {max_workers} workers...")
        start_time = time.time()
        
        failed_files = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(self.generate_single_thumbnail, file_path, file_type): (file_path, file_type)
                for file_path, file_type in all_files
            }
            
            for future in as_completed(future_to_file):
                file_path, file_type = future_to_file[future]
                try:
                    success, message = future.result()
                    if not success:
                        failed_files.append((file_path, message))
                        
                except Exception as e:
                    failed_files.append((file_path, str(e)))
        
        elapsed = time.time() - start_time
        success_count = self.total_files - len(failed_files)
        
        print(f"\n🏁 Processing complete in {elapsed:.1f}s")
        print(f"✅ Success: {success_count}/{self.total_files}")
        
        if failed_files:
            print(f"❌ Failed: {len(failed_files)}")
            for file_path, error in failed_files[:3]:
                print(f"   • {file_path.name}: {error}")
            if len(failed_files) > 3:
                print(f"   ... and {len(failed_files) - 3} more")
    
    def run(self) -> int:
        print("🖼️  Desktop Thumbnail Generator")
        print("=" * 40)
        
        if not self.setup_cache_dir():
            return 1
        
        videos, images = self.find_files()
        if not any([videos, images]):
            print("ℹ️  No media files found")
            return 0
        
        for video in videos:
            if self.needs_thumbnail(video):
                self.files_to_process['videos'].append(video)
                
        for image in images:
            if self.needs_thumbnail(image):
                self.files_to_process['images'].append(image)
        
        self.total_files = (
            len(self.files_to_process['videos']) + 
            len(self.files_to_process['images'])
        )
        
        if self.total_files == 0:
            print("✓ All thumbnails are up to date")
            return 0
        
        print(f"📋 {self.total_files} files need thumbnail generation")
        print(f"   • Videos: {len(self.files_to_process['videos'])}")
        print(f"   • Images: {len(self.files_to_process['images'])}")
        
        max_workers = min(4, os.cpu_count() or 1, self.total_files)
        
        try:
            self.process_files(max_workers)
            print("🎉 Thumbnail generation complete!")
            return 0
        except KeyboardInterrupt:
            print("\n⚠️  Interrupted by user")
            return 130
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return 1

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 desktop_thumbgen.py <desktop_path> <cache_dir>")
        return 1

    desktop_path = sys.argv[1]
    cache_dir = sys.argv[2]
    generator = DesktopThumbnailGenerator(desktop_path, cache_dir)
    return generator.run()

if __name__ == '__main__':
    sys.exit(main())
