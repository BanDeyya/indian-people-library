"""Respect-rule, outfit and token tests (AGENTS.md section 2, plan section 3)."""
from __future__ import annotations

import copy
import re
import unittest

import clip_tokens
import compile_prompts
from lib import (SafetyChecker, item_problems, items_by_id, load_characters, load_config, load_policy,
                 load_profiles, load_regions, load_vocab, representative_outfit, slot_conflicts, tiebreak_order)
from test_safety import adult, child


class RuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.regions, cls.cfg = load_regions(), load_config()
        cls.kl = items_by_id(cls.regions["kerala"])
        cls.pb = items_by_id(cls.regions["punjab"])

    def test_marital_item_needs_married(self) -> None:
        c = adult()
        self.assertTrue(item_problems(self.kl["kl_thali"], c))  # single
        c["marital_status"] = "married"
        self.assertEqual(item_problems(self.kl["kl_thali"], c), [])

    def test_community_item_only_for_that_community(self) -> None:
        c = adult()
        c.update(group="adult_male", region="punjab", community="hindu")
        self.assertTrue(item_problems(self.pb["pb_dastar_m"], c))
        c["community"] = "sikh"
        self.assertEqual(item_problems(self.pb["pb_dastar_m"], c), [])

    def test_restricted_never_allowed(self) -> None:
        item = dict(self.kl["kl_jimikki"], restricted=True)
        self.assertTrue(item_problems(item, adult()))

    def test_child_never_gets_marital_item(self) -> None:
        item = dict(self.kl["kl_thali"], **{"for": ["child_girl"]})
        c = child()
        c["marital_status"] = "married"  # even if a file is edited wrongly
        self.assertIn("marital item on a child", item_problems(item, c))

    def test_era_filter(self) -> None:
        item = dict(self.kl["kl_churidar_f"], era={"from": 2000, "to": None})
        c = adult()
        self.assertTrue(item_problems(item, c, era=1970))
        self.assertEqual(item_problems(item, c, era=2010), [])

    def test_slot_conflicts(self) -> None:
        self.assertTrue(slot_conflicts([self.kl["kl_churidar_f"], self.kl["kl_set_mundu_f"]]))
        self.assertEqual(slot_conflicts([self.kl["kl_set_mundu_f"], self.kl["kl_jimikki"], self.kl["kl_kasu_mala"]]), [])

    def test_representative_outfit_uses_own_wardrobe(self) -> None:
        chars = {c["id"]: c for _, c in load_characters()}
        bodo = chars["AS-AF-0001"]
        outfit = representative_outfit(bodo, self.regions["assam"], self.cfg)
        self.assertTrue(set(outfit) <= set(bodo["wardrobe"]) | set(bodo.get("always_wear", [])))

    def test_sikh_always_wear_in_every_job(self) -> None:
        chars = {c["id"]: c for _, c in load_characters()}
        c = chars["PB-AM-0001"]
        vocab, checker, profiles = load_vocab(), SafetyChecker(load_policy()), load_profiles()
        for pid in ("sdxl-photoreal", "flux"):
            for j in compile_prompts.jobs_for(c, self.regions["punjab"], vocab, checker, profiles[pid], self.cfg,
                                              stage="all", candidates=2):
                self.assertIn("turban", j["prompt"], j["job_id"])

    def test_tiebreak_default_is_state_majority(self) -> None:
        self.assertEqual(tiebreak_order(self.regions["punjab"], {"representation": {"tiebreak": "state_majority"}})[0], "sikh")
        self.assertEqual(tiebreak_order(self.regions["kerala"], {"representation": {"tiebreak": "state_majority"}})[0], "hindu")

    def test_tiebreak_override_only_reorders_present_traditions(self) -> None:
        order = tiebreak_order(self.regions["punjab"], {"representation": {"tiebreak": "christian"}})
        self.assertEqual(order[0], "christian")
        self.assertEqual(tiebreak_order(self.regions["punjab"], {"representation": {"tiebreak": "jain"}})[0], "sikh")


