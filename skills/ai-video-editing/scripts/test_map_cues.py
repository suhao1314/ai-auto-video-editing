"""Tests for map_cues. They use no media files and do not render anything."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import map_cues


SRT = """1
00:00:00,500 --> 00:00:02,000
intact

2
00:00:02,500 --> 00:00:03,500
trimmed

3
00:00:02,800 --> 00:00:04,500
split

4
00:00:06,000 --> 00:00:08,000
adjacent remains intact

5
00:00:09,000 --> 00:00:09,500
removed
"""


class MapCuesTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(tempfile.gettempdir())
        self.tmp = tempfile.TemporaryDirectory(
            prefix="map-cues-", dir=temp_root if temp_root.is_dir() else None
        )
        self.root = Path(self.tmp.name)
        self.plan = self.root / "plan.json"
        self.srt = self.root / "source.srt"
        self.plan.write_text(json.dumps({
            "source_duration_s": 10,
            "kept_spans_s": [[0, 3], [4, 6], [6, 9]],
        }), encoding="utf-8")
        self.srt.write_text(SRT, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_classifies_and_maps_original_cues(self):
        result = map_cues.map_cues(self.plan, self.srt)
        by_number = {cue["source_cue_number"]: cue for cue in result["cues"]}
        self.assertEqual(result["program_duration_s"], 8)
        self.assertEqual(by_number[1]["status"], "intact")
        self.assertEqual(by_number[2]["status"], "trimmed")
        self.assertEqual(by_number[3]["status"], "split")
        self.assertEqual(by_number[4]["status"], "intact")
        self.assertEqual(by_number[5]["status"], "removed")
        self.assertEqual(by_number[4]["program_coverage"], [{
            "source_range_s": [6.0, 8.0], "program_range_s": [5.0, 7.0],
        }])
        self.assertIn("不得自动截断", by_number[2]["review_prompts"][0])
        self.assertEqual(by_number[3]["text"], "split")

    def test_rejects_overlapping_keeps_and_cue_past_source(self):
        self.plan.write_text(json.dumps({
            "source_duration_s": 10, "kept_spans_s": [[0, 4], [3.5, 8]],
        }), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "must not overlap"):
            map_cues.map_cues(self.plan, self.srt)
        self.plan.write_text(json.dumps({
            "source_duration_s": 1, "kept_spans_s": [[0, 1]],
        }), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "beyond"):
            map_cues.map_cues(self.plan, self.srt)

    def test_cli_accepts_stdin_plan(self):
        process = subprocess.run(
            [sys.executable, "-B", str(Path(map_cues.__file__)), "-", str(self.srt)],
            input=json.dumps({"source_duration_s": 10, "kept_spans_s": [[0, 10]]}),
            text=True, capture_output=True, check=True,
        )
        self.assertEqual(json.loads(process.stdout)["summary"]["intact"], 5)

    def test_empty_keep_list_reports_all_removed(self):
        self.plan.write_text('{"source_duration_s": 10, "kept_spans_s": []}', encoding="utf-8")
        result = map_cues.map_cues(self.plan, self.srt)
        self.assertEqual(result["program_duration_s"], 0)
        self.assertEqual(result["summary"]["removed"], 5)


if __name__ == "__main__":
    unittest.main()
