"""Render a 16:9 evidence card around one local screenshot or screen recording.

The card has three readable moments: state, trigger and result. Video inputs
play from --start-seconds to their source end by default. They never loop.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile


FPS = 30
FONT = Path(__file__).resolve().parent / "font.ttf"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def ffmpeg_path(value: str) -> str:
    return str(Path(value).resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def break_text(value: str, width: int, max_rows: int | None = None) -> str:
    """Keep narrow title and sidebar fields inside their intended rectangle."""
    rows = []
    for original in value.replace("\r", "").split("\n"):
        while len(original) > width:
            rows.append(original[:width])
            original = original[width:]
        rows.append(original or " ")
    if max_rows is not None and len(rows) > max_rows:
        rows = rows[:max_rows]
        rows[-1] = rows[-1][:-1] + "…" if len(rows[-1]) >= width else rows[-1] + "…"
    return "\n".join(rows)


def media_seconds(path: Path) -> float:
    raw = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)
    ], text=True, encoding="utf-8")
    duration = float(json.loads(raw)["format"]["duration"])
    if duration <= 0:
        raise ValueError("Input duration is unavailable")
    return duration


def point(value: str) -> tuple[int, int, int, int]:
    try:
        parsed = tuple(int(part.strip()) for part in value.split(","))
    except ValueError as error:
        raise ValueError("--focus uses x,y,width,height inside the 860x440 main window") from error
    if len(parsed) != 4 or parsed[2] < 1 or parsed[3] < 1:
        raise ValueError("--focus uses x,y,width,height inside the 860x440 main window")
    x, y, width, height = parsed
    if x < 0 or y < 0 or x + width > 860 or y + height > 440:
        raise ValueError("--focus must fit inside the 860x440 main window")
    return parsed


def text_layer(textfile: Path, x: int, y: int, size: int, color: str, *, enable: str | None = None) -> str:
    layer = (
        f"drawtext=fontfile='{ffmpeg_path(str(FONT))}':textfile='{ffmpeg_path(str(textfile))}':"
        f"x={x}:y={y}:fontsize={size}:line_spacing=7:fontcolor={color}:"
        "shadowcolor=0x132238@0.18:shadowx=0:shadowy=2:expansion=none"
    )
    return layer + (f":enable='{enable}'" if enable else "")


def write_texts(temp: Path, args: argparse.Namespace) -> dict[str, Path]:
    values = {
        "kicker": break_text(args.kicker, 20, 1),
        "title": break_text(args.title, 6, 2),
        "one": break_text(args.step_one, 8, 1),
        "two": break_text(args.step_two, 8, 1),
        "three": break_text(args.step_three, 8, 1),
        "caption_one": break_text(args.caption_one, 34, 1),
        "caption_two": break_text(args.caption_two, 34, 1),
        "caption_three": break_text(args.caption_three, 34, 1),
        "demo_header": "文件管理",
        "demo_before": "《周报.md》还在下载目录",
        "demo_action": "选中资料后，点击“移入项目”",
        "demo_after": "已归档 · 项目/文档/周报.md",
        "demo_button": "移入项目",
        "demo_done": "归档完成",
    }
    paths: dict[str, Path] = {}
    for key, value in values.items():
        path = temp / f"{key}.txt"
        path.write_text(value, encoding="utf-8")
        paths[key] = path
    return paths


def stage_points(args: argparse.Namespace, seconds: float, demo: bool) -> tuple[float, float]:
    action = args.action_at_seconds
    result = args.result_at_seconds
    if demo:
        action = seconds / 3 if action is None else action
        result = seconds * 2 / 3 if result is None else result
    elif action is None and result is None:
        return seconds, seconds
    elif action is None or result is None:
        raise ValueError("Set both --action-at-seconds and --result-at-seconds for a real video")
    if not 0 < action < result < seconds:
        raise ValueError("Action and result times must satisfy 0 < action < result < output duration")
    return action, result


def build_filter(args: argparse.Namespace, texts: dict[str, Path], seconds: float, demo: bool) -> str:
    first_end, second_end = stage_points(args, seconds, demo)
    # Half-open ranges ensure an exact boundary frame never draws two stage labels.
    first = f"lt(t,{first_end:.3f})"
    second = f"gte(t,{first_end:.3f})*lt(t,{second_end:.3f})"
    third = f"gte(t,{second_end:.3f})"
    base = "color=c=0xEFF4F8:s=1280x720:r=30:d=" + f"{seconds:.3f}[base]"
    if demo:
        source = (
            f"color=c=0xE7EEF7:s=860x440:r=30:d={seconds:.3f},"
            "drawbox=x=40:y=46:w=780:h=52:color=0xFFFFFF:t=fill,"
            + text_layer(texts["demo_header"], 70, 60, 28, "0x203752") + ","
            "drawbox=x=40:y=132:w=780:h=234:color=0xFFFFFF:t=fill,"
            + text_layer(texts["demo_before"], 72, 174, 34, "0x173553", enable=first) + ","
            "drawbox=x=72:y=248:w=470:h=54:color=0xF1F5F8:t=fill:enable='" + first + "',"
            + text_layer(texts["demo_action"], 72, 174, 31, "0x173553", enable=second) + ","
            "drawbox=x=486:y=248:w=242:h=64:color=0x1A7F72:t=fill:enable='" + second + "',"
            + text_layer(texts["demo_button"], 518, 265, 20, "0xFFFFFF", enable=second) + ","
            + text_layer(texts["demo_after"], 72, 174, 34, "0x173553", enable=third) + ","
            "drawbox=x=72:y=248:w=600:h=64:color=0xDDF2EB:t=fill:enable='" + third + "',"
            + text_layer(texts["demo_done"], 96, 266, 25, "0x1A7F72", enable=third) + "[source]"
        )
    else:
        source = (
            f"[0:v]trim=start={args.start_seconds:.3f}:end={args.start_seconds + seconds:.3f},"
            "setpts=PTS-STARTPTS,fps=30,scale=w=860:h=440:force_original_aspect_ratio=decrease,"
            "pad=860:440:(ow-iw)/2:(oh-ih)/2:color=0xDFE8F0,setsar=1[source]"
        )
    focus = point(args.focus) if args.focus else None
    board = (
        "[base]drawbox=x=44:y=38:w=1192:h=644:color=0xFFFFFF:t=fill,"
        "drawbox=x=44:y=38:w=1192:h=76:color=0x173553:t=fill,"
        "drawbox=x=72:y=144:w=860:h=440:color=0x172F49:t=fill,"
        "drawbox=x=72:y=144:w=860:h=440:color=0x172F49:t=4,"
        "drawbox=x=962:y=144:w=224:h=440:color=0xE9F2F4:t=fill,"
        "drawbox=x=72:y=610:w=1114:h=42:color=0xF2F6F9:t=fill,"
        + text_layer(texts["kicker"], 74, 61, 23, "0xF4F8FA") + ","
        + text_layer(texts["title"], 982, 178, 31, "0x173553") + ","
        + text_layer(texts["one"], 982, 408, 23, "0x1A7F72", enable=first) + ","
        + text_layer(texts["two"], 982, 408, 23, "0x1A7F72", enable=second) + ","
        + text_layer(texts["three"], 982, 408, 23, "0x1A7F72", enable=third) + ","
        + text_layer(texts["caption_one"], 98, 620, 24, "0x173553", enable=first) + ","
        + text_layer(texts["caption_two"], 98, 620, 24, "0x173553", enable=second) + ","
        + text_layer(texts["caption_three"], 98, 620, 24, "0x173553", enable=third) + "[board];"
        "[board][source]overlay=x=72:y=144:shortest=1"
    )
    if focus:
        focus_x, focus_y, focus_w, focus_h = focus
        board += (
            f",drawbox=x={72 + focus_x}:y={144 + focus_y}:w={focus_w}:h={focus_h}:"
            f"color=0x1A7F72@0.90:t=4:enable='{second}'"
        )
    return ";".join([base, source, board + ",format=yuv420p[out]"])


def source_window(args: argparse.Namespace) -> tuple[bool, float]:
    if args.demo:
        return True, args.duration_seconds or 12.0
    if not args.input:
        raise ValueError("Pass --input for a local real source, or use --demo only for visual review")
    source = args.input.resolve(strict=True)
    if source.suffix.lower() in IMAGE_SUFFIXES:
        return False, args.duration_seconds or 12.0
    available = media_seconds(source) - args.start_seconds
    if available <= 0:
        raise ValueError("--start-seconds is after the video ends")
    return False, min(args.duration_seconds, available) if args.duration_seconds else available


def render(args: argparse.Namespace) -> None:
    global FONT
    FONT = args.font.resolve()
    if not FONT.is_file():
        raise ValueError(f"Chinese font unavailable: {FONT}")
    if args.start_seconds < 0:
        raise ValueError("--start-seconds cannot be negative")
    output = args.output.resolve()
    if output.exists():
        raise ValueError(f"Refusing to overwrite existing file: {output}")
    demo, seconds = source_window(args)
    if seconds <= 0:
        raise ValueError("Requested duration must be positive")
    if not demo and args.focus and (args.action_at_seconds is None or args.result_at_seconds is None):
        raise ValueError("--focus requires both --action-at-seconds and --result-at-seconds")
    output.parent.mkdir(parents=True, exist_ok=True)
    if demo:
        args.kicker = "操作示意"
        args.focus = args.focus or "486,248,242,64"
    with tempfile.TemporaryDirectory(prefix="generic-template-", dir=output.parent) as temp_name:
        texts = write_texts(Path(temp_name), args)
        command = ["ffmpeg", "-n"]
        if demo:
            command += ["-f", "lavfi", "-i", f"color=c=black:s=2x2:r={FPS}:d={seconds:.3f}"]
        else:
            source = args.input.resolve()
            if source.suffix.lower() in IMAGE_SUFFIXES:
                command += ["-loop", "1", "-framerate", str(FPS), "-t", f"{seconds:.3f}", "-i", str(source)]
            else:
                command += ["-i", str(source)]
        command += [
            "-filter_complex", build_filter(args, texts, seconds, demo), "-map", "[out]", "-t", f"{seconds:.3f}",
            "-r", str(FPS), "-an", "-c:v", "libx264", "-crf", "19", "-preset", "medium",
            "-movflags", "+faststart", str(output),
        ]
        subprocess.run(command, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Local screenshot, screen recording or footage")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--font", type=Path, default=FONT, help="Local font file with Chinese glyphs")
    parser.add_argument("--start-seconds", type=float, default=0, help="Video source in-point. Video stops at its source end.")
    parser.add_argument("--duration-seconds", type=float, help="Shorten video input or set still-image duration")
    parser.add_argument("--focus", help="x,y,width,height inside the 860x440 source window; omitted means no frame")
    parser.add_argument("--action-at-seconds", type=float, help="Output-relative time when the real action begins")
    parser.add_argument("--result-at-seconds", type=float, help="Output-relative time when the result becomes readable")
    parser.add_argument("--kicker", default="实操说明")
    parser.add_argument("--title", default="把重点画面讲清楚")
    parser.add_argument("--step-one", default="先看原来的状态")
    parser.add_argument("--step-two", default="找到要操作的位置")
    parser.add_argument("--step-three", default="确认结果已经出现")
    parser.add_argument("--caption-one", default="先看清楚它原来在哪里")
    parser.add_argument("--caption-two", default="说到动作时，再把这个位置框出来")
    parser.add_argument("--caption-three", default="结果出现后，留时间读完")
    parser.add_argument("--demo", action="store_true", help="Render a labelled placeholder for template review")
    args = parser.parse_args()
    try:
        render(args)
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"Template render failed: {error}", file=sys.stderr)
        return 1
    print(f"Rendered: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
