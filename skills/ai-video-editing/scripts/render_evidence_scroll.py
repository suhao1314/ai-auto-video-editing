"""Render a silent, editable-timeline MP4 from a real local long screenshot.

Coordinates are source-image pixels. Times are LOCAL clip seconds, quantized
up to the next frame. A quintic ease moves the crop from start-y to the target
row, holds through read-until, then optionally moves to end-y by the last frame.
The image is cropped/scaled, never retyped, redrawn, or supplemented with UI.
Requires existing Pillow and FFmpeg; installs nothing and refuses replacement.
"""

import argparse
from collections import deque
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading

from PIL import Image


def finite(value, name, lower=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value < lower:
        raise ValueError(f"{name} must be >= {lower}")
    return float(value)


def size_arg(value):
    try:
        width, height = map(int, value.lower().split("x"))
    except (ValueError, AttributeError):
        raise argparse.ArgumentTypeError("size must be WIDTHxHEIGHT, e.g. 1280x720")
    if min(width, height) < 64 or max(width, height) > 3840 or width % 2 or height % 2:
        raise argparse.ArgumentTypeError("size must be even, 64..3840 pixels per side")
    return width, height


def ease(value):
    return value ** 3 * (10 + value * (-15 + 6 * value))


@dataclass
class Motion:
    fps: int
    frames: int
    start_frame: int
    arrive_frame: int
    read_frame: int
    start_top: float
    target_top: float
    end_top: float
    scale: float
    target_y: float

    def top(self, frame):
        if not 0 <= frame < self.frames:
            raise ValueError("Frame index is outside the clip")
        if frame <= self.start_frame:
            value = self.start_top
        elif frame < self.arrive_frame:
            amount = (frame - self.start_frame) / (self.arrive_frame - self.start_frame)
            value = self.start_top + (self.target_top - self.start_top) * ease(amount)
        elif frame <= self.read_frame or self.end_top == self.target_top:
            value = self.target_top
        else:
            amount = (frame - self.read_frame) / (self.frames - 1 - self.read_frame)
            value = self.target_top + (self.end_top - self.target_top) * ease(amount)
        return round(value)


def prepare(image, *, size=(1280, 720), crop_x=0, crop_width=None, start_y=0,
            target_y, target_screen_y=0.4, scroll_start=0.4, arrive_at=2.8,
            read_until=4.8, duration=6, end_y=None, fps=25):
    width, height = size_arg(f"{size[0]}x{size[1]}")
    if isinstance(fps, bool) or not isinstance(fps, int) or not 1 <= fps <= 60:
        raise ValueError("fps must be an integer from 1 to 60")
    crop_width = image.width if crop_width is None else crop_width
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (crop_x, crop_width)):
        raise ValueError("crop-x and crop-width must be integer source pixels")
    if crop_x < 0 or crop_width <= 0 or crop_x + crop_width > image.width:
        raise ValueError("Horizontal crop must be fully inside the source image")
    for value, name in ((start_y, "start-y"), (target_y, "target-y"),
                        (target_screen_y, "target-screen-y"), (scroll_start, "scroll-start"),
                        (arrive_at, "arrive-at"), (read_until, "read-until"), (duration, "duration")):
        finite(value, name)
    if target_screen_y >= 1 or target_y >= image.height:
        raise ValueError("target-screen-y must be >= 0 and < 1; target-y must be inside the image")
    if not 0 <= scroll_start < arrive_at <= read_until <= duration:
        raise ValueError("Require 0 <= scroll-start < arrive-at <= read-until <= duration")
    scale = width / crop_width
    scaled_height = round(image.height * scale)
    max_top = scaled_height - height
    if max_top < 0:
        raise ValueError("The image/crop is shorter than the viewport; choose a shorter output height")
    start_top = start_y * scale
    target_top = target_y * scale - target_screen_y * height
    end_top = target_top if end_y is None else finite(end_y, "end-y") * scale
    if any(not 0 <= value <= max_top for value in (start_top, target_top, end_top)):
        raise ValueError("Start, target or end crop extends outside the image; adjust crop/target-screen-y")
    frames = math.ceil(duration * fps - 1e-9)
    quantize = lambda seconds: math.ceil(seconds * fps - 1e-9)
    begin, arrive, read = map(quantize, (scroll_start, arrive_at, read_until))
    if frames < 3 or arrive - begin < 2 or arrive >= frames:
        raise ValueError("Motion needs a start, an intermediate and an arrival frame")
    if end_y is not None and read >= frames - 1:
        raise ValueError("Continuation needs at least one frame after read-until")
    if image.mode == "RGBA" or "transparency" in image.info:
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, "white")
        flat.paste(rgba, mask=rgba.getchannel("A"))
        image = flat
    strip = image.convert("RGB").crop((crop_x, 0, crop_x + crop_width, image.height))
    canvas = strip.resize((width, scaled_height), Image.Resampling.LANCZOS)
    motion = Motion(fps, frames, begin, arrive, read, start_top, target_top, end_top, scale, target_y)
    return canvas, motion


