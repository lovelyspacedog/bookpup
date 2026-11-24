"""Walk the Trail step machine contract."""

import unittest
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.walk_trail_steps import WALK_TRAIL_STEP_IDS

JS_STEPS = ROOT / "static" / "app-walk-trail.js"


class WalkTrailStepTests(unittest.TestCase):
    def test_canonical_steps(self) -> None:
        self.assertEqual(len(WALK_TRAIL_STEP_IDS), len(set(WALK_TRAIL_STEP_IDS)))
        self.assertEqual(WALK_TRAIL_STEP_IDS[0], "welcome")
        self.assertEqual(WALK_TRAIL_STEP_IDS[-1], "done")
        for required in ("fetch", "tag", "pack", "pack-bots"):
            self.assertIn(required, WALK_TRAIL_STEP_IDS)

    def test_js_steps_match_python(self) -> None:
        text = JS_STEPS.read_text()
        ids = re.findall(r'\n\s+id:\s+"([^"]+)"', text)
        start = text.find("const steps = [")
        self.assertGreater(start, 0)
        block = text[start : text.find("];", start) + 2]
        js_ids = re.findall(r'\n\s+id:\s+"([^"]+)"', block)
        self.assertEqual(js_ids, list(WALK_TRAIL_STEP_IDS))


if __name__ == "__main__":
    unittest.main()