class IdentityItemTests(unittest.TestCase):
    def test_marital_items_never_dropped(self) -> None:
        """A married character's marital items appear in every prompt, for every profile."""
        cfg, vocab, regions, profiles = load_config(), load_vocab(), load_regions(), load_profiles()
        checker = SafetyChecker(load_policy())
        for _, c in load_characters():
            region = regions[c["region"]]
            items = items_by_id(region)
            # worn-every-day marital jewellery/accessories (a festive marital *garment* is only worn on its day)
            marital = [w for w in c["wardrobe"] if "marital" in items[w].get("meaning", [])
                       and items[w]["slot"] in ("jewellery", "accessory") and not item_problems(items[w], c)]
            for pid, prof in profiles.items():
                for j in compile_prompts.jobs_for(c, region, vocab, checker, prof, cfg, stage="all", candidates=1):
                    for w in marital:
                        text = items[w]["prompt"] if prof["variant"] == "long" else items[w].get("short") or items[w]["prompt"]
                        self.assertIn(text, j["prompt"], f"{j['job_id']} [{pid}] lost {w}")


class OccasionRuleTests(unittest.TestCase):
    def test_marital_festivals_respect_status(self) -> None:
        """Festivals limited by marital status (e.g. Gangaur, Karva Chauth) never pick other characters."""
        cfg, vocab, regions, profiles = load_config(), load_vocab(), load_regions(), load_profiles()
        checker = SafetyChecker(load_policy())
        for _, c in load_characters():
            region = regions[c["region"]]
            limited = [o for o in region["occasions"] if o.get("marital_status") and c["marital_status"] not in o["marital_status"]]
            for j in compile_prompts.jobs_for(c, region, vocab, checker, profiles["flux"], cfg, stage="outfits", candidates=1):
                for o in limited:
                    self.assertNotIn(o["scene"], j["prompt"], f"{j['job_id']} placed at {o['id']}")

    def test_group_limited_festivals(self) -> None:
        """Festivals limited to some groups (e.g. Sama Chakeva for girls and women) never pick others."""
        cfg, vocab, regions, profiles = load_config(), load_vocab(), load_regions(), load_profiles()
        checker = SafetyChecker(load_policy())
        for _, c in load_characters():
            region = regions[c["region"]]
            limited = [o for o in region["occasions"] if o.get("for") and c["group"] not in o["for"]]
            if not limited:
                continue
            for j in compile_prompts.jobs_for(c, region, vocab, checker, profiles["generic-long"], cfg,
                                              stage="outfits", candidates=1):
                for o in limited:
                    self.assertNotIn(o["scene"], j["prompt"], f"{j['job_id']} placed at {o['id']}")

    def test_widowed_gangaur_case(self) -> None:
        import copy
        cfg, vocab, regions, profiles = load_config(), load_vocab(), load_regions(), load_profiles()
        c = copy.deepcopy({x["id"]: x for _, x in load_characters()}["RJ-AF-0001"])
        c["marital_status"] = "widowed"
        c["wardrobe"] = [w for w in c["wardrobe"] if w not in ("rj_bichiya",)]
        jobs = compile_prompts.jobs_for(c, regions["rajasthan"], vocab, SafetyChecker(load_policy()), profiles["flux"], cfg,
                                        stage="outfits", candidates=1)
        self.assertFalse(any("Gangaur" in j["prompt"] for j in jobs))


class WorshipPlaceTests(unittest.TestCase):
    WORDS = {"gurdwara": "sikh", "church": "christian", "mosque": "muslim", "temple": "hindu", "namghar": "hindu",
             "stupa": "buddhist", "monastery": "buddhist", "gompa": "buddhist", "imambara": "muslim"}

    def test_nobody_at_another_faiths_place_of_worship(self) -> None:
        cfg, vocab, regions, profiles = load_config(), load_vocab(), load_regions(), load_profiles()
        checker = SafetyChecker(load_policy())
        from lib import community
        for _, c in load_characters():
            region = regions[c["region"]]
            religion = community(region, c["community"]).get("religion")
            for pid in ("sdxl-photoreal", "flux"):
                for j in compile_prompts.jobs_for(c, region, vocab, checker, profiles[pid], cfg, stage="all", candidates=1):
                    scene = j["prompt"]
                    for text in c["look"].values():  # face/hair words like "scar on his temple" are not places
                        scene = scene.replace(str(text), "")
                    for word, faith in self.WORDS.items():
                        if re.search(rf"\b{word}\b", scene.lower()):
                            self.assertEqual(religion, faith, f"{j['job_id']} [{pid}] is at a {word}")


