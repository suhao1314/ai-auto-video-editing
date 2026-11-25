"""Extract three export frames and check a fixed ROI against reviewed state references.

This is a pixel evidence check, not approval of an operation or its meaning.
The action frame must still be watched with the surrounding video and narration.
Use identical canvas size and object placement; camera moves or layout changes
need manual alignment before this fixed-rectangle comparison can be meaningful.
Uses existing FFmpeg/ffprobe and compare_roi.mjs; installs nothing.
Exit 0: image checks passed (manual review pending), 1: image mismatch, 2: input/tool error.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from check_export import inspect, local_file, run_tool


def csv_numbers(value, count, converter):
    try:
        numbers = tuple(converter(item) for item in value.split(","))
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use comma-separated numbers") from error
    if len(numbers) != count or not all(math.isfinite(n) for n in numbers):
        raise argparse.ArgumentTypeError(f"Expected {count} finite numbers")
    return numbers


def fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path), "sha256": digest.hexdigest()}


def extract_frame(video, seconds, stream_index, output):
    # Accurate input seeking decodes from the preceding keyframe; no resize/crop is applied.
    run_tool(["ffmpeg", "-nostdin", "-v", "error", "-n", "-protocol_whitelist", "file,pipe",
              "-ss", str(seconds), "-i", str(video), "-map", f"0:{stream_index}",
              "-frames:v", "1", "-update", "1", str(output)])
    if not output.is_file() or output.stat().st_size == 0:
        raise ValueError(f"No decoded frame at {seconds}s")


def compare(left, right, label, args):
    report = args.output / f"{label}.json"
    command = ["node", str(Path(__file__).with_name("compare_roi.mjs")),
               "--baseline", str(left), "--actual", str(right),
               "--roi", ",".join(str(n) for n in args.roi),
               "--diff", str(args.output / f"{label}.png"), "--report", str(report),
               "--threshold", str(args.threshold),
               "--max-diff-ratio", str(args.max_diff_ratio),
               "--max-diff-pixels", str(math.floor(args.roi[2] * args.roi[3] * args.max_diff_ratio))]
    if args.visual_regression_root:
        command += ["--visual-regression-root", str(args.visual_regression_root.resolve())]
    result = subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode not in (0, 1):
        raise ValueError(result.stderr.strip()[-1500:] or "ROI comparison unavailable")
    data = json.loads(report.read_text(encoding="utf-8"))
    return {"same_within_tolerance": result.returncode == 0,
            "diff_pixels": data["diffPixels"], "diff_ratio": data["diffRatio"],
            "report": str(report), "diff": str(args.output / f"{label}.png")}


def check(args):
    video = Path(local_file(args.video))
    before_ref = Path(local_file(args.reference_before))
    after_ref = Path(local_file(args.reference_after))
    args.output = args.output.resolve()
    if args.output.exists():
        raise ValueError("Choose a new output directory; existing outputs are never overwritten")
    if not (0 <= args.times[0] < args.times[1] < args.times[2]):
        raise ValueError("Times must increase: before < action < after")
    if not (0 <= args.threshold <= 1 and 0 <= args.max_diff_ratio < 1):
        raise ValueError("Threshold must be 0..1; max-diff-ratio must be 0..<1")
    stream, _, container = inspect(str(video))
    duration_value = stream.get("duration")
    if duration_value in (None, "N/A"):
        duration_value = container.get("duration")
    if duration_value not in (None, "N/A") and args.times[-1] >= float(duration_value):
        raise ValueError("All samples must lie inside the video")
    x, y, width, height = args.roi
    if x < 0 or y < 0 or width < 1 or height < 1 or x + width > stream["width"] or y + height > stream["height"]:
        raise ValueError("ROI must fit the decoded video frame")
    args.output.mkdir(parents=True, exist_ok=False)
    samples = {}
    for name, seconds in zip(("before", "action", "after"), args.times):
        frame = args.output / f"{name}.png"
        extract_frame(video, seconds, stream["index"], frame)
        samples[name] = {"requested_seconds": seconds, **fingerprint(frame)}

    pairs = {}
    for label, left, right in (
        ("reference-separation", before_ref, after_ref),
        ("before-expected", before_ref, Path(samples["before"]["path"])),
        ("after-expected", after_ref, Path(samples["after"]["path"])),
        ("before-after", Path(samples["before"]["path"]), Path(samples["after"]["path"])),
        ("before-versus-result", after_ref, Path(samples["before"]["path"])),
    ):
        pairs[label] = compare(left, right, label, args)
    findings = []
    if pairs["reference-separation"]["same_within_tolerance"]:
        findings.append("references_not_distinguishable_in_roi")
    if not pairs["before-expected"]["same_within_tolerance"]:
        findings.append("before_does_not_match_reviewed_before_state")
    if not pairs["after-expected"]["same_within_tolerance"]:
        findings.append("after_does_not_match_reviewed_result_state")
    if pairs["before-after"]["same_within_tolerance"]:
        findings.append("no_distinguishable_state_change_between_samples")
    if not pairs["reference-separation"]["same_within_tolerance"] and pairs["before-versus-result"]["same_within_tolerance"]:
        findings.append("result_state_already_visible_at_before_sample")
    report = {"status": "image_checks_passed" if not findings else "image_mismatch",
              "manual_review_required": True,
              "limits": "Only three requested times and a fixed ROI were checked. References require prior human verification. Watch the action frame and surrounding video with narration; pixel changes do not prove a click, merge, correct text, or correct timing between samples.",
              "video": fingerprint(video), "references": {"before": fingerprint(before_ref), "after": fingerprint(after_ref)},
              "roi": args.roi, "threshold": args.threshold, "max_diff_ratio": args.max_diff_ratio,
              "samples": samples, "comparisons": pairs, "findings": findings}
    report_path = args.output / "scene-evidence.json"
    report_path.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "findings": findings,
                      "manual_review_required": True, "report": str(report_path)}, ensure_ascii=True))
    return int(bool(findings))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--times", required=True, type=lambda s: csv_numbers(s, 3, float), metavar="BEFORE,ACTION,AFTER")
    parser.add_argument("--roi", required=True, type=lambda s: csv_numbers(s, 4, int), metavar="X,Y,WIDTH,HEIGHT")
    parser.add_argument("--reference-before", required=True, type=Path, help="reviewed full-frame PNG/JPG on this same canvas")
    parser.add_argument("--reference-after", required=True, type=Path, help="reviewed full-frame PNG/JPG showing the result")
    parser.add_argument("--output", required=True, type=Path, help="new directory for extracted frames and the comparison report")
    parser.add_argument("--threshold", type=float, default=0.1, help="Pixelmatch per-pixel threshold, default 0.1")
    parser.add_argument("--max-diff-ratio", type=float, default=0, help="allowed changed-pixel fraction, default 0 (exact above threshold)")
    parser.add_argument("--visual-regression-root", type=Path, help="existing runner directory if the skill was copied elsewhere")
    args = parser.parse_args()
    try:
        return check(args)
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, f"Scene evidence unavailable: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
