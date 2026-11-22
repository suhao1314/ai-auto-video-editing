"""Regression checks for the offline editorial-plan gate."""
from pathlib import Path
import tempfile
import unittest


import check_plan

TEST_TEMP_DIR = Path(tempfile.gettempdir())


def sample_plan(origin="web"):
    asset = {
        "id": "A01",
        "origin": origin,
        "kind": "video",
        "purpose": "Show the claimed action.",
        "state": "candidate",
        "path": "assets/action.mp4",
        "needs_download": True,
        "url": "https://example.test/shared/action",
        "variant": "1080p, 3-5 seconds",
        "license": "Creator approved this use",
        "license_url": "https://example.test/terms",
        "cost": "free",
    }
    plan = {
        "revision": "test-v1",
        "timebase": "audio",
        "end_ms": 1200,
        "lines": [{"id": "L01", "text": "Show the actual result."}],
        "assets": [asset],
        "shots": [{
            "id": "S01", "lines": ["L01"], "from_ms": 0, "to_ms": 1200,
            "assets": ["A01"], "picture": "A01 result frame.",
            "layout": "Full frame.", "motion": "Hold on the result.",
            "transition": "Cut.", "subtitle": "Highlight result.",
            "bgm": "None.", "sfx": "Keep the real click if present.",
        }],
        "approvals": {
            "plan": {"revision": "test-v1", "evidence": "User approved the plan."},
            "downloads": [],
            "edit": None,
        },
    }
    asset_key = check_plan.details(asset)
    plan["approvals"]["downloads"].append({
        "id": "A01", "key": asset_key, "evidence": "User approved A01 only."
    })
    return plan


class CheckPlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(
            prefix="ai-video-editing-check-", dir=TEST_TEMP_DIR if TEST_TEMP_DIR.is_dir() else None
        )
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_download_can_be_approved_before_edit(self):
        plan = sample_plan("user")
        plan["approvals"]["plan"] = None
        # A user-recorded clip may be delivered through a share link. Its source
        # and the permission to fetch it are independent facts.
        check_plan.validate(plan, "download", ["A01"], self.base)
        with self.assertRaisesRegex(ValueError, "包装方案"):
            check_plan.validate(plan, "edit", [], self.base)

    def test_changed_download_selection_requires_its_own_reply(self):
        plan = sample_plan()
        plan["assets"][0]["variant"] = "different footage"
        with self.assertRaisesRegex(ValueError, "尚无用户授权"):
            check_plan.validate(plan, "download", ["A01"], self.base)

    def test_private_original_can_use_project_permission_evidence(self):
        plan = sample_plan("user")
        asset = plan["assets"][0]
        del asset["license_url"]
        asset["permission_evidence"] = "Owner's message approving use in this project"
        plan["approvals"]["downloads"][0]["key"] = check_plan.details(asset)
        check_plan.validate(plan, "download", ["A01"], self.base)
        del asset["permission_evidence"]
        with self.assertRaisesRegex(ValueError, "permission_evidence"):
            check_plan.validate(plan, "download", ["A01"], self.base)

    def test_edit_requires_ready_local_file_after_download(self):
        plan = sample_plan()
        clip = self.base / "assets" / "action.mp4"
        clip.parent.mkdir()
        clip.write_bytes(b"test media")
        plan["assets"][0]["state"] = "ready"
        plan["approvals"]["edit"] = {
            "revision": "test-v1", "evidence": "Assets are ready; start editing."
        }
        check_plan.validate(plan, "edit", [], self.base)

    def test_edit_rejects_unready_or_missing_file(self):
        plan = sample_plan()
        plan["approvals"]["edit"] = {"revision": "test-v1", "evidence": "Start."}
        with self.assertRaisesRegex(ValueError, "尚未备齐"):
            check_plan.validate(plan, "edit", [], self.base)
        plan["assets"][0]["state"] = "ready"
        with self.assertRaisesRegex(ValueError, "本机文件不存在"):
            check_plan.validate(plan, "edit", [], self.base)

    def test_download_requires_itemized_approval(self):
        plan = sample_plan()
        plan["approvals"]["downloads"] = []
        with self.assertRaisesRegex(ValueError, "尚无用户授权"):
            check_plan.validate(plan, "download", ["A01"], self.base)

    def test_shot_cannot_claim_visual_without_registered_asset(self):
        plan = sample_plan()
        plan["shots"][0]["assets"] = []
        with self.assertRaisesRegex(ValueError, "缺少镜头素材"):
            check_plan.validate(plan, "proposal", [], self.base)


if __name__ == "__main__":
    unittest.main()
