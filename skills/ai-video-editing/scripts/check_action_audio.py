"""Read-only action/SFX window checks using stdlib and an existing FFmpeg.

Cues JSON: {"timebase":"program", "cues":[{"id":"click", "seconds":1.2,
"origin":"added", "tolerance_s":0.12, "search_s":0.5}]}.
Origins: added (default), existing (already in original), silent (no added SFX).
Existing {"events":[{"time":1.2,...}]} mix reports are also accepted; time must
be absolute program time. Shot-relative "at" is deliberately not inferred.
All input tracks must be aligned to the PROGRAM timeline, starting at zero.
For source-time cues use --time-map with source_duration_s and kept_spans_s;
only same-order cuts at unchanged speed are supported. No audio is written.

This detects thresholded sample energy/onsets, NOT sound identity, masking,
perceived loudness, true peak, copyright, or whether a sound fits an action.
"""

import argparse
from array import array
from collections import Counter, deque
from dataclasses import dataclass
import json
import math
from pathlib import Path
import subprocess
import sys
import threading

from map_cues import read_plan

RATE = 16000
CHANNELS = 2  # Preserve opposing channels; mono downmix could cancel a click.
FRAME_SAMPLES = 160  # 10 ms measurement bins, not frame-accurate AV sync.
BIN_S = FRAME_SAMPLES / RATE


def number(value, label, minimum=None, maximum=None):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value)):
        raise ValueError(f"{label} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{label} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{label} must be <= {maximum}")
    return float(value)


def db(value):
    return round(20 * math.log10(value), 2) if value > 0 else None


@dataclass
class Track:
    path: str
    peaks: list
    powers: list
    sample_frames: int

    @property
    def duration_s(self):
        return self.sample_frames / RATE


def decode_track(path, ffmpeg="ffmpeg", timeout_s=300):
    """Stream decoded PCM into compact bin statistics; never save PCM to disk."""
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError(f"Audio input does not exist: {path}")
    command = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-nostdin",
               "-protocol_whitelist", "file,pipe", "-i", str(path), "-map", "0:a:0", "-vn", "-ac", str(CHANNELS),
               "-ar", str(RATE), "-f", "f32le", "pipe:1"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    errors = deque(maxlen=8)

    def read_errors():
        while True:
            chunk = process.stderr.read(1024)
            if not chunk:
                break
            errors.append(chunk)

    reader = threading.Thread(target=read_errors, daemon=True)
    reader.start()
    expired = threading.Event()

    def expire():
        expired.set()
        process.kill()

    timer = threading.Timer(timeout_s, expire)
    timer.daemon = True
    timer.start()
    peaks, powers, samples = [], [], 0
    try:
        while True:
            raw = process.stdout.read(FRAME_SAMPLES * CHANNELS * 4)
            if not raw:
                break
            if len(raw) % (CHANNELS * 4):
                raise ValueError("FFmpeg returned an incomplete PCM sample")
            values = array("f")
            values.frombytes(raw)
            if sys.byteorder != "little":
                values.byteswap()
            if any(not math.isfinite(value) for value in values):
                raise ValueError("Decoded audio contains non-finite samples")
            peaks.append(max(abs(value) for value in values))
            powers.append(sum(value * value for value in values) / len(values))
            samples += len(values) // CHANNELS
        process.wait()
        reader.join()
        if expired.is_set():
            raise ValueError(f"Audio decode exceeded {timeout_s} seconds")
        if process.returncode:
            detail = b"".join(errors).decode("utf-8", errors="replace").strip()
            raise ValueError(f"FFmpeg could not decode {path.name}: {detail}")
        if not samples:
            raise ValueError(f"Audio input has no decoded samples: {path.name}")
    finally:
        timer.cancel()
        if process.poll() is None:
            process.kill()
        process.wait()
        reader.join(timeout=5)
        process.stdout.close()
        process.stderr.close()
    return Track(str(path), peaks, powers, samples)


