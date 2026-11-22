"""Use the pinned talking-head planner to propose source-time cuts; write JSON to stdout."""

import argparse
from importlib.util import module_from_spec, spec_from_file_location
import json
import math
from pathlib import Path
import sys


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def seconds(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("Expected a finite time in seconds")
    return float(value)


def checked_range(start, end, total):
    start, end = seconds(start), seconds(end)
    if not 0 <= start < end <= total + 0.001:
        raise ValueError(f"Invalid source interval {start}–{end} for {total} s")
    return start, min(end, total)


def protect(proposed, protected, fps, total):
    # Include a whole boundary frame if a user's range starts or ends between frames.
    spans = list(proposed)
    spans.extend((math.floor(s * fps) / fps, math.ceil(e * fps) / fps) for s, e in protected)
    merged = []
    for s, e in sorted(spans):
        s, e = max(0, s), min(total, e)
        if e <= s:
            continue
        if merged and s <= merged[-1][1] + 1e-8:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def plan(spec_file, transcript_file):
    settings = read_json(spec_file)
    media = (spec_file.parent / settings["video"]).resolve(strict=True)
    if not media.is_file():
        raise ValueError("Expected a local media file")
    vendor_path = Path(__file__).resolve().parents[1] / "upstream/social-media-video-editing/edit_video.py"
    vendor_spec = spec_from_file_location("talking_head_editor", vendor_path)
    editor = module_from_spec(vendor_spec)
    vendor_spec.loader.exec_module(editor)
    editor.check_tools()
    _, _, total, fps = editor.probe(str(media))
    if not (math.isfinite(total) and math.isfinite(fps) and total > 0 and fps > 0):
        raise ValueError("No usable video duration or frame rate")
    words = read_json(transcript_file)["words"]
    if not isinstance(words, list) or not words:
        raise ValueError("A timed transcript with a nonempty words list is required")
    last_start = -1
    for word in words:
        if not isinstance(word["w"], str) or not word["w"].strip():
            raise ValueError("Empty transcript word")
        start, end = checked_range(word["start"], word["end"], total)
        if start < last_start:
            raise ValueError("Transcript must be in source-time order")
        word.update(start=start, end=end)
        last_start = start
    protected = [checked_range(s, e, total) for s, e in settings.get("keep", [])]
    for item in settings.get("cut", []):
        checked_range(item[0], item[1], total)
        if len(item) != 3 or not isinstance(item[2], str) or not item[2].strip():
            raise ValueError("A proposed manual cut needs [start, end, reason]")
    # English filler and retake heuristics are opt-in for multilingual recordings.
    for key, default in (("style", "podcast"), ("fillers", []), ("stutters", False),
                         ("retakes", False), ("voiced_gaps", False)):
        settings.setdefault(key, default)
    if settings["style"] not in editor.PRESETS:
        raise ValueError("Unknown rough-cut style")
    db, noise = editor.audio_energy(str(media))
    black, changes = editor.visual_events(str(media))
    marked, retakes = editor.mark(words, settings)
    proposed, log = editor.plan_spans(words, marked, settings, total, fps, db, noise, black, changes)
    kept = protect(proposed, protected, fps, total)
    cuts = []
    cursor = 0.0
    for start, end in kept + [[total, total]]:
        if start - cursor > 1e-8:
            reasons = [r for s, e, r in settings.get("cut", []) if s < start and e > cursor]
            reasons += [r for s, e, r, _ in log if s < start and e > cursor]
            excerpt = [w["w"] for w in words if w["start"] < start and w["end"] > cursor]
            cuts.append({"source_s": [round(cursor, 6), round(start, 6)],
                         "reasons": list(dict.fromkeys(reasons)) or ["check boundary"],
                         "words": excerpt})
        cursor = end
    return {"source": media.name, "source_duration_s": total, "proposed_duration_s":
            round(sum(e - s for s, e in kept), 6), "keep_requested_s": protected,
            "kept_spans_s": [[round(s, 6), round(e, 6)] for s, e in kept],
            "proposed_removals": cuts, "possible_retakes_for_review": retakes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("transcript", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(plan(args.spec, args.transcript), indent=2, ensure_ascii=False))
    except (OSError, ValueError, TypeError, KeyError, IndexError) as error:
        parser.exit(1, f"Rough cut unavailable: {error}\n")


if __name__ == "__main__":
    main()