def render(image, output, *, ffmpeg="ffmpeg", **settings):
    image, output = Path(image).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(f"Output already exists; choose a new filename: {output}")
    if output.suffix.lower() != ".mp4" or not output.parent.is_dir():
        raise ValueError("Output must be a new .mp4 in an existing directory")
    if not image.is_file():
        raise ValueError("Image input does not exist")
    source_hash = hashlib.sha256(image.read_bytes()).hexdigest()
    with Image.open(image) as original:
        original.load()
        source_size = list(original.size)
        canvas, motion = prepare(original, **settings)
    width, height = settings.get("size", (1280, 720))
    descriptor, staging = tempfile.mkstemp(prefix=f".{output.stem}-", suffix=".mp4", dir=output.parent)
    os.close(descriptor)
    staging = Path(staging)
    process = None
    reader = None
    errors = deque(maxlen=8)
    try:
        command = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-s:v", f"{width}x{height}",
                   "-r", str(motion.fps), "-i", "pipe:0", "-an", "-c:v", "libx264",
                   "-preset", "veryfast", "-crf", "16", "-threads", "2",
                   "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(staging)]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        def collect_errors():
            while True:
                chunk = process.stderr.read(1024)
                if not chunk:
                    break
                errors.append(chunk)

        reader = threading.Thread(target=collect_errors, daemon=True)
        reader.start()
        try:
            for frame in range(motion.frames):
                top = motion.top(frame)
                process.stdin.write(canvas.crop((0, top, width, top + height)).tobytes())
            process.stdin.close()
        except (BrokenPipeError, OSError):
            try:
                process.stdin.close()
            except OSError:
                pass
            process.wait()
            reader.join()
            detail = b"".join(errors).decode("utf-8", errors="replace")
            raise ValueError(f"FFmpeg stopped while receiving frames: {detail}") from None
        process.wait()
        reader.join()
        if process.returncode:
            detail = b"".join(errors).decode("utf-8", errors="replace")
            raise ValueError(f"FFmpeg could not render the clip: {detail}")
        if hashlib.sha256(image.read_bytes()).hexdigest() != source_hash:
            raise ValueError("Source image changed during render; the clip was not committed")
        # Exclusive creation also works where Windows policies/filesystems disallow hardlinks.
        created = False
        try:
            with output.open("xb") as destination:
                created = True
                with staging.open("rb") as source:
                    shutil.copyfileobj(source, destination)
        except OSError:
            if created:
                output.unlink(missing_ok=True)
            raise
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()
            if reader is not None:
                reader.join(timeout=5)
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
            process.stderr.close()
        staging.unlink(missing_ok=True)
        canvas.close()
    checkpoints = sorted({0, motion.start_frame, motion.arrive_frame,
                          min(motion.frames - 1, motion.read_frame), motion.frames - 1})
    return {"schema_version": 1, "image": str(image), "image_sha256": source_hash,
            "source_size": source_size, "output": str(output), "size": [width, height],
            "fps": motion.fps, "frames": motion.frames, "duration_s": motion.frames / motion.fps,
            "audio": False, "scale": motion.scale, "crop_x": settings.get("crop_x", 0),
            "crop_width": settings.get("crop_width") or source_size[0],
            "arrive_at_s": motion.arrive_frame / motion.fps,
            "read_until_s": motion.read_frame / motion.fps,
            "continues_after_reading": settings.get("end_y") is not None,
            "keyframes": [{"frame": frame, "seconds": frame / motion.fps,
                           "source_top_y": motion.top(frame) / motion.scale,
                           "target_screen_y_px": motion.target_y * motion.scale - motion.top(frame)}
                          for frame in checkpoints],
            "notes": ["Silent screenshot crop only; place on the matching narration timeline.",
                      "Arrival/read times are rounded up to the next frame; positions to output pixels.",
                      "Readability and whether the source row is correct need visual review.",
                      "H.264 and scaling preserve content, not exact original pixel values."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--start-y", type=float, default=0)
    parser.add_argument("--target-y", type=float, required=True)
    parser.add_argument("--target-screen-y", type=float, default=0.4)
    parser.add_argument("--scroll-start", type=float, default=0.4)
    parser.add_argument("--arrive-at", type=float, default=2.8)
    parser.add_argument("--read-until", type=float, default=4.8)
    parser.add_argument("--duration", type=float, default=6)
    parser.add_argument("--end-y", type=float)
    parser.add_argument("--crop-x", type=int, default=0)
    parser.add_argument("--crop-width", type=int)
    parser.add_argument("--size", type=size_arg, default=(1280, 720))
    parser.add_argument("--fps", type=int, default=25)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = vars(parser.parse_args())
    try:
        report = render(**args)
    except (OSError, ValueError, argparse.ArgumentTypeError) as error:
        parser.exit(2, f"Evidence scroll unavailable: {error}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
