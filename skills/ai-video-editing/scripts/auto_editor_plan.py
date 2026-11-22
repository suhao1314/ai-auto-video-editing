"""Turn an Auto-Editor linear timeline into this skill's read-only rough-cut plan.

Only same-source, forward, normal-speed cuts are representable.  It is intended
for reviewing Auto-Editor's candidate silence removals before an editor renders
or uses them to remap captions with map_cues.py.
"""

import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import subprocess
import sys


EPSILON = 0.000001


def number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)


def timebase(value, label):
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a rational string such as 30/1")
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError(f"{label} is not a valid rational") from error
    if result <= 0:
        raise ValueError(f"{label} must be positive")
    return result


def absolute_source(timeline_path, value, source_root=None):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Timeline has no usable source path")
    source = Path(value)
    if source.is_absolute():
        return source.resolve()
    roots = [timeline_path.parent, Path.cwd()]
    if source_root is not None:
        roots.insert(1, Path(source_root))
    matches = []
    for root in roots:
        candidate = (root / source).resolve()
        if candidate.is_file() and candidate not in matches:
            matches.append(candidate)
    if len(matches) > 1:
        raise ValueError(
            "Relative timeline source resolves to more than one local file. "
            "Pass --source-root or use an absolute source path."
        )
    if matches:
        return matches[0]
    # Parsing a hand-written timeline can work before its source is copied in.
    # plan() always probes the chosen path before it produces a usable proposal.
    return (timeline_path.parent / source).resolve()


def normal_effect(effect):
    return effect == [] or effect in (["speed:1"], ["speed:1.0"], ["nil"])


def clip_range(start, end, rate, label):
    start, end = number(start, f"{label} start"), number(end, f"{label} end")
    if start < 0 or end <= start:
        raise ValueError(f"{label} must have a nonempty nonnegative range")
    return [float(Fraction(str(start)) / rate), float(Fraction(str(end)) / rate)]


def merge_spans(spans):
    output = []
    for start, end in spans:
        if output and start < output[-1][1] - EPSILON:
            raise ValueError("Timeline reorders or overlaps source ranges; it cannot be handed to map_cues.py")
        if output and abs(start - output[-1][1]) <= EPSILON:
            output[-1][1] = end
        else:
            output.append([start, end])
    return output


def v1(data, timeline_path, fallback_rate=None, source_root=None):
    if "timebase" in data:
        rate = timebase(data["timebase"], "v1 timebase")
    elif fallback_rate is not None:
        rate = fallback_rate
    else:
        raise ValueError("v1 has no timebase; probe the original source first")
    source = absolute_source(timeline_path, data.get("source"), source_root)
    chunks = data.get("chunks")
    if not isinstance(chunks, list):
        raise ValueError("v1 chunks must be a list")
    expected, kept = 0.0, []
    for index, chunk in enumerate(chunks, 1):
        if not isinstance(chunk, list) or len(chunk) != 3:
            raise ValueError(f"v1 chunk {index} must be [start, end, speed]")
        start, end = clip_range(chunk[0], chunk[1], rate, f"v1 chunk {index}")
        if abs(start - expected) > EPSILON:
            raise ValueError("v1 chunks must cover source time continuously from zero")
        expected = end
        speed = number(chunk[2], f"v1 chunk {index} speed")
        if abs(speed - 1.0) <= EPSILON:
            kept.append([start, end])
        elif abs(speed) <= EPSILON or speed >= 99999:
            continue
        else:
            raise ValueError("v1 speed changes cannot be represented by a same-speed rough-cut plan")
    return source, rate, merge_spans(kept), expected