class SettingFilterTests(unittest.TestCase):
    def test_community_and_home_settings_only_for_fitting_characters(self) -> None:
        """A Koliwada is only for Koli characters; a village home only for characters who live in a village."""
        cfg, vocab, regions, profiles = load_config(), load_vocab(), load_regions(), load_profiles()
        checker = SafetyChecker(load_policy())
        for _, c in load_characters():
            region = regions[c["region"]]
            wrong = [s for s in region["settings"]
                     if (s.get("communities") and c["community"] not in s["communities"])
                     or (s.get("lives_in") and s["lives_in"] != c["setting"])]
            for j in compile_prompts.jobs_for(c, region, vocab, checker, profiles["generic-long"], cfg,
                                              stage="outfits", candidates=1):
                for s in wrong:
                    self.assertNotIn(s["description"], j["prompt"], f"{j['job_id']} placed at {s['id']}")


class TokenTests(unittest.TestCase):
    def test_known_counts(self) -> None:
        self.assertEqual(clip_tokens.count("a photo of a cat"), 5)
        self.assertEqual(clip_tokens.count(""), 0)

    def test_short_profiles_fit_budget(self) -> None:
        cfg, vocab, regions, profiles = load_config(), load_vocab(), load_regions(), load_profiles()
        checker = SafetyChecker(load_policy())
        for pid, prof in profiles.items():
            if prof["long_prompt"] != "truncate":
                continue
            for _, c in load_characters():
                for j in compile_prompts.jobs_for(c, regions[c["region"]], vocab, checker, prof, cfg,
                                                  stage="all", candidates=1):
                    self.assertLessEqual(j["tokens"], 75, f"{pid} {j['job_id']}")
                    self.assertIn(c["look"]["signature_mark"], j["prompt"])


class PlaceNameTests(unittest.TestCase):
    def test_sub_region_place_replaces_long_region_name(self) -> None:
        from lib import _subject, load_regions
        r = load_regions()["dnh-dd"]
        c = {"group": "adult_female", "age": 30, "community": "hindu", "sub_region": "daman"}
        self.assertTrue(_subject(c, r).endswith("from Daman"))
        c2 = {"group": "adult_female", "age": 30, "community": "hindu", "sub_region": "nowhere"}
        self.assertTrue(_subject(c2, r).endswith(f"from {r['name']}"))


class FestivalStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.regions = load_regions()
        cls.chars = [c for _, c in load_characters()]

    def test_outfit_is_meant_for_the_occasion(self) -> None:
        for c in self.chars:
            r = self.regions[c["region"]]
            items = items_by_id(r)
            for o, outfit in compile_prompts.festival_plan(c, r)[0]:
                self.assertIn(o.get("occasion", "festive"), items[outfit[0]]["occasion"], (c["id"], o["id"]))

    def test_only_own_or_shared_festivals(self) -> None:
        for c in self.chars:
            r = self.regions[c["region"]]
            for o, _ in compile_prompts.festival_plan(c, r)[0]:
                comms = o.get("communities")
                self.assertTrue(not comms or c["community"] in comms, (c["id"], o["id"]))

    def test_mourning_rite_never_in_festive_only_clothes(self) -> None:
        for c in self.chars:
            r = self.regions[c["region"]]
            for o, outfit in compile_prompts.festival_plan(c, r)[0]:
                if o.get("occasion") == "mourning":
                    self.assertFalse(compile_prompts.is_festive_outfit(r, outfit), (c["id"], o["id"]))

    def test_children_are_with_parents(self) -> None:
        from lib import load_config, load_policy, load_profiles, load_vocab
        cfg, vocab, profiles = load_config(), load_vocab(), load_profiles()
        prof = profiles["generic-long"]
        checker = SafetyChecker(load_policy())
        kids = [c for c in self.chars if c["group"].startswith("child") and c.get("origin", "handmade") == "handmade"]
        if not kids:  # no child character files present; test the fixture child instead
            kids = [child()]
        for c in kids:
            for j in compile_prompts.jobs_for(c, self.regions[c["region"]], vocab, checker, prof, cfg,
                                              stage="festivals", candidates=1):
                self.assertIn("with their parents", j["prompt"])


if __name__ == "__main__":
    unittest.main()
