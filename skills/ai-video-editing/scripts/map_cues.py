"""Map an original SRT onto a same-order, constant-speed rough-cut timeline.

This is a read-only review aid. It does not rewrite subtitle text or create an SRT
for the edited program. A cue crossing a removed range needs an editor's decision.
"""

import argparse
import json
import math
from pathlib import Path
import re
import sys

from check_export import SRT_RANGE, milliseconds

EPSILON = 0.000001


def finite_seconds(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number of seconds")
    return float(value)


def rounded(value):
    return round(value, 6)


def read_plan(path_or_stdin):
    raw = sys.stdin.read() if path_or_stdin == "-" else Path(path_or_stdin).read_text(encoding="utf-8-sig")
    plan = json.loads(raw)
    if not isinstance(plan, dict):
        raise ValueError("Rough-cut plan must be a JSON object")
    duration = finite_seconds(plan.get("source_duration_s"), "source_duration_s")
    if duration <= 0:
        raise ValueError("source_duration_s must be positive")
    spans = plan.get("kept_spans_s")
    if not isinstance(spans, list):
        raise ValueError("kept_spans_s must be a list")
    checked = []
    for number, span in enumerate(spans, 1):
        if not isinstance(span, list) or len(span) != 2:
            raise ValueError(f"kept_spans_s[{number}] must be [start_s, end_s]")
        start = finite_seconds(span[0], f"kept_spans_s[{number}][0]")
        end = finite_seconds(span[1], f"kept_spans_s[{number}][1]")
        if not (0 <= start < end <= duration + EPSILON and start < duration):
            raise ValueError(f"kept span {number} is outside source duration or empty")
        start, end = max(0.0, start), min(duration, end)
        if checked and start < checked[-1][1]:
            raise ValueError("kept_spans_s must be in source order and must not overlap")
        if checked and start == checked[-1][1]:
            checked[-1][1] = end
        else:
            checked.append([start, end])
    return duration, checked


def read_srt(path):
    text = Path(path).read_text(encoding="utf-8-sig").strip()
    if not text:
        raise ValueError("SRT is empty")
    cues, previous_start = [], -1
    for ordinal, block in enumerate(re.split(r"\n[ \t]*\n+", text), 1):
        lines = block.splitlines()
        raw_number = ordinal
        if lines and lines[0].strip().isdigit():
            raw_number = int(lines.pop(0).strip())
        match = SRT_RANGE.fullmatch(lines[0].strip()) if lines else None
        caption_lines = lines[1:] if lines else []
        if not match or not any(line.strip() for line in caption_lines):
            raise ValueError(f"SRT cue {raw_number}: missing valid timing or caption")
        start = milliseconds(match.groups()[:4]) / 1000
        end = milliseconds(match.groups()[4:]) / 1000
        if start < previous_start - EPSILON or start >= end:
            raise ValueError(f"SRT cue {raw_number}: times are out of order or empty")
        cues.append({"source_cue_number": raw_number, "text": "\n".join(caption_lines),
                     "source_range_s": [start, end]})
        previous_start = start
    return cues


def map_cue(cue, spans):
    fragments = []
    program_cursor = 0.0
    source_start, source_end = cue["source_range_s"]
    for keep_start, keep_end in spans:
        part_start, part_end = max(source_start, keep_start), min(source_end, keep_end)
        if part_end > part_start + EPSILON:
            fragments.append({
                "source_range_s": [rounded(part_start), rounded(part_end)],
                "program_range_s": [rounded(program_cursor + part_start - keep_start),
                                    rounded(program_cursor + part_end - keep_start)],
            })
        program_cursor += keep_end - keep_start
    if not fragments:
        status = "removed"
        prompts = ["原句完全落在删段内。决定是否补录、重排或删除这句字幕。"]
    elif len(fragments) > 1:
        status = "split"
        prompts = ["原句被删段拆开。逐字核对两边语义后，再决定保留哪段或改成新的字幕屏。"]
    elif (abs(fragments[0]["source_range_s"][0] - source_start) <= EPSILON
          and abs(fragments[0]["source_range_s"][1] - source_end) <= EPSILON):
        status = "intact"
        prompts = []
    else:
        status = "trimmed"
        prompts = ["原句只保留了其中一部分。不得自动截断字幕文字，先试听边界再人工改字幕屏。"]
    return {**cue, "status": status, "program_coverage": fragments, "review_prompts": prompts}


def map_cues(plan_path, srt_path):
    duration, spans = read_plan(plan_path)
    cues = read_srt(srt_path)
    if any(cue["source_range_s"][1] > duration + EPSILON for cue in cues):
        raise ValueError("SRT contains a cue beyond source_duration_s")
    results = [map_cue(cue, spans) for cue in cues]
    counts = {status: sum(cue["status"] == status for cue in results)
              for status in ("intact", "removed", "trimmed", "split")}
    return {
        "schema_version": 1,
        "mapping_scope": "same-order constant-speed source timeline",
        "source_duration_s": rounded(duration),
        "program_duration_s": rounded(sum(end - start for start, end in spans)),
        "kept_spans_s": [[rounded(start), rounded(end)] for start, end in spans],
        "summary": counts,
        "cues": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", help="rough_cut_plan.py JSON path, or - to read JSON from stdin")
    parser.add_argument("srt", help="UTF-8 SRT in original source time")
    args = parser.parse_args()
    try:
        print(json.dumps(map_cues(args.plan, args.srt), ensure_ascii=False, indent=2))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        parser.exit(1, f"Cue mapping unavailable: {error}\n")


if __name__ == "__main__":
    main()
