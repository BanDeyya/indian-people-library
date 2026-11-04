"""Safety tests. These must always pass before anything is generated or published.

    uv run python -m unittest discover -s scripts -p "test_*.py"
"""
from __future__ import annotations

import copy
import unittest

import compile_prompts
from lib import (SafetyChecker, UnsafePrompt, load_config, load_policy, load_profiles, load_regions,
                 load_vocab, render)


def adult() -> dict:
    return {"schema_version": 2, "id": "KL-AF-9999", "name": "Test", "region": "kerala", "community": "hindu",
            "group": "adult_female", "age_band": "26-35", "age": 30, "setting": "urban", "marital_status": "single",
            "release": "private", "status": "draft", "language": ["Malayalam"], "wardrobe": ["kl_churidar_f"],
            "look": {"skin_tone_mst": 6, "face": "oval face", "hair": "long black hair",
                     "build": "average", "signature_mark": "mole on cheek"}}


def child() -> dict:
    c = adult()
    c.update(id="KL-CG-9999", group="child_girl", age_band="6-9", age=8, wardrobe=["kl_pattu_pavada_g"])
    return c


class SafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checker = SafetyChecker(load_policy())
        cls.vocab, cls.regions, cls.cfg = load_vocab(), load_regions(), load_config()
        cls.profiles = load_profiles()

    def prompt(self, c: dict, profile: str = "flux") -> dict:
        return render(c, self.regions["kerala"], self.vocab, self.checker, self.profiles[profile],
                      outfit_ids=c["wardrobe"], view="front", setting="plain background",
                      setting_short=None, framing="portrait")

    def test_sexual_words_blocked_for_adults_in_every_profile(self) -> None:
        for pid in self.profiles:
            for bad in ["seductive look", "visible cleavage", "lingerie", "NSFW"]:
                c = adult()
                c["look"]["face"] = bad
                with self.assertRaises(UnsafePrompt, msg=f"{pid}: {bad}"):
                    self.prompt(c, pid)

    def test_child_extra_words_blocked(self) -> None:
        for bad in ["beautiful face", "wearing lipstick", "model pose", "bride"]:
            c = child()
            c["look"]["face"] = bad
            with self.assertRaises(UnsafePrompt, msg=bad):
                self.prompt(c)

    def test_child_words_allowed_for_adults(self) -> None:
        c = adult()
        c["look"]["face"] = "beautiful oval face"
        self.prompt(c)  # must not raise

    def test_whole_word_matching(self) -> None:
        self.assertEqual(self.checker.blocked_terms("gold bracelet, shirt button, Essex", child=False), [])

    def test_child_negative_includes_child_safety(self) -> None:
        p = self.prompt(child(), "sdxl-photoreal")
        self.assertIn("makeup", p["negative_prompt"])
        self.assertIn("nsfw", p["negative_prompt"])

    def test_child_long_prompt_has_child_positive(self) -> None:
        self.assertIn("age-appropriate", self.prompt(child(), "generic-long")["prompt"])

    def test_adult_negative_has_safety(self) -> None:
        p = self.prompt(adult(), "sdxl-photoreal")
        self.assertIn("nude", p["negative_prompt"])
        self.assertNotIn("makeup", p["negative_prompt"])

    def test_children_always_private_in_jobs(self) -> None:
        c = child()
        c["release"] = "public"  # even if someone edits the file wrongly
        jobs = compile_prompts.jobs_for(c, self.regions["kerala"], self.vocab, self.checker,
                                        self.profiles["sdxl-photoreal"], self.cfg, stage="candidates", candidates=2)
        self.assertTrue(all(j["release"] == "private" for j in jobs))
        self.assertTrue(all(j["folder"].startswith("Indian People Library - Private/") for j in jobs))

    def test_child_outfit_scenes_have_family(self) -> None:
        c = child()
        c["wardrobe"] = ["kl_pattu_pavada_g", "kl_small_studs"]
        for pid in ("sdxl-photoreal", "flux"):
            jobs = compile_prompts.jobs_for(c, self.regions["kerala"], self.vocab, self.checker,
                                            self.profiles[pid], self.cfg, stage="outfits", candidates=1)
            self.assertTrue(jobs)
            for j in jobs:
                if "setting" not in j["dropped"]:
                    self.assertRegex(j["prompt"], "parents|family|classmates")

    def test_safety_terms_cannot_be_dropped_from_negatives(self) -> None:
        # Short profiles drop positive safety words from the prompt; negatives must still carry safety.
        for pid, prof in self.profiles.items():
            if prof["negatives"]:
                self.assertIn("nsfw", self.prompt(adult(), pid)["negative_prompt"], pid)


if __name__ == "__main__":
    unittest.main()
