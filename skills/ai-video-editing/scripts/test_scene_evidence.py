"""Synthetic state changes exercise the bundled ROI runner without real media."""

from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

from PIL import Image

import check_scene_evidence as scene


SCRIPTS = Path(__file__).resolve().parent
RUNNER = SCRIPTS.parent / "tools/visual-regression"


def available():
    if not all(shutil.which(tool) for tool in ("ffmpeg", "ffprobe", "node")):
        return False
    result = subprocess.run(
        ["node", "--input-type=module", "-e",
         "import {createRequire} from 'node:module'; "
         "const r=createRequire(process.argv[1]); "
         "r('pngjs'); r('jpeg-js'); r.resolve('pixelmatch');",
         str(RUNNER / "package.json")], capture_output=True)
    return result.returncode == 0


class FingerprintTests(unittest.TestCase):
    def test_chunked_hash_matches_sha256(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("AI_VIDEO_TEST_TEMP")) as folder:
            path = Path(folder) / "bytes.bin"
            data = b"synthetic" * 140000
            path.write_bytes(data)
            self.assertEqual(scene.fingerprint(path),
                             {"path": str(path), "sha256": hashlib.sha256(data).hexdigest()})

    def test_csv_rejects_bad_shapes_and_nonfinite_values(self):
        import argparse
        for value in ("1,2", "0,nan,2", "0,1,inf", "zero,1,2"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                scene.csv_numbers(value, 3, float)


@unittest.skipUnless(available(), "Existing FFmpeg, FFprobe, Node and bundled ROI dependencies required")
class SceneEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="scene-evidence-",
                                              dir=os.environ.get("AI_VIDEO_TEST_TEMP"))
        self.root = Path(self.tmp.name)
        self.before = self.root / "before.png"
        self.after = self.root / "after.png"
        self.video = self.root / "states.mkv"
        with Image.new("RGB", (64, 64), "red") as before:
            before.save(self.before)
            first = before.tobytes()
        with Image.new("RGB", (64, 64), "blue") as after:
            after.save(self.after)
            second = after.tobytes()
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s:v", "64x64",
                        "-r", "10", "-i", "pipe:0", "-an", "-c:v", "ffv1",
                        "-pix_fmt", "bgr0", str(self.video)],
                       input=first * 10 + second * 10, capture_output=True, check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def args(self, name="checks", **changes):
        return SimpleNamespace(**{
            "video": self.video, "times": (.2, .9, 1.4), "roi": (0, 0, 64, 64),
            "reference_before": self.before, "reference_after": self.after,
            "output": self.root / name, "threshold": .1, "max_diff_ratio": 0,
            "visual_regression_root": None, **changes})

    def check(self, args):
        with redirect_stdout(io.StringIO()) as output:
            code = scene.check(args)
        self.assertEqual(json.loads(output.getvalue())["manual_review_required"], True)
        report = json.loads((args.output / "scene-evidence.json").read_text(encoding="utf-8"))
        return code, report

    def test_real_three_frame_change_passes_and_preserves_inputs(self):
        original = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (self.video, self.before, self.after)}
        code, report = self.check(self.args())
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "image_checks_passed")
        self.assertEqual(report["findings"], [])
        self.assertEqual(set(report["samples"]), {"before", "action", "after"})
        self.assertTrue(report["manual_review_required"])
        self.assertEqual(original, {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in (self.video, self.before, self.after)})

    def test_result_visible_too_early_and_identical_references_are_reported(self):
        code, report = self.check(self.args(times=(1.1, 1.3, 1.5)))
        self.assertEqual(code, 1)
        self.assertIn("result_state_already_visible_at_before_sample", report["findings"])
        self.assertIn("no_distinguishable_state_change_between_samples", report["findings"])
        code, report = self.check(self.args("same-refs", reference_after=self.before))
        self.assertEqual(code, 1)
        self.assertIn("references_not_distinguishable_in_roi", report["findings"])

    def test_invalid_bounds_and_existing_output_are_rejected_without_replacement(self):
        for changes in ({"times": (.9, .2, 1.4)}, {"times": (.2, .9, 2)},
                        {"roi": (60, 0, 10, 10)}, {"max_diff_ratio": 1},
                        {"threshold": float("nan")}):
            args = self.args(**changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                scene.check(args)
            self.assertFalse(args.output.exists())
        args = self.args()
        args.output.mkdir()
        keep = args.output / "keep.txt"
        keep.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "never overwritten"):
            scene.check(args)
        self.assertEqual(keep.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
