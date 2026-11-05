"""Catalogue site data: children and private characters never reach the site."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import build_site
from lib import load_characters


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        build_site.build(cls.out)
        cls.index = json.loads((cls.out / "data" / "index.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_no_children_or_private(self) -> None:
        private = {c["id"] for _, c in load_characters() if c.get("release") != "public"}
        ids = {r[0] for r in self.index["rows"]}
        self.assertTrue(ids)
        self.assertFalse(ids & private)
        detail_ids = {c["id"] for f in (self.out / "data" / "regions").glob("*.json")
                      for c in json.loads(f.read_text(encoding="utf-8"))["characters"]}
        self.assertEqual(detail_ids, ids)

    def test_every_character_has_prompt_and_clothes(self) -> None:
        for f in (self.out / "data" / "regions").glob("*.json"):
            for c in json.loads(f.read_text(encoding="utf-8"))["characters"]:
                self.assertTrue(c["prompt"], c["id"])
                self.assertTrue(c["wardrobe"], c["id"])

    def test_all_regions(self) -> None:
        self.assertEqual(len(self.index["regions"]), 36)



class DatasetTests(unittest.TestCase):
    def test_dataset_has_no_private_characters(self) -> None:
        import build_dataset
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ds"
            build_dataset.build(out)
            ids = {json.loads(line)["id"] for line in (out / "characters.jsonl").open(encoding="utf-8")}
            private = {c["id"] for _, c in load_characters() if c.get("release") != "public"}
            self.assertTrue(ids)
            self.assertFalse(ids & private)
            self.assertIn("license: cc-by-4.0", (out / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