def v2(data, timeline_path, source_root=None):
    rate = timebase(data.get("tb"), "v2 tb")
    source = absolute_source(timeline_path, data.get("source"), source_root)
    effects, clips = data.get("effects"), data.get("clips")
    if not isinstance(effects, list) or not isinstance(clips, list):
        raise ValueError("v2 needs effects and clips lists")
    previous_source_end, kept = 0.0, []
    for index, clip in enumerate(clips, 1):
        if not isinstance(clip, list) or len(clip) != 3 or not isinstance(clip[2], int):
            raise ValueError(f"v2 clip {index} must be [start, end, effect-index]")
        start, end = clip_range(clip[0], clip[1], rate, f"v2 clip {index}")
        if start < previous_source_end - EPSILON:
            raise ValueError("v2 clips must remain in source order and must not overlap")
        previous_source_end = end
        effect_index = clip[2]
        if not 0 <= effect_index < len(effects) or not isinstance(effects[effect_index], list):
            raise ValueError(f"v2 clip {index} references an unknown effect")
        effect = effects[effect_index]
        if effect == ["cut"]:
            continue
        if normal_effect(effect):
            kept.append([start, end])
            continue
        raise ValueError("v2 effects other than normal-speed play or cut cannot be represented")
    return source, rate, merge_spans(kept), previous_source_end


def v3(data, timeline_path, source_root=None):
    rate = timebase(data.get("timebase"), "v3 timebase")
    video_layers = data.get("v")
    if not isinstance(video_layers, list) or len(video_layers) != 1 or not isinstance(video_layers[0], list):
        raise ValueError("v3 needs exactly one video layer")
    if data.get("transitions"):
        raise ValueError("v3 transitions cannot be represented by a plain rough-cut plan")
    clips = video_layers[0]
    if not clips:
        raise ValueError("v3 base layer has no clips")
    source = None
    previous_source_end, expected_program_start, kept = 0.0, 0.0, []
    for index, clip in enumerate(clips, 1):
        if not isinstance(clip, dict):
            raise ValueError(f"v3 video clip {index} must be an object")
        if clip.get("effects") not in (None, [], ["speed:1"], ["speed:1.0"], ["nil"]):
            raise ValueError("v3 effects other than normal-speed play cannot be represented")
        if clip.get("stream") != 0:
            raise ValueError("v3 nonzero source video streams need separate editorial review")
        clip_source = absolute_source(timeline_path, clip.get("src"), source_root)
        if source is None:
            source = clip_source
        elif clip_source != source:
            raise ValueError("v3 multiple sources cannot be represented by a rough-cut plan")
        output_start = number(clip.get("start"), f"v3 clip {index} start")
        duration = number(clip.get("dur"), f"v3 clip {index} duration")
        offset = number(clip.get("offset"), f"v3 clip {index} offset")
        if output_start < 0 or duration <= 0 or offset < 0:
            raise ValueError(f"v3 clip {index} has invalid start, duration, or offset")
        if abs(output_start - expected_program_start) > EPSILON:
            raise ValueError("v3 clips must be contiguous in programme time")
        expected_program_start = output_start + duration
        start, end = float(Fraction(str(offset)) / rate), float(Fraction(str(offset + duration)) / rate)
        if start < previous_source_end - EPSILON:
            raise ValueError("v3 source ranges must remain in source order")
        previous_source_end = end
        kept.append([start, end])
    audio_layers = data.get("a")
    if not isinstance(audio_layers, list) or len(audio_layers) != 1 or not isinstance(audio_layers[0], list):
        raise ValueError("v3 needs exactly one audio layer aligned with the base video")
    audio_clips = audio_layers[0]
    if len(audio_clips) != len(clips):
        raise ValueError("v3 audio clips must align one-to-one with base video clips")
    for index, (video_clip, audio_clip) in enumerate(zip(clips, audio_clips), 1):
        if not isinstance(audio_clip, dict):
            raise ValueError(f"v3 audio clip {index} must be an object")
        if audio_clip.get("effects") not in (None, [], ["speed:1"], ["speed:1.0"], ["nil"]):
            raise ValueError("v3 audio effects cannot be represented by a rough-cut plan")
        audio_source = absolute_source(timeline_path, audio_clip.get("src"), source_root)
        fields = ("start", "dur", "offset")
        if audio_source != source or any(audio_clip.get(field) != video_clip.get(field) for field in fields):
            raise ValueError("v3 audio must use the same source, programme position, and source offset as video")
    return source, rate, merge_spans(kept), previous_source_end


