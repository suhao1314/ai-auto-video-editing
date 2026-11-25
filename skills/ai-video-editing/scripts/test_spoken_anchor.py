"""Regression checks for transcript clocks and honest keyword intervals."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from find_spoken_anchor import find_anchors
from review_window import read_words


class SpokenAnchorTests(unittest.TestCase):
    def load(self, source, **options):
        with tempfile.TemporaryDirectory(dir=os.environ.get("AI_VIDEO_TEST_TEMP")) as folder:
            path = Path(folder) / "words.json"
            path.write_text(json.dumps(source), encoding="utf-8-sig")
            return read_words(path, **options)

    def test_legacy_forms_preserve_sorted_times(self):
        entries = [{"w": "later", "start": 2, "end": 3},
                   {"text": "earlier", "start": 0, "end": 1},
                   {"type": "silence"}]
        for source in [entries, {"words": entries}]:
            words = self.load(source)
            self.assertEqual([w["text"] for w in words], ["earlier", "later"])
            self.assertEqual(words[1]["start"], 2)

    def test_breeze_paragraph_remains_on_its_own_clock(self):
        words = self.load({"word_timestamps": [{"word": "main", "start": 2.25, "end": 2.75}]})
        self.assertEqual((words[0]["start"], words[0]["end"]), (2.25, 2.75))

    def lines(self):
        return {"lines": [{"id": "L33", "text": "合进 main", "global_start": 100,
                           "duration": 3, "global_end": 103,
                           "words": [{"word": "合", "start": .2, "end": .5},
                                     {"word": "进", "start": .5, "end": .7},
                                     {"word": "main", "start": .7, "end": 1}]}]}

    def test_unmarked_line_clock_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "clock is unmarked"):
            self.load(self.lines())

    def test_confirmed_line_clock_offsets_once(self):
        words = self.load(self.lines(), line_words_local=True)
        self.assertEqual(words[0]["start"], 100.2)
        source = self.lines()
        source["word_timebase"] = "line-local"
        self.assertEqual(self.load(source)[0]["start"], 100.2)

    def test_incompatible_word_clock_and_line_duration_rejected(self):
        source = self.lines()
        source["lines"][0]["words"][0]["end"] = 100.5
        with self.assertRaisesRegex(ValueError, "timebase"):
            self.load(source, line_words_local=True)

    def test_cross_token_phrase_and_excerpt_window(self):
        words = self.load(self.lines(), line_words_local=True)
        hits = find_anchors(words, "合进main", line="L33", context="合进", origin=99,
                            start=1, end=2)
        self.assertEqual(len(hits), 1)
        self.assertAlmostEqual(hits[0]["start"], 1.2)
        self.assertEqual(hits[0]["end"], 2)
        self.assertEqual(hits[0]["precision"], "word-boundaries")
        self.assertEqual(find_anchors(words, "合进main", origin=99, start=1.3, end=2), [])

    def test_repeated_and_partial_tokens_return_all_without_interpolation(self):
        words = self.load({"words": [{"text": "main", "start": 1, "end": 2},
                                      {"text": "main", "start": 3, "end": 4}]})
        hits = find_anchors(words, "ai")
        self.assertEqual([(h["start"], h["end"]) for h in hits], [(1, 2), (3, 4)])
        self.assertTrue(all(h["precision"] == "covering-token-interval" for h in hits))
        self.assertEqual(len(find_anchors(words, "MAIN")), 2)
        self.assertEqual(find_anchors(words, "main", context="missing"), [])

    def test_phrases_do_not_cross_line_boundaries(self):
        source = {"word_timebase": "line-local", "lines": [
            {"id": "a", "global_start": 0, "duration": 1,
             "words": [{"word": "合", "start": 0, "end": 1}]},
            {"id": "b", "global_start": 1, "duration": 1,
             "words": [{"word": "进", "start": 0, "end": 1}]}]}
        self.assertEqual(find_anchors(self.load(source), "合进"), [])

    def test_nonfinite_words_and_invalid_windows_rejected(self):
        with self.assertRaises(ValueError):
            self.load({"words": [{"w": "bad", "start": 0, "end": float("inf")}]})
        with self.assertRaises(ValueError):
            find_anchors([], "main", origin=float("nan"))

    def test_cli_requires_confirmed_line_clock_and_reports_all_legacy_hits(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get("AI_VIDEO_TEST_TEMP")) as folder:
            path = Path(folder) / "words.json"
            path.write_text(json.dumps(self.lines()), encoding="utf-8")
            command = [sys.executable, "-B", str(Path(__file__).with_name("find_spoken_anchor.py")),
                       str(path), "main"]
            unconfirmed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(unconfirmed.returncode, 2)
            self.assertIn("clock is unmarked", unconfirmed.stderr)
            confirmed = subprocess.run(command + ["--line-words-local"], capture_output=True, text=True)
            self.assertEqual(confirmed.returncode, 0, confirmed.stderr)
            self.assertEqual(json.loads(confirmed.stdout)["matches"][0]["start"], 100.7)
            path.write_text(json.dumps({"words": [{"w": "main", "start": 1, "end": 2},
                                                   {"w": "main", "start": 3, "end": 4}]}),
                            encoding="utf-8")
            legacy = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(legacy.returncode, 0, legacy.stderr)
            self.assertEqual(len(json.loads(legacy.stdout)["matches"]), 2)
            absent = subprocess.run(command + ["--context", "missing"], capture_output=True, text=True)
            self.assertEqual(absent.returncode, 1)


if __name__ == "__main__":
    unittest.main()
