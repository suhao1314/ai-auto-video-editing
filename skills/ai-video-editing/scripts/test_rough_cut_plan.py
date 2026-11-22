"""Regression for silent pictures that the editor has explicitly agreed to keep."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from rough_cut_plan import plan, protect


class ProtectedPictures(unittest.TestCase):
    def test_unaligned_edges_include_the_whole_boundary_frame(self):
        self.assertEqual(protect([(1, 2)], [(2.01, 2.39), (4.11, 5)], 25, 5),
                         [[1, 2.4], [4.08, 5]])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "requires FFmpeg")
    def test_midshot_and_silent_ending_survive_actual_planner(self):
        temp_root = Path(tempfile.gettempdir())
        with tempfile.TemporaryDirectory(dir=temp_root if temp_root.is_dir() else None) as folder:
            work = Path(folder)
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                            "testsrc2=s=96x64:r=25:duration=9", "-f", "lavfi", "-i",
                            "sine=f=550:d=9", "-c:v", "libx264", "-preset", "ultrafast",
                            "-c:a", "aac", str(work / "clip.mp4")], check=True)
            spec, transcript = work / "edit.json", work / "words.json"
            keep = [[2, 2.48], [8, 9]]
            spec.write_text(json.dumps({"video": "clip.mp4", "keep": keep}), encoding="utf-8")
            transcript.write_text(json.dumps({"words": [
                {"w": "看这里。", "start": 0.6, "end": 1.3},
                {"w": "下一步。", "start": 5.5, "end": 6.1}]}), encoding="utf-8")
            result = plan(spec, transcript)
            self.assertTrue(result["proposed_removals"])
            for start, end in keep:
                self.assertTrue(any(s <= start and e >= end for s, e in result["kept_spans_s"]))
                for cut in result["proposed_removals"]:
                    s, e = cut["source_s"]
                    self.assertFalse(s < end and e > start)


if __name__ == "__main__":
    unittest.main()
