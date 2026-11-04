"""Tests for the character generator (scripts/generator.py, scripts/new_character.py)."""
from __future__ import annotations

import random
import unittest

import new_character
from compile_prompts import festival_plan
from generator import draft, own_items, skin_range, peers
from lib import CHILD_GROUPS, item_problems, items_by_id, load_characters, load_regions, load_vocab

CASES = [("bihar", "maithil", "adult_female"), ("punjab", "sikh", "adult_male"), ("punjab", "sikh", "child_boy"),
         ("kerala", "syrian_christian", "adult_female"), ("nagaland", "angami", "adult_female"),
         ("west-bengal", "bengali_hindu", "old_female"), ("jammu-kashmir", "kashmiri_muslim", "child_girl"),
         ("mizoram", "mizo", "old_male")]


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.regions, cls.vocab = load_regions(), load_vocab()
        cls.hand = [c for _, c in load_characters() if c.get("origin", "handmade") == "handmade"]
        cls.made = []
        for slug, comm, group in CASES:
            r = cls.regions[slug]
            if not any(c["id"] == comm for c in r["communities"]):
                continue
            for k in range(25):
                rng = random.Random(f"{slug}{comm}{group}{k}")
                ch, _ = draft(rng, r, comm, group, cls.vocab, list(cls.hand), festival_plan, set(), 9000 + k)
                cls.made.append((r, ch))

    def test_cases_exist(self) -> None:
        self.assertGreater(len(self.made), 150)

    def test_every_item_allowed(self) -> None:
        for r, ch in self.made:
            items = items_by_id(r)
            for i in ch["wardrobe"]:
                self.assertEqual(item_problems(items[i], ch), [], f"{ch['id']} {i}")

    def test_marital_items_only_when_married(self) -> None:
        for r, ch in self.made:
            items = items_by_id(r)
            if ch["marital_status"] != "married":
                self.assertFalse([i for i in ch["wardrobe"] if "marital" in items[i].get("meaning", [])], ch["id"])

    def test_children_private_and_single(self) -> None:
        kids = [ch for _, ch in self.made if ch["group"] in CHILD_GROUPS]
        self.assertTrue(kids)
        for ch in kids:
            self.assertEqual((ch["release"], ch["marital_status"]), ("private", "single"))
            self.assertNotIn("occupation", ch)

    def test_always_wear_present(self) -> None:
        for r, ch in self.made:
            comm = next(c for c in r["communities"] if c["id"] == ch["community"])
            for i in comm.get("always_wear", {}).get(ch["group"], []):
                self.assertIn(i, ch["wardrobe"], ch["id"])

    def test_own_dress_first(self) -> None:
        for r, ch in self.made:
            own = {i["id"] for i in own_items(r, ch["community"]) if ch["group"] in i["for"]}
            items = items_by_id(r)
            if any(items[i]["slot"] in ("full", "lower") for i in own):
                self.assertTrue(set(ch["wardrobe"]) & own, ch["id"])

    def test_names_from_community_list(self) -> None:
        for r, ch in self.made:
            comm = next(c for c in r["communities"] if c["id"] == ch["community"])
            n = comm["names"]
            allowed = set(n["female"] + n["male"] + n.get("second_female", []) + n.get("second_male", []))
            given = n["female"] + n["male"]  # given names may have two words (e.g. Ann Mary)
            ok = any(ch["name"] == g or (ch["name"].startswith(g + " ") and ch["name"][len(g) + 1:] in allowed)
                     for g in given)
            self.assertTrue(ok, ch["name"])

    def test_skin_tone_in_range(self) -> None:
        for r, ch in self.made:
            lo, hi = skin_range(r, ch["community"], peers(self.hand, r, ch["community"]))
            self.assertTrue(lo <= ch["look"]["skin_tone_mst"] <= hi, ch["id"])

    def test_own_festivals_have_clothes(self) -> None:
        for r, ch in self.made:
            _, skipped = festival_plan(ch, r)
            occ = {o["id"]: o for o in r["occasions"]}
            self.assertFalse([s for s in skipped if occ[s].get("occasion") != "mourning"
                              and occ[s].get("communities")], ch["id"])

    def test_share_keeps_total(self) -> None:
        self.assertEqual(sum(new_character.share({"a": 5, "b": 3, "c": 1}, 17).values()), 17)
        self.assertEqual(new_character.share({"a": 1}, 4), {"a": 4})


if __name__ == "__main__":
    unittest.main()
