"""Media file helpers: type detection, metadata removal, probing and ffmpeg access.

Only the standard library is needed here; Pillow and ffmpeg are used when present.
"""

import functools
import glob
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile

from . import REPO_ROOT

EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "video/webm": "webm",
    "video/mp4": "mp4",
    "video/x-m4v": "m4v",
}


# Finds ffmpeg or ffprobe: EPMTS_FFMPEG_DIR, then tools/bin (downloaded by the launchers), then PATH.
def find_tool(name):
    executable = name + (".exe" if os.name == "nt" else "")
    directories = []
    if os.environ.get("EPMTS_FFMPEG_DIR"):
        directories.append(os.environ["EPMTS_FFMPEG_DIR"])
    directories.extend(glob.glob(os.path.join(REPO_ROOT, "tools", "bin", "**", "bin"), recursive=True))
    directories.append(os.path.join(REPO_ROOT, "tools", "bin"))
    for directory in directories:
        candidate = os.path.join(directory, executable)
        if os.path.isfile(candidate):
            return candidate
    return shutil.which(name)


# Chooses the constant frame rate option from `ffmpeg -version` output: -fps_mode since
# ffmpeg 5.1, -vsync before (it was removed later). A build without a release number is a
# recent development build, which has -fps_mode.
def frame_rate_mode_args(version_output):
    match = re.search(r"ffmpeg version n?(\d+)\.(\d+)", version_output or "")
    if match and (int(match.group(1)), int(match.group(2))) < (5, 1):
        return ["-vsync", "cfr"]
    return ["-fps_mode", "cfr"]


# Asks one ffmpeg binary for its version once, and returns its constant frame rate option.
@functools.lru_cache(maxsize=None)
def ffmpeg_frame_rate_mode_args(ffmpeg):
    try:
        output = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        output = ""
    return tuple(frame_rate_mode_args(output))


# Computes the lowercase SHA-256 of a file, the media identifier across packs.
def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# Detects a supported media type from the file content, never from its name.
def sniff_type(path):
    with open(path, "rb") as handle:
        head = handle.read(64)
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        return "video/x-m4v" if brand.startswith(b"M4V") else "video/mp4"
    return None


# Returns the media family of a type: still, gif, film or None.
def family(media_type):
    if media_type in ("image/jpeg", "image/png", "image/webp"):
        return "still"
    if media_type == "image/gif":
        return "gif"
    if media_type in ("video/webm", "video/mp4", "video/x-m4v"):
        return "film"
    return None


# Copies a JPEG without its APPn metadata segments (EXIF, XMP, IPTC) and comments; ICC (APP2) is kept.
def _strip_jpeg(data):
    out = bytearray(data[:2])
    position = 2
    while position + 4 <= len(data):
        if data[position] != 0xFF:
            break
        marker = data[position + 1]
        if marker == 0xDA:  # start of scan: the rest is image data
            out += data[position:]
            return bytes(out)
        length = struct.unpack(">H", data[position + 2:position + 4])[0]
        segment = data[position:position + 2 + length]
        keep = not (0xE1 <= marker <= 0xEF and marker != 0xE2) and marker != 0xFE
        if keep:
            out += segment
        position += 2 + length
    out += data[position:]
    return bytes(out)


# Copies a PNG without its text, time and EXIF chunks.
def _strip_png(data):
    dropped = {b"tEXt", b"zTXt", b"iTXt", b"tIME", b"eXIf"}
    out = bytearray(data[:8])
    position = 8
    while position + 8 <= len(data):
        length = struct.unpack(">I", data[position:position + 4])[0]
        kind = data[position + 4:position + 8]
        end = position + 12 + length
        if kind not in dropped:
            out += data[position:end]
        position = end
    return bytes(out)


# Copies a WebP without its EXIF and XMP chunks, clearing their flags in VP8X.
def _strip_webp(data):
    chunks = bytearray()
    position = 12
    while position + 8 <= len(data):
        kind = data[position:position + 4]
        size = struct.unpack("<I", data[position + 4:position + 8])[0]
        end = position + 8 + size + (size & 1)
        chunk = bytearray(data[position:end])
        if kind == b"VP8X":
            chunk[8] &= ~0x0C & 0xFF  # EXIF (0x08) and XMP (0x04) flags
        if kind not in (b"EXIF", b"XMP "):
            chunks += chunk
        position = end
    return b"RIFF" + struct.pack("<I", len(chunks) + 4) + b"WEBP" + bytes(chunks)


