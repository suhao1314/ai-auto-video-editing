"""Unit tests for the Auto-Editor timeline adapter.  No media is rendered."""

import tempfile
import unittest

import auto_editor_plan as adapter


class AutoEditorPlanTests(unittest.TestCase):
    def setUp(self):
        self.path = adapter.Path(tempfile.gettempdir()) / "timeline.v1"

    def test_v1_tracks_normal_speed_and_cuts(self):
        data = {
            "version": "1", "source": "source.mp4", "timebase": "30/1",
            "chunks": [[0, 36, 1.0], [36, 90, 99999.0], [90, 126, 1.0]],
        }
        version, source, rate, kept, covered, covers_source = adapter.parse_timeline(data, self.path)
        self.assertEqual(version, "1")
        self.assertEqual(source, self.path.parent / "source.mp4")
        self.assertEqual(str(rate), "30")
        self.assertEqual(kept, [[0.0, 1.2], [3.0, 4.2]])
        self.assertEqual(covered, 4.2)
        self.assertTrue(covers_source)

    def test_v2_and_v3_match_exported_shape(self):
        v2 = {
            "version": "2", "source": "source.mp4", "tb": "30/1",
            "effects": [["cut"], []],
            "clips": [[0, 36, 1], [36, 90, 0], [90, 126, 1]],
        }
        v3 = {
            "version": "3", "timebase": "30/1",
            "v": [[
                {"src": "source.mp4", "start": 0, "dur": 36, "offset": 0, "stream": 0},
                {"src": "source.mp4", "start": 36, "dur": 36, "offset": 90, "stream": 0},
            ]],
            "a": [[
                {"src": "source.mp4", "start": 0, "dur": 36, "offset": 0, "stream": 0},
                {"src": "source.mp4", "start": 36, "dur": 36, "offset": 90, "stream": 0},
            ]],
        }
        self.assertEqual(adapter.parse_timeline(v2, self.path)[3], [[0.0, 1.2], [3.0, 4.2]])
        self.assertEqual(adapter.parse_timeline(v3, self.path)[3], [[0.0, 1.2], [3.0, 4.2]])
        self.assertFalse(adapter.parse_timeline(v3, self.path)[5])

    def test_v2_allows_a_gap_as_an_implicit_cut(self):
        data = {
            "version": "2", "source": "source.mp4", "tb": "30/1",
            "effects": [[]], "clips": [[30, 60, 0]],
        }
        self.assertEqual(adapter.parse_timeline(data, self.path)[3], [[1.0, 2.0]])

    def test_rejects_speed_changes_layers_and_reordered_source(self):
        with self.assertRaisesRegex(ValueError, "speed changes"):
            adapter.parse_timeline({
                "version": "1", "source": "source.mp4", "timebase": "30/1",
                "chunks": [[0, 30, 1], [30, 60, 1.5]],
            }, self.path)
        with self.assertRaisesRegex(ValueError, "exactly one video layer"):
            adapter.parse_timeline({
                "version": "3", "timebase": "30/1", "v": [[], []],
            }, self.path)
        with self.assertRaisesRegex(ValueError, "source order"):
            adapter.parse_timeline({
                "version": "3", "timebase": "30/1",
                "v": [[
                    {"src": "source.mp4", "start": 0, "dur": 30, "offset": 30, "stream": 0},
                    {"src": "source.mp4", "start": 30, "dur": 30, "offset": 0, "stream": 0},
                ]],
                "a": [[
                    {"src": "source.mp4", "start": 0, "dur": 30, "offset": 30, "stream": 0},
                    {"src": "source.mp4", "start": 30, "dur": 30, "offset": 0, "stream": 0},
                ]],
            }, self.path)

    def test_v3_rejects_audio_that_does_not_follow_the_video_cut(self):
        with self.assertRaisesRegex(ValueError, "same source"):
            adapter.parse_timeline({
                "version": "3", "timebase": "30/1",
                "v": [[{"src": "source.mp4", "start": 0, "dur": 30, "offset": 0, "stream": 0}]],
                "a": [[{"src": "music.mp3", "start": 0, "dur": 30, "offset": 0, "stream": 0}]],
            }, self.path)

    def test_v1_without_timebase_uses_the_probed_source_rate(self):
        data = {"version": "1", "source": "source.mp4", "chunks": [[0, 30000, 1]]}
        result = adapter.parse_timeline(data, self.path, adapter.Fraction(30000, 1001))
        self.assertEqual(result[2], adapter.Fraction(30000, 1001))

    def test_relative_source_uses_one_real_root_and_rejects_ambiguity(self):
        temporary_root = adapter.Path(tempfile.gettempdir())
        with tempfile.TemporaryDirectory(dir=temporary_root) as directory:
            root = adapter.Path(directory)
            timeline = root / "timeline" / "cut.v1"
            source_root = root / "source-root"
            timeline.parent.mkdir()
            source_root.mkdir()
            (source_root / "source.mp4").touch()
            self.assertEqual(
                adapter.absolute_source(timeline, "source.mp4", source_root),
                (source_root / "source.mp4").resolve(),
            )
            (timeline.parent / "source.mp4").touch()
            with self.assertRaisesRegex(ValueError, "more than one"):
                adapter.absolute_source(timeline, "source.mp4", source_root)


if __name__ == "__main__":
    unittest.main()
