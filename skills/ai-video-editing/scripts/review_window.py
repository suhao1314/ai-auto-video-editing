"""Review a disputed edit locally with the pinned filmstrip and waveform renderer."""

import argparse
from importlib.util import module_from_spec, spec_from_file_location
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from check_export import inspect, local_file


def load_renderer():
    path = Path(__file__).resolve().parents[1] / "upstream/browser-use-video-use/timeline_view.py"
    spec = spec_from_file_location("video_use_timeline_view", path)
    renderer = module_from_spec(spec)
    spec.loader.exec_module(renderer)
    windows_font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc"
    renderer.FONT_CANDIDATES.insert(0, str(windows_font))
    return renderer


def read_words(path, *, line_words_local=False):
    """Normalize supported word formats without inferring an unmarked line clock.

    For ``lines`` inputs the caller must confirm sentence-local word times via
    line_words_local=True, or the input must declare word_timebase='line-local'.
    An explicit declaration is still checked against each sentence's duration.
    """
    source = json.loads(path.read_text(encoding="utf-8-sig"))
    words = []

    def append(entries, offset=0, duration=None, metadata=None):
        if not isinstance(entries, list):
            raise ValueError("Expected a word list")
        for item in entries:
            if not isinstance(item, dict):
                raise ValueError("Each word must be an object")
            if item.get("type", "word") != "word":
                continue
            start, end = float(item["start"]), float(item["end"])
            label = item.get("text", item.get("w", item.get("word")))
            if not (isinstance(label, str) and label.strip() and 0 <= start <= end < math.inf):
                raise ValueError("Each word needs text and finite nonnegative times in seconds")
            if duration is not None and end > duration + .0001:
                raise ValueError("Sentence-local word extends beyond its line; check the timebase")
            words.append({"type": "word", "text": label, "start": offset + start,
                          "end": offset + end, **(metadata or {})})

    if isinstance(source, dict) and "lines" in source:
        declaration = source.get("word_timebase")
        if declaration not in (None, "line-local"):
            raise ValueError("Unsupported declared word_timebase; expected line-local")
        if not (line_words_local or declaration == "line-local"):
            raise ValueError("Line word clock is unmarked. Verify its generator, then use --line-words-local; do not guess")
        if not isinstance(source["lines"], list):
            raise ValueError("Expected a lines list")
        for index, line in enumerate(source["lines"]):
            offset = float(line["global_start"])
            duration = float(line["duration"]) if "duration" in line else float(line["global_end"]) - offset
            if not (math.isfinite(offset) and offset >= 0 and math.isfinite(duration) and duration >= 0
                    and math.isfinite(offset + duration)):
                raise ValueError("Each line needs a finite global_start and nonnegative duration/global_end")
            if "global_end" in line and not math.isclose(float(line["global_end"]), offset + duration, abs_tol=.0001):
                raise ValueError("Line duration and global_end disagree")
            append(line["words"], offset, duration,
                   {"line_id": str(line.get("id", index + 1)), "line_index": index,
                    "line_text": line.get("text", "")})
    elif isinstance(source, dict):
        keys = [key for key in ("words", "word_timestamps") if key in source]
        if len(keys) != 1:
            raise ValueError("Use exactly one words or word_timestamps list")
        append(source[keys[0]])
    else:
        append(source)
    return sorted(words, key=lambda w: w["start"])


def render(args):
    if not (args.video.is_file() and 0 <= args.start < args.end < math.inf and 2 <= args.frames <= 24):
        raise ValueError("Expected a local video, an increasing range in seconds, and 2 to 24 frames")
    if args.output.suffix.lower() != ".png" or args.output.exists():
        raise ValueError("Choose a new output PNG path")
    source = Path(local_file(args.video))
    video, audio_tracks, _ = inspect(str(source))
    duration = video.get("duration")
    if duration and duration != "N/A" and args.end >= float(duration):
        raise ValueError("The last sample must be inside the video; choose an earlier end time")
    words = read_words(args.words, line_words_local=getattr(args, "line_words_local", False)) if args.words else None
    renderer = load_renderer()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.output.parent) as staging:
        work = Path(staging)
        transcript = None
        if words is not None:
            transcript = work / "words.json"
            # ASCII escapes keep the original helper portable across Windows code pages.
            transcript.write_text(json.dumps({"words": words}, ensure_ascii=True), encoding="ascii")
        preview = work / "review.png"
        previous_temp = tempfile.tempdir
        try:
            tempfile.tempdir = str(work.resolve())
            renderer.render_timeline(source, args.start, args.end, preview, args.frames, transcript)
        finally:
            tempfile.tempdir = previous_temp
        if not audio_tracks:
            # The upstream renderer draws a flat envelope for silent media. Mark that case explicitly.
            from PIL import Image, ImageDraw
            with Image.open(preview) as original:
                sheet = original.copy()
            ImageDraw.Draw(sheet).text((50, sheet.height - 27), "No audio track",
                                       font=renderer.load_font(15), fill=renderer.FG)
            sheet.save(preview)
        with preview.open("rb") as prepared, args.output.open("xb") as output:
            shutil.copyfileobj(prepared, output)
    print(args.output.resolve())
    step = (args.end - args.start) / (args.frames - 1)
    print("Frame samples (s):", ", ".join(f"{args.start + step*i:.3f}" for i in range(args.frames)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("start", type=float)
    parser.add_argument("end", type=float)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--words", type=Path, help="optional word timings on the same clock as this video")
    parser.add_argument("--line-words-local", action="store_true", help="confirm words in a lines file use sentence-local seconds, then add global_start")
    parser.add_argument("--frames", type=int, default=6)
    args = parser.parse_args()
    try:
        render(args)
    except (ValueError, KeyError, TypeError, AttributeError, ImportError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Review window unavailable: {error}\n")


if __name__ == "__main__":
    main()