def load_cues(path, time_map=None):
    manifest = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict):
        raise ValueError("Cues JSON must be an object")
    timebase = manifest.get("timebase", "program")
    if timebase not in ("program", "source"):
        raise ValueError("timebase must be program or source")
    if timebase == "source" and time_map is None:
        raise ValueError("Source-time cues require --time-map; do not guess edited timestamps")
    if timebase == "program" and time_map is not None:
        raise ValueError("--time-map is only valid with source-time cues")
    duration, spans = read_plan(time_map) if time_map else (None, None)
    raw_cues = manifest.get("cues", manifest.get("events"))
    if not isinstance(raw_cues, list) or not raw_cues:
        raise ValueError("cues must be a non-empty list")
    cues, identifiers = [], set()
    for ordinal, raw in enumerate(raw_cues, 1):
        if not isinstance(raw, dict):
            raise ValueError(f"Cue {ordinal} must be an object")
        cue_id = raw.get("id", str(ordinal))
        if not isinstance(cue_id, str) or not cue_id.strip() or cue_id in identifiers:
            raise ValueError(f"Cue {ordinal} needs a unique non-empty string id")
        identifiers.add(cue_id)
        seconds = number(raw.get("seconds", raw.get("time")), f"{cue_id}.seconds", minimum=0)
        tolerance = number(raw.get("tolerance_s", 0.12), f"{cue_id}.tolerance_s", 0.01, 5)
        search = number(raw.get("search_s", 0.5), f"{cue_id}.search_s", tolerance, 30)
        origin = raw.get("origin", "added")
        if origin not in ("added", "existing", "silent"):
            raise ValueError(f"{cue_id}.origin must be added, existing, or silent")
        cue = {"id": cue_id, "input_seconds": seconds, "origin": origin,
               "tolerance_s": tolerance, "search_s": search, "program_seconds": seconds}
        for key in ("label", "shot", "type"):
            if isinstance(raw.get(key), str):
                cue[key] = raw[key]
        if spans is not None:
            cue["program_seconds"] = None
            cue["mapping_status"] = "removed"
            if seconds >= duration:
                cue["mapping_status"] = "source_out_of_range"
            else:
                cursor = 0.0
                for start, end in spans:
                    if start <= seconds < end:  # half-open ranges, matching cut semantics
                        cue["program_seconds"] = cursor + seconds - start
                        cue["mapping_status"] = "mapped"
                        break
                    cursor += end - start
        cues.append(cue)
    return timebase, cues


def measure(track, seconds, tolerance, search, threshold):
    if seconds >= track.duration_s:
        return {"status": "track_out_of_range", "duration_s": round(track.duration_s, 6)}
    start, end = max(0, seconds - search), min(track.duration_s, seconds + search)
    lower = max(0, seconds - tolerance)
    upper = min(track.duration_s, seconds + tolerance)
    first = max(0, int(start / BIN_S))
    stop = min(len(track.peaks), math.ceil(end / BIN_S))
    inside = [index for index in range(first, stop)
              if index * BIN_S < upper and (index + 1) * BIN_S > lower]
    active = [index for index in range(first, stop) if track.peaks[index] >= threshold]
    onsets = [index * BIN_S for index in active
              if index == 0 or track.peaks[index - 1] < threshold]
    onset = min(onsets, key=lambda time: abs(time - seconds)) if onsets else None
    in_window = any(track.peaks[index] >= threshold for index in inside)
    if onset is not None and abs(onset - seconds) <= tolerance + BIN_S:
        status = "onset_in_window"
    elif in_window:
        status = "activity_without_aligned_onset"
    elif onset is not None:
        status = "onset_outside_window"
    else:
        status = "no_activity"
    window_peak = max((track.peaks[index] for index in inside), default=0)
    power = sum(track.powers[index] for index in inside) / len(inside) if inside else 0
    return {"status": status, "window_s": [round(lower, 6), round(upper, 6)],
            "window_clipped_to_track": seconds - tolerance < 0 or seconds + tolerance > track.duration_s,
            "search_window_s": [round(start, 6), round(end, 6)],
            "peak_dbfs": db(window_peak), "rms_dbfs": db(math.sqrt(power)),
            "nearest_onset_s": round(onset, 6) if onset is not None else None,
            "onset_offset_s": round(onset - seconds, 6) if onset is not None else None,
            "activity_in_window": in_window}


