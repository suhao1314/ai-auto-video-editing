"""Read a local video export and optionally check its SRT and stream-copied picture."""

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys


def run_tool(args, *, read_log=False):
    result = subprocess.run(args, capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise ValueError(result.stderr.strip()[-1500:] or f"{args[0]} exited {result.returncode}")
    return result.stderr if read_log else result.stdout


def local_file(path):
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError(f"Expected a local file: {path}")
    return str(resolved)


def inspect(path):
    args = ["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
            "-show_format", "-show_streams", "-show_data_hash", "sha256", "-of", "json", path]
    probe = json.loads(run_tool(args))
    streams = probe["streams"]
    pictures = [s for s in streams if s["codec_type"] == "video"
                and not s.get("disposition", {}).get("attached_pic")]
    if not pictures:
        raise ValueError(f"No video stream in {Path(path).name}")
    video = next((s for s in pictures if s.get("disposition", {}).get("default")), pictures[0])
    audio = [s for s in streams if s["codec_type"] == "audio"]
    return video, audio, probe["format"]


def decode(path, video_index):
    args = ["ffmpeg", "-nostdin", "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe",
            "-i", path, "-map", f"0:{video_index}", "-map", "0:a?", "-fps_mode", "passthrough",
            "-progress", "pipe:1", "-nostats", "-f", "null", "-"]
    progress = run_tool(args)
    frames = re.findall(r"^frame=(\d+)\s*$", progress, re.MULTILINE)
    if "progress=end" not in progress or not frames or int(frames[-1]) < 1:
        raise ValueError("Full decode returned no video frames")
    return int(frames[-1])


def measure_mix(path, tracks):
    if not tracks:
        raise ValueError("Loudness measurement requires an audio track")
    track = next((s for s in tracks if s.get("disposition", {}).get("default")), tracks[0])
    args = ["ffmpeg", "-nostdin", "-nostats", "-hide_banner", "-v", "info",
            "-protocol_whitelist", "file,pipe", "-i", path, "-map", f"0:{track['index']}",
            "-af", "loudnorm=print_format=json", "-f", "null", "-"]
    log = run_tool(args, read_log=True)
    measurements = re.search(r'(\{\s*"input_i"\s*:[^{}]*\})', log)
    if not measurements:
        raise ValueError("FFmpeg did not return an audio measurement")
    data = json.loads(measurements.group(1))
    return {"stream_index": track["index"], "integrated_lufs": data["input_i"],
            "true_peak_dbtp": data["input_tp"]}


SRT_TIME = r"(\d{2,}):([0-5]\d):([0-5]\d)[,.](\d{3})"
SRT_RANGE = re.compile(SRT_TIME + r"\s*-->\s*" + SRT_TIME + r"(?:\s+.*)?")


def milliseconds(parts):
    h, m, s, ms = map(int, parts)
    return ((h * 60 + m) * 60 + s) * 1000 + ms


def check_srt(path, length, tolerance):
    text = Path(local_file(path)).read_text(encoding="utf-8-sig").strip()
    blocks = re.split(r"\n[ \t]*\n+", text)
    previous_start = previous_end = -1
    overlap_count = 0
    last_end = 0
    for number, block in enumerate(blocks, 1):
        lines = block.splitlines()
        if lines and lines[0].strip().isdigit():
            lines = lines[1:]
        match = SRT_RANGE.fullmatch(lines[0].strip()) if lines else None
        if not match or not any(line.strip() for line in lines[1:]):
            raise ValueError(f"SRT cue {number}: missing valid timing or caption")
        start = milliseconds(match.groups()[:4])
        end = milliseconds(match.groups()[4:])
        if start < previous_start or start >= end or end > (length + tolerance) * 1000:
            raise ValueError(f"SRT cue {number}: out of order, empty duration or beyond export ({end} ms)")
        overlap_count += int(start < previous_end)
        previous_start, previous_end = start, max(previous_end, end)
        last_end = max(last_end, end)
    return {"cues": len(blocks), "last_end_ms": last_end, "overlapping_cues": overlap_count}


def picture_fingerprint(path, video):
    # Include codec configuration and presentation data. Normalize equivalent container timescales.
    fields = ("codec_name", "extradata_hash", "width", "height", "sample_aspect_ratio",
              "pix_fmt", "color_space", "color_range", "color_primaries", "color_transfer", "field_order")
    description = [video.get(key) for key in fields] + [video.get("side_data_list", [])]
    digest = hashlib.sha256(json.dumps(description, sort_keys=True).encode("utf-8"))
    args = ["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-select_streams",
            str(video["index"]), "-show_packets", "-show_data_hash", "sha256", "-show_entries",
            "packet=pts,dts,duration,data_hash", "-of", "json", path]
    timebase = Fraction(video["time_base"])
    packets = json.loads(run_tool(args)).get("packets", [])
    if not packets:
        raise ValueError("No video packet hashes available for picture comparison")
    for packet in packets:
        if not packet.get("data_hash"):
            raise ValueError("Video packet without a hash in " + Path(path).name)
        times = [packet.get(key, "N/A") for key in ("pts", "dts", "duration")]
        times = [str(int(value) * timebase) if value != "N/A" else value for value in times]
        digest.update(("|".join(times + [packet["data_hash"]]) + "\n").encode("ascii"))
    return digest.hexdigest()


def check(args):
    path = local_file(args.export)
    video, audio, container = inspect(path)
    if args.require_audio and not audio:
        raise ValueError("Expected an audio track")
    seconds = float(container.get("duration") or video.get("duration") or "nan")
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("Export duration is unavailable")
    fps = Fraction(video.get("avg_frame_rate") or "0") if video.get("avg_frame_rate") != "0/0" else 0
    tolerance = float(1 / fps) if fps > 0 else 0.04
    if args.expect_duration is not None:
        if not math.isfinite(args.expect_duration) or args.expect_duration <= 0:
            raise ValueError("Expected duration must be positive and finite")
        if abs(seconds - args.expect_duration) > tolerance + 0.001:
            raise ValueError(f"Expected {args.expect_duration} s, got {seconds} s")
    result = {"file": Path(path).name, "duration_s": seconds, "size": [video["width"], video["height"]],
              "fps_average": str(fps), "decoded_video_frames": decode(path, video["index"]),
              "audio_tracks": [{"codec": track["codec_name"], "channels": track.get("channels"),
                                "duration_s": track.get("duration")} for track in audio]}
    if args.srt:
        result["srt"] = check_srt(args.srt, seconds, tolerance + 0.001)
    if args.loudness:
        result["audio_measurement"] = measure_mix(path, audio)
    if args.same_picture_as:
        base = local_file(args.same_picture_as)
        reference_video, _, _ = inspect(base)
        actual = picture_fingerprint(path, video)
        if actual != picture_fingerprint(base, reference_video):
            raise ValueError("Picture stream or timestamps differ from " + Path(base).name)
        result["matching_picture_sha256"] = actual
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    parser.add_argument("--srt", type=Path, help="UTF-8 subtitles timed against the final export")
    parser.add_argument("--require-audio", action="store_true", help="Fail if the file has no audio track")
    parser.add_argument("--loudness", action="store_true", help="Measure integrated LUFS and true peak on the default audio track")
    parser.add_argument("--expect-duration", type=float, help="Expected seconds, allowing one average frame")
    parser.add_argument("--same-picture-as", type=Path, help="Reference with the same compressed video and timing")
    args = parser.parse_args()
    try:
        result = check(args)
    except (OSError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
