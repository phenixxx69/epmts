"""Converted representations: still PNG/JPEG pictures and VP8 IVF videos with an OGG sound track.

Pictures are made while the caller waits; videos are made in the background and polled.
Every file is cached under cache_dir/converted, named by the source SHA-256 and profile.
"""

import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from epmts import media as media_tools

PROFILES = {
    "png": {"extension": "png", "content_type": "image/png", "kind": "img"},
    "jpg": {"extension": "jpg", "content_type": "image/jpeg", "kind": "img"},
    "ivf": {"extension": "ivf", "content_type": "video/x-ivf", "kind": "video"},
}
MAX_IMAGE_WIDTH = 1920
MAX_VIDEO_WIDTH = 1280
MAX_VIDEO_SECONDS = 60
VIDEO_FRAME_RATE = 30
FAILURE_RETENTION = 600

READY, PENDING, FAILED = "ready", "pending", "failed"


class Converter:
    """Produces and caches converted files."""

    # Prepares the cache folder and the background workers.
    def __init__(self, cache_dir, workers=2):
        self.directory = os.path.join(cache_dir, "converted")
        os.makedirs(self.directory, exist_ok=True)
        self.executor = ThreadPoolExecutor(max_workers=workers)
        self.running = {}
        self.started = {}
        self.lock = threading.Lock()

    # Returns the cache path of a converted file.
    def path(self, media_hash, profile):
        return os.path.join(self.directory, "{}.{}".format(media_hash, PROFILES[profile]["extension"]))

    # Returns the cache path of the sound track of a converted video.
    def audio_path(self, media_hash):
        return os.path.join(self.directory, "{}.ogg".format(media_hash))

    # Returns the marker that remembers a recent failure.
    def _failure_marker(self, media_hash, profile):
        return self.path(media_hash, profile) + ".failed"

    # Returns (state, path): makes pictures now, starts videos in the background.
    def request(self, source, media_hash, media_type, profile, wait_seconds=0):
        target = self.path(media_hash, profile)
        if os.path.isfile(target) and os.path.getsize(target) > 0:
            return READY, target
        marker = self._failure_marker(media_hash, profile)
        if os.path.isfile(marker) and time.time() - os.path.getmtime(marker) < FAILURE_RETENTION:
            return FAILED, None
        key = (media_hash, profile)
        with self.lock:
            future = self.running.get(key)
            if future is None:
                future = self.executor.submit(self._convert, source, media_hash, media_type, profile)
                self.running[key] = future
                self.started[key] = time.time()
        if PROFILES[profile]["kind"] == "img":
            wait_seconds = max(wait_seconds, 25)
        if wait_seconds:
            try:
                future.result(timeout=wait_seconds)
            except Exception:
                pass  # a timeout means "still running"; a failure leaves its marker
        if future.done():
            with self.lock:
                self.running.pop(key, None)
                self.started.pop(key, None)
            return (READY, target) if os.path.isfile(target) else (FAILED, None)
        return PENDING, None

    # Returns the whole seconds since a running conversion started.
    def elapsed(self, media_hash, profile):
        started = self.started.get((media_hash, profile))
        return int(time.time() - started) if started else 0

    # Runs one conversion into a temporary file, then publishes it atomically.
    def _convert(self, source, media_hash, media_type, profile):
        target = self.path(media_hash, profile)
        temporary = target + ".part"
        try:
            if PROFILES[profile]["kind"] == "img":
                self._make_picture(source, media_type, profile, temporary)
            else:
                self._make_video(source, temporary)
                self._make_audio(source, media_hash)
            os.replace(temporary, target)
        except Exception:
            if os.path.exists(temporary):
                os.unlink(temporary)
            with open(self._failure_marker(media_hash, profile), "w"):
                pass
            raise

    # Writes the first usable image of a media as PNG or JPEG.
    def _make_picture(self, source, media_type, profile, target):
        from PIL import Image
        image = media_tools.first_frame(source, media_type)
        if image is None:
            raise RuntimeError("no frame could be read (is ffmpeg installed?)")
        if image.width > MAX_IMAGE_WIDTH:
            image = image.resize((MAX_IMAGE_WIDTH, round(image.height * MAX_IMAGE_WIDTH / image.width)), Image.Resampling.LANCZOS)
        if profile == "jpg":
            image.convert("RGB").save(target, "JPEG", quality=90)
        else:
            image.save(target, "PNG")

    # Encodes a VP8 IVF video (the only codec some game engines play).
    def _make_video(self, source, target):
        ffmpeg = media_tools.find_tool("ffmpeg")
        if ffmpeg is None:
            raise RuntimeError("ffmpeg is required for video conversion")
        subprocess.run(
            [ffmpeg, "-y", "-nostdin", "-loglevel", "error", "-i", source, "-an",
             "-c:v", "libvpx", "-b:v", "1M", "-crf", "10", "-deadline", "good", "-cpu-used", "2",
             "-pix_fmt", "yuv420p", "-r", str(VIDEO_FRAME_RATE), *media_tools.ffmpeg_frame_rate_mode_args(ffmpeg),
             "-t", str(MAX_VIDEO_SECONDS),
             "-vf", "scale='trunc(min({},iw)/2)*2':-2".format(MAX_VIDEO_WIDTH), "-f", "ivf", target],
            check=True, timeout=900,
        )

    # Extracts the sound track as OGG Vorbis when the source has one.
    def _make_audio(self, source, media_hash):
        ffmpeg = media_tools.find_tool("ffmpeg")
        ffprobe = media_tools.find_tool("ffprobe")
        if ffmpeg is None or ffprobe is None:
            return
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", source],
            capture_output=True, text=True, timeout=60,
        )
        if "audio" not in probe.stdout:
            return
        target = self.audio_path(media_hash)
        temporary = target + ".part"
        result = subprocess.run(
            [ffmpeg, "-y", "-nostdin", "-loglevel", "error", "-i", source, "-vn", "-c:a", "libvorbis", "-q:a", "4",
             "-t", str(MAX_VIDEO_SECONDS), "-f", "ogg", temporary],
            timeout=600,
        )
        if result.returncode == 0 and os.path.isfile(temporary):
            os.replace(temporary, target)
        elif os.path.exists(temporary):
            os.unlink(temporary)