def check(cues_path, *, sfx=None, original=None, mix=None, time_map=None,
          threshold_dbfs=-45, ffmpeg="ffmpeg", decode_timeout_s=300):
    threshold_dbfs = number(threshold_dbfs, "threshold_dbfs", -120, 0)
    decode_timeout_s = number(decode_timeout_s, "decode_timeout_s", 1)
    timebase, cues = load_cues(cues_path, time_map)
    inputs = {name: path for name, path in (("sfx", sfx), ("original", original), ("mix", mix)) if path}
    if not inputs:
        raise ValueError("Provide at least one of --sfx, --original, --mix")
    cache, tracks = {}, {}
    for name, path in inputs.items():
        key = str(Path(path).resolve())
        if key not in cache:
            cache[key] = decode_track(key, ffmpeg, decode_timeout_s)
        tracks[name] = cache[key]
    threshold = 10 ** (threshold_dbfs / 20)
    results = []
    for cue in cues:
        result = dict(cue)
        seconds = cue["program_seconds"]
        if seconds is None:
            result.update(status=cue["mapping_status"], needs_review=True, measurements={})
            results.append(result)
            continue
        measurements = {name: measure(track, seconds, cue["tolerance_s"], cue["search_s"], threshold)
                        for name, track in tracks.items()}
        result["measurements"] = measurements
        target_name = "original" if cue["origin"] == "existing" else "sfx"
        target = measurements.get(target_name)
        status, review = "unverifiable_without_separate_track", True
        if target:
            status = target["status"]
            review = status != "onset_in_window"
            if cue["origin"] == "silent":
                status = "unexpected_added_activity" if target.get("activity_in_window") else "no_added_activity"
                review = status != "no_added_activity"
                if target["status"] == "track_out_of_range":
                    status, review = "track_out_of_range", True
        if cue["origin"] == "existing" and "sfx" in measurements:
            if measurements["sfx"].get("activity_in_window"):
                status, review = "possible_duplicate_added_activity", True
        if any(value["status"] == "track_out_of_range" for value in measurements.values()):
            status, review = "track_out_of_range", True
        elif (cue["origin"] != "silent" and target
              and target["status"] == "onset_in_window" and "mix" in measurements
              and not measurements["mix"].get("activity_in_window")):
            status, review = "final_mix_has_no_activity", True
        result.update(status=status, needs_review=review)
        results.append(result)
    # A single independent stem onset cannot establish two distinct action sounds.
    groups = {}
    for result in results:
        if result["status"] == "onset_in_window":
            target_name = "original" if result["origin"] == "existing" else "sfx"
            onset = result["measurements"][target_name]["nearest_onset_s"]
            groups.setdefault((target_name, onset), []).append(result)
    for group in groups.values():
        if len(group) > 1:
            for result in group:
                result.update(status="shared_onset_needs_review", needs_review=True)
    return {"schema_version": 1, "input_timebase": timebase,
            "measurement": {"sample_rate_hz": RATE, "channels": CHANNELS,
                            "bin_s": BIN_S, "activity_threshold_dbfs": threshold_dbfs,
                            "timing_uncertainty_s": BIN_S},
            "scope": "Thresholded sample energy/onsets in aligned program-time tracks",
            "listening_required": True,
            "limitations": ["Energy is not sound identity or proof a cue survived the final mix.",
                            "Mixed speech/music cannot establish whether a specific SFX exists.",
                            "Audibility, masking, fit, AV sync, true peak and loudness require other checks.",
                            "Source mapping supports same-order cuts only, without speed changes.",
                            "Tracks must start at program zero; container timestamps are not alignment proof."],
            "tracks": {name: {"path": track.path, "duration_s": round(track.duration_s, 6)}
                       for name, track in tracks.items()},
            "summary": {"cues": len(results), "needs_review": sum(item["needs_review"] for item in results),
                        "statuses": dict(Counter(item["status"] for item in results))},
            "cues": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cues", required=True, help="UTF-8 cues JSON path")
    parser.add_argument("--sfx", help="Independent ADDED SFX stem, on the program timeline")
    parser.add_argument("--original", help="Original sound stem, on the program timeline")
    parser.add_argument("--mix", help="Optional final mix/video; energy is not SFX attribution")
    parser.add_argument("--time-map", help="Same-order constant-speed rough_cut_plan.py JSON")
    parser.add_argument("--threshold-dbfs", type=float, default=-45)
    parser.add_argument("--ffmpeg", default="ffmpeg", help="Existing FFmpeg executable")
    parser.add_argument("--decode-timeout-s", type=float, default=300)
    args = parser.parse_args()
    try:
        report = check(args.cues, sfx=args.sfx, original=args.original, mix=args.mix,
                       time_map=args.time_map, threshold_dbfs=args.threshold_dbfs,
                       ffmpeg=args.ffmpeg, decode_timeout_s=args.decode_timeout_s)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f"Action audio check unavailable: {error}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 1 if report["summary"]["needs_review"] else 0


if __name__ == "__main__":
    sys.exit(main())
