"""Synthetic regression images only. Media is temporary; no real screenshot is changed."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageChops, ImageDraw, ImageStat

import render_evidence_scroll as scroll


def decoded_frame(path, frame, size):
    result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path),
                             "-vf", f"select=eq(n\\,{frame})", "-frames:v", "1", "-f", "rawvideo",
                             "-pix_fmt", "rgb24", "pipe:1"], capture_output=True, check=True)
    return Image.frombytes("RGB", size, result.stdout)


class MotionTests(unittest.TestCase):
    def setUp(self):
        self.image = Image.new("RGB", (320, 1000), "white")
        self.settings = dict(size=(320, 180), target_y=300, target_screen_y=0.5,
                             scroll_start=0.2, arrive_at=0.8, read_until=1.2,
                             duration=1.6, fps=10)

    def tearDown(self):
        self.image.close()

    def motion(self, **changes):
        settings = {**self.settings, **changes}
        canvas, motion = scroll.prepare(self.image, **settings)
        canvas.close()
        return motion

    def test_eases_then_holds_through_cut(self):
        motion = self.motion()
        self.assertEqual(motion.top(0), 0)
        self.assertEqual(motion.top(2), 0)
        self.assertEqual(motion.top(8), 210)
        self.assertEqual([motion.top(index) for index in range(8, 16)], [210] * 8)
        self.assertEqual(sorted(motion.top(index) for index in range(16)),
                         [motion.top(index) for index in range(16)])
        self.assertLess(motion.top(3) - motion.top(2), motion.top(5) - motion.top(4))

    def test_optional_continuation_starts_after_reading_and_hits_last_frame(self):
        motion = self.motion(end_y=500)
        self.assertEqual(motion.top(12), 210)
        self.assertGreater(motion.top(13), 210)
        self.assertEqual(motion.top(15), 500)

    def test_frame_quantization_and_invalid_motion_are_explicit(self):
        motion = self.motion(arrive_at=0.81)
        self.assertEqual(motion.arrive_frame, 9)
        for changes in ({"target_y": 1001}, {"target_y": 0}, {"start_y": 999},
                        {"crop_x": 319, "crop_width": 2}, {"target_screen_y": 1},
                        {"arrive_at": 1.3}, {"arrive_at": 0.21, "scroll_start": 0.2},
                        {"end_y": 500, "read_until": 1.6}, {"fps": True},
                        {"duration": float("nan")}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.motion(**changes)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "Existing FFmpeg and FFprobe required")
class RenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="evidence-scroll-tests-")
        self.root = Path(self.tmp.name)
        self.source = self.root / "synthetic-only.png"
        self.output = self.root / "scene.mp4"
        self.image = Image.new("RGB", (320, 1000), "white")
        draw = ImageDraw.Draw(self.image)
        for y in range(0, 1000, 20):
            draw.rectangle((0, y, 319, y + 9), fill=(210, 210, 210))
            draw.text((4, y), f"SYNTHETIC TEST ROW {y}", fill="black")
        draw.rectangle((0, 300, 319, 305), fill=(240, 20, 20))
        self.image.save(self.source)
        self.settings = dict(size=(320, 180), target_y=300, target_screen_y=0.5,
                             scroll_start=0.2, arrive_at=0.8, read_until=1.2,
                             duration=1.6, fps=10)

    def tearDown(self):
        self.image.close()
        self.tmp.cleanup()

    def test_actual_encoded_target_position_hold_pixels_and_silent_stream(self):
        before = hashlib.sha256(self.source.read_bytes()).hexdigest()
        report = scroll.render(self.source, self.output, **self.settings)
        info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_streams",
                                          "-of", "json", str(self.output)], capture_output=True,
                                         text=True, check=True).stdout)
        self.assertEqual(len(info["streams"]), 1)
        video = info["streams"][0]
        self.assertEqual(video["codec_type"], "video")
        self.assertEqual((video["width"], video["height"]), (320, 180))
        self.assertEqual(int(video["nb_read_frames"]), 16)
        expected = self.image.crop((0, 210, 320, 390))
        frames = [decoded_frame(self.output, frame, (320, 180)) for frame in (8, 12, 15)]
        for frame in frames:
            error = sum(ImageStat.Stat(ImageChops.difference(expected, frame)).mean) / 3
            self.assertLess(error, 2)
            red_rows = [y for y in range(180) if frame.getpixel((160, y))[0] > 180
                        and frame.getpixel((160, y))[1] < 80]
            self.assertLessEqual(abs(min(red_rows) - 90), 1)
        hold_difference = sum(ImageStat.Stat(ImageChops.difference(frames[0], frames[-1])).mean) / 3
        self.assertLess(hold_difference, 1)
        self.assertEqual(report["arrive_at_s"], 0.8)
        self.assertFalse(report["audio"])
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), before)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["scene.mp4", "synthetic-only.png"])

    def test_refuses_to_overwrite_and_does_not_leave_staging_file_on_error(self):
        self.output.write_bytes(b"KEEP ME")
        with self.assertRaises(FileExistsError):
            scroll.render(self.source, self.output, **self.settings)
        self.assertEqual(self.output.read_bytes(), b"KEEP ME")
        second = self.root / "failed.mp4"
        with self.assertRaises(OSError):
            scroll.render(self.source, second, ffmpeg="missing-ffmpeg-for-test", **self.settings)
        self.assertFalse(second.exists())
        self.assertFalse(list(self.root.glob(".*.mp4")))

    def test_cli_produces_a_real_clip_and_json_contract(self):
        command = [sys.executable, "-B", str(Path(scroll.__file__)), "--image", str(self.source),
                   "--output", str(self.output), "--size", "320x180", "--target-y", "300",
                   "--target-screen-y", "0.5", "--scroll-start", "0.2", "--arrive-at", "0.8",
                   "--read-until", "1.2", "--duration", "1.6", "--fps", "10", "--end-y", "500"]
        process = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report["frames"], 16)
        self.assertEqual(report["keyframes"][-1]["source_top_y"], 500)
        last = decoded_frame(self.output, 15, (320, 180))
        expected = self.image.crop((0, 500, 320, 680))
        self.assertLess(sum(ImageStat.Stat(ImageChops.difference(last, expected)).mean) / 3, 2)
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)


if __name__ == "__main__":
    unittest.main()
