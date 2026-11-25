"""Synthetic missing/wrong-time SFX regressions. Temporary WAVs are cleaned up."""

from array import array
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave

import check_action_audio as audio


@unittest.skipUnless(shutil.which("ffmpeg"), "An existing FFmpeg is required; never install one")
class ActionAudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="action-audio-")
        self.root = Path(self.tmp.name)
        self.cues = self.root / "cues.json"
        self.plan = self.root / "plan.json"

    def tearDown(self):
        self.tmp.cleanup()

    def manifest(self, cues, timebase="program"):
        self.cues.write_text(json.dumps({"timebase": timebase, "cues": cues}), encoding="utf-8")
        return self.cues

    def wav(self, name, pulses=(), duration=3, channels=1, amplitude=0.5):
        values = array("h")
        for index in range(round(duration * audio.RATE)):
            seconds = index / audio.RATE
            active = any(start <= seconds < end for start, end in pulses)
            value = round(amplitude * 32767 * math.cos(2 * math.pi * 800 * seconds)) if active else 0
            values.append(value)
            if channels == 2:
                values.append(-value)  # Detect channel cancellation bugs.
        if sys.byteorder != "little":
            values.byteswap()
        path = self.root / name
        with wave.open(str(path), "wb") as output:
            output.setnchannels(channels)
            output.setsampwidth(2)
            output.setframerate(audio.RATE)
            output.writeframes(values.tobytes())
        return path

    def test_detects_correct_missing_and_late_sound(self):
        self.manifest([{"id": "correct", "seconds": 0.5},
                       {"id": "missing", "seconds": 1.4},
                       {"id": "late", "seconds": 2.1}])
        path = self.wav("sfx.wav", [(0.5, 0.55), (2.4, 2.45)])
        report = audio.check(self.cues, sfx=path)
        results = {item["id"]: item for item in report["cues"]}
        self.assertEqual(results["correct"]["status"], "onset_in_window")
        self.assertEqual(results["missing"]["status"], "no_activity")
        self.assertEqual(results["late"]["status"], "onset_outside_window")
        self.assertAlmostEqual(results["late"]["measurements"]["sfx"]["onset_offset_s"], 0.3, places=2)
        self.assertEqual(report["summary"]["needs_review"], 2)
        self.assertTrue(report["listening_required"])

    def test_mix_only_cannot_attribute_sfx_or_claim_it_is_missing(self):
        self.manifest([{"seconds": 1}])
        for pulses in ([], [(0, 3)]):
            report = audio.check(self.cues, mix=self.wav("mixed.wav", pulses))
            self.assertEqual(report["cues"][0]["status"], "unverifiable_without_separate_track")
            self.assertEqual(report["summary"]["needs_review"], 1)

    def test_existing_click_does_not_require_an_added_sound(self):
        self.manifest([{"seconds": 1, "origin": "existing"}])
        original = self.wav("original.wav", [(1, 1.04)])
        silent = self.wav("sfx.wav")
        report = audio.check(self.cues, original=original, sfx=silent)
        self.assertEqual(report["cues"][0]["status"], "onset_in_window")
        self.assertEqual(report["summary"]["needs_review"], 0)
        duplicate = self.wav("duplicate.wav", [(1, 1.04)])
        report = audio.check(self.cues, original=original, sfx=duplicate)
        self.assertEqual(report["cues"][0]["status"], "possible_duplicate_added_activity")

    def test_silent_cue_and_sustained_noise_are_not_valid_action_onsets(self):
        self.manifest([{"id": "silent", "seconds": 1, "origin": "silent"},
                       {"id": "added", "seconds": 2}])
        report = audio.check(self.cues, sfx=self.wav("continuous.wav", [(0, 3)]))
        self.assertEqual(report["cues"][0]["status"], "unexpected_added_activity")
        self.assertEqual(report["cues"][1]["status"], "activity_without_aligned_onset")
        self.manifest([{"seconds": 1, "origin": "silent"}])
        report = audio.check(self.cues, sfx=self.wav("silence.wav"))
        self.assertEqual(report["cues"][0]["status"], "no_added_activity")

    def test_source_time_mapping_removed_ranges_and_half_open_boundary(self):
        self.plan.write_text(json.dumps({"source_duration_s": 6,
                                         "kept_spans_s": [[0, 1], [3, 5]]}), encoding="utf-8")
        self.manifest([{"id": "mapped", "seconds": 3.5},
                       {"id": "cut-end", "seconds": 1},
                       {"id": "removed", "seconds": 2},
                       {"id": "beyond", "seconds": 6}], "source")
        report = audio.check(self.cues, sfx=self.wav("program.wav", [(1.5, 1.55)]), time_map=self.plan)
        self.assertEqual(report["cues"][0]["program_seconds"], 1.5)
        self.assertEqual(report["cues"][0]["status"], "onset_in_window")
        self.assertEqual([cue["status"] for cue in report["cues"]][1:],
                         ["removed", "removed", "source_out_of_range"])

    def test_source_without_mapping_is_rejected(self):
        self.manifest([{"seconds": 1}], "source")
        with self.assertRaisesRegex(ValueError, "require --time-map"):
            audio.check(self.cues, sfx="unused.wav")

    def test_existing_mix_report_absolute_time_is_accepted_but_local_at_is_not(self):
        self.cues.write_text(json.dumps({"events": [{"time": 1, "at": 0.2, "shot": "S03", "type": "click"}]}), encoding="utf-8")
        timebase, cues = audio.load_cues(self.cues)
        self.assertEqual(timebase, "program")
        self.assertEqual(cues[0]["program_seconds"], 1)
        self.assertEqual(cues[0]["shot"], "S03")
        self.cues.write_text('{"events":[{"at":0.2}]}', encoding="utf-8")
        with self.assertRaises(ValueError):
            audio.load_cues(self.cues)

    def test_bounds_and_clipped_measurement_window(self):
        self.manifest([{"id": "start", "seconds": 0}, {"id": "end", "seconds": 3}])
        report = audio.check(self.cues, sfx=self.wav("edge.wav", [(0, 0.04)]))
        self.assertTrue(report["cues"][0]["measurements"]["sfx"]["window_clipped_to_track"])
        self.assertEqual(report["cues"][1]["status"], "track_out_of_range")

    def test_opposing_stereo_channels_do_not_hide_click(self):
        self.manifest([{"seconds": 1}])
        report = audio.check(self.cues, sfx=self.wav("stereo.wav", [(1, 1.04)], channels=2))
        self.assertEqual(report["cues"][0]["status"], "onset_in_window")

    def test_a_shared_onset_cannot_prove_two_distinct_actions(self):
        self.manifest([{"id": "one", "seconds": 1}, {"id": "two", "seconds": 1.04}])
        report = audio.check(self.cues, sfx=self.wav("once.wav", [(1, 1.04)]))
        self.assertEqual([cue["status"] for cue in report["cues"]], ["shared_onset_needs_review"] * 2)

    def test_energy_in_sfx_but_silent_mix_is_reported(self):
        self.manifest([{"seconds": 1}])
        report = audio.check(self.cues, sfx=self.wav("sfx.wav", [(1, 1.04)]),
                             mix=self.wav("mix.wav"))
        self.assertEqual(report["cues"][0]["status"], "final_mix_has_no_activity")

    def test_input_validation_and_bad_time_map(self):
        for value in (True, -1, float("nan"), "00:01"):
            self.manifest([{"seconds": value}])
            with self.assertRaises(ValueError):
                audio.load_cues(self.cues)
        self.manifest([{"seconds": 1, "tolerance_s": 0.2, "search_s": 0.1}])
        with self.assertRaises(ValueError):
            audio.load_cues(self.cues)
        self.manifest([{"id": "same", "seconds": 1}, {"id": "same", "seconds": 2}])
        with self.assertRaises(ValueError):
            audio.load_cues(self.cues)
        self.manifest([{"seconds": 1}], "source")
        self.plan.write_text('{"source_duration_s":3,"kept_spans_s":[[0,2],[1,3]]}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "overlap"):
            audio.load_cues(self.cues, self.plan)

    def test_cli_reproducible_exit_codes_and_read_only_inputs(self):
        self.manifest([{"seconds": 1}])
        path = self.wav("sfx.wav", [(1, 1.04)])
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()}
        command = [sys.executable, "-B", str(Path(audio.__file__)), "--cues", str(self.cues), "--sfx", str(path)]
        first = subprocess.run(command, text=True, capture_output=True)
        second = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()}
        self.assertEqual(before, after)
        self.manifest([{"seconds": 2}])
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
        bad = subprocess.run(command + ["--threshold-dbfs", "nan"], capture_output=True)
        self.assertEqual(bad.returncode, 2)

    def test_no_audio_stream_is_an_error(self):
        bad = self.root / "not-audio.txt"
        bad.write_text("not media", encoding="utf-8")
        self.manifest([{"seconds": 1}])
        with self.assertRaisesRegex(ValueError, "could not decode"):
            audio.check(self.cues, sfx=bad)


if __name__ == "__main__":
    unittest.main()