def parse_timeline(data, timeline_path, fallback_rate=None, source_root=None):
    if not isinstance(data, dict):
        raise ValueError("Timeline must be a JSON object")
    version = str(data.get("version", ""))
    if version == "1":
        source, rate, kept, covered = v1(data, timeline_path, fallback_rate, source_root)
        covers_source = True
    elif version == "2":
        source, rate, kept, covered = v2(data, timeline_path, source_root)
        covers_source = False
    elif version == "3":
        source, rate, kept, covered = v3(data, timeline_path, source_root)
        covers_source = False
    else:
        raise ValueError("Only Auto-Editor v1, v2, and plain single-layer v3 timelines are supported")
    return version, source, rate, kept, covered, covers_source


def probe_media(source):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,avg_frame_rate", "-of", "json", str(source)],
        check=True, capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    raw_duration = data["format"]["duration"]
    try:
        duration = float(raw_duration)
    except (TypeError, ValueError) as error:
        raise ValueError("source duration must be a finite number") from error
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Source has no positive duration")
    video = next((stream for stream in data.get("streams", []) if stream.get("codec_type") == "video"), None)
    if not video or not video.get("avg_frame_rate") or video["avg_frame_rate"] == "0/0":
        raise ValueError("Source needs a video frame rate to resolve an old v1 timeline without timebase")
    return duration, timebase(video["avg_frame_rate"], "source frame rate")


def source_candidate(data, timeline_path, source_root=None):
    version = str(data.get("version", ""))
    if version in ("1", "2"):
        return absolute_source(timeline_path, data.get("source"), source_root)
    if version == "3":
        layers = data.get("v")
        if isinstance(layers, list) and len(layers) == 1 and isinstance(layers[0], list) and layers[0]:
            first = layers[0][0]
            if isinstance(first, dict):
                return absolute_source(timeline_path, first.get("src"), source_root)
    raise ValueError("Timeline has no source that can be probed")


def plan(timeline_path, source_root=None):
    timeline_path = Path(timeline_path).resolve(strict=True)
    data = json.loads(timeline_path.read_text(encoding="utf-8-sig"))
    candidate = source_candidate(data, timeline_path, source_root)
    duration, fallback_rate = probe_media(candidate)
    version, source, rate, kept, covered, covers_source = parse_timeline(
        data, timeline_path, fallback_rate, source_root
    )
    if source != candidate:
        raise ValueError("Timeline source changed while parsing")
    frame_seconds = float(1 / rate)
    if covers_source and abs(covered - duration) > frame_seconds + EPSILON:
        raise ValueError("Timeline does not cover the source duration within one frame")
    if not covers_source and covered > duration + frame_seconds + EPSILON:
        raise ValueError("v3 clip points beyond the source duration")
    normalized = [[round(max(0.0, start), 6), round(min(duration, end), 6)] for start, end in kept]
    removals, cursor = [], 0.0
    for start, end in normalized + [[duration, duration]]:
        if start > cursor + EPSILON:
            removals.append({"source_s": [round(cursor, 6), round(start, 6)],
                             "reasons": [f"auto-editor v{version} marked this source range inactive"]})
        cursor = end
    return {
        "source": str(source),
        "source_duration_s": round(duration, 6),
        "proposed_duration_s": round(sum(end - start for start, end in normalized), 6),
        "kept_spans_s": normalized,
        "proposed_removals": removals,
        "auto_editor": {
            "timeline_version": version,
            "timebase": f"{rate.numerator}/{rate.denominator}",
            "adapter_scope": "single-source, forward, normal-speed cuts only",
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timeline", type=Path, help="Auto-Editor .v1, .v2, or eligible .v3 JSON")
    parser.add_argument("--source-root", type=Path,
                        help="directory used to resolve a relative source in the timeline")
    args = parser.parse_args()
    try:
        print(json.dumps(plan(args.timeline, args.source_root), ensure_ascii=False, indent=2))
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Auto-Editor plan unavailable: {error}\n")


if __name__ == "__main__":
    main()