# Returns the EXIF orientation of a JPEG (1 = upright), or None when Pillow or the tag is missing.
def _jpeg_orientation(path):
    try:
        from PIL import Image
        with Image.open(path) as image:
            return image.getexif().get(0x0112)
    except Exception:
        return None


# Writes a metadata-free copy of a media to target; films need ffmpeg, GIF is copied as is.
def strip_metadata(source, target, media_type):
    if media_type == "image/jpeg" and _jpeg_orientation(source) not in (None, 1):
        # Removing EXIF would drop the rotation: apply it to the pixels first.
        from PIL import Image, ImageOps
        with Image.open(source) as image:
            icc = image.info.get("icc_profile")
            rotated = ImageOps.exif_transpose(image).convert("RGB")
        rotated.save(target, "JPEG", quality=95, icc_profile=icc)
        return
    if media_type in ("image/jpeg", "image/png", "image/webp"):
        with open(source, "rb") as handle:
            data = handle.read()
        cleaner = {"image/jpeg": _strip_jpeg, "image/png": _strip_png, "image/webp": _strip_webp}[media_type]
        with open(target, "wb") as handle:
            handle.write(cleaner(data))
        return
    if family(media_type) == "film":
        ffmpeg = find_tool("ffmpeg")
        if ffmpeg is None:
            raise RuntimeError("ffmpeg is required to import a video (metadata must be removed)")
        container = "webm" if media_type == "video/webm" else "mp4"
        subprocess.run(
            [ffmpeg, "-y", "-nostdin", "-loglevel", "error", "-i", source, "-map", "0", "-map_metadata", "-1",
             "-map_chapters", "-1", "-c", "copy", "-f", container, target],
            check=True,
        )
        return
    shutil.copyfile(source, target)


# Returns width, height and duration (seconds or None) of a media file.
def probe(path, media_type):
    width = height = duration = None
    if family(media_type) in ("still", "gif"):
        try:
            from PIL import Image
            with Image.open(path) as image:
                width, height = image.size
        except Exception:
            pass
        return width, height, None
    ffprobe = find_tool("ffprobe")
    if ffprobe is None:
        return None, None, None
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
             "-of", "json", path],
            capture_output=True, text=True, timeout=60, check=True,
        )
        info = json.loads(result.stdout or "{}")
        stream = (info.get("streams") or [{}])[0]
        width, height = stream.get("width"), stream.get("height")
        raw = (info.get("format") or {}).get("duration")
        duration = round(float(raw), 3) if raw not in (None, "N/A") else None
    except (subprocess.SubprocessError, ValueError, OSError):
        pass
    return width, height, duration


# Prepares a source file for a pack: metadata stripped into a temp file, then hashed and probed.
def prepare(source, work_dir):
    media_type = sniff_type(source)
    if media_type is None:
        raise ValueError("unsupported media type (allowed: jpeg, png, webp, gif, webm, mp4)")
    handle, temporary = tempfile.mkstemp(dir=work_dir, suffix=".tmp")
    os.close(handle)
    try:
        strip_metadata(source, temporary, media_type)
        width, height, duration = probe(temporary, media_type)
        return {
            "path": temporary,
            "hash": sha256_file(temporary),
            "size": os.path.getsize(temporary),
            "type": media_type,
            "size_x": width,
            "size_y": height,
            "duration": duration,
        }
    except Exception:
        os.unlink(temporary)
        raise


# Returns the first usable frame of a GIF or film as a PIL image (ffmpeg for films), or None.
def first_frame(path, media_type, seek_seconds=1):
    from PIL import Image
    if family(media_type) in ("still", "gif"):
        with Image.open(path) as image:
            image.seek(0)
            return image.convert("RGB")
    ffmpeg = find_tool("ffmpeg")
    if ffmpeg is None:
        return None
    for seek in (["-ss", str(seek_seconds)], []):
        try:
            result = subprocess.run(
                [ffmpeg, "-nostdin", "-loglevel", "error"] + seek + ["-i", path, "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-"],
                capture_output=True, timeout=60,
            )
        except (subprocess.SubprocessError, OSError):
            return None
        if result.returncode == 0 and result.stdout:
            import io
            return Image.open(io.BytesIO(result.stdout)).convert("RGB")
    return None
