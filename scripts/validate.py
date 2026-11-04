"""Validate every region and character file (schema v2), the respect rules, and the safety check
on every prompt each model profile would produce. Exit code 1 on any error.

    uv run scripts/validate.py
"""
from __future__ import annotations

import json
import sys

from jsonschema import Draft202012Validator

import compile_prompts
from lib import (DATA, GROUP_CODES, PRIMARY_SLOTS, SCHEMA, SafetyChecker, UnsafePrompt, is_child, item_problems,
                 items_by_id, load_characters, load_config, load_json, load_policy, load_profiles, load_regions,
                 load_vocab, slot_conflicts)


def age_in_band(age: int, band: str) -> bool:
    if band.endswith("+"):
        return age >= int(band[:-1])
    lo, hi = band.split("-")
    return int(lo) <= age <= int(hi)


LONGEST_PROFILE = "generic-long"


def check_region(slug: str, r: dict, checker: SafetyChecker, errors: list, warnings: list) -> None:
    name = f"region {slug}"
    if r.get("slug") != slug:
        errors.append(f"{name}: slug must match the file name")
    src_ids = [s["id"] for s in r["sources"]]
    comm_ids = [c["id"] for c in r["communities"]]
    seen_rc = {}
    religion_words = {"hindu", "muslim", "christian", "jain", "buddhist", "sikh"}
    for c in r["communities"]:
        key = (c.get("religion"), c.get("culture", "").strip().lower(), c["name"].strip().lower())
        if key in seen_rc:
            errors.append(f"{name}: communities {seen_rc[key]} and {c['id']} have the same name, religion and culture")
        seen_rc[key] = c["id"]
        words = c["name"].split(" (")[0].lower().split()
        # a religion word together with other words outside brackets means region + religion in one name
        if len(words) > 1 and any(w in religion_words for w in words) and c["name"].split(" (")[0].strip() not in (
                "Syrian Christian", "Latin Christian"):
            errors.append(f"{name}: community {c['id']} name '{c['name']}' mixes religion and region; "
                          "put the region in `culture`")
    items = r["wardrobe"] + r["accessories"]
    ids = [i["id"] for i in items]
    for label, lst in (("source", src_ids), ("community", comm_ids), ("item", ids)):
        dupes = {x for x in lst if lst.count(x) > 1}
        if dupes:
            errors.append(f"{name}: duplicate {label} ids {sorted(dupes)}")

    if r["religion_mix"]["source"] not in src_ids:
        errors.append(f"{name}: religion_mix.source is not a source id")
    for sid in r["religion_mix"].get("checked_against", []):
        if sid not in src_ids:
            errors.append(f"{name}: religion_mix.checked_against {sid} is not a source id")
    total = sum(r["religion_mix"]["shares"].values())
    if not 98 <= total <= 101:
        errors.append(f"{name}: religion shares add up to {total:.2f}, expected about 100")

    excluded = {e["name"].lower() for e in r.get("excluded_communities", [])}
    for c in r["communities"]:
        if c["name"].lower() in excluded:
            errors.append(f"{name}: community {c['id']} is in excluded_communities")
        if c.get("religion") and c["religion"] not in r["religion_mix"]["shares"]:
            warnings.append(f"{name}: community {c['id']} religion {c['religion']} not in religion_mix")
        idx = {i["id"]: i for i in r["wardrobe"] + r["accessories"]}
        for grp, wids in c.get("always_wear", {}).items():
            if grp not in GROUP_CODES:
                errors.append(f"{name}: community {c['id']} always_wear has unknown group {grp}")
            for wid in wids:
                it = idx.get(wid)
                if not it:
                    errors.append(f"{name}: community {c['id']} always_wear item {wid} does not exist")
                elif grp not in it["for"] or it.get("community") not in (None, c["id"]):
                    errors.append(f"{name}: community {c['id']} always_wear item {wid} is not for {grp} of this community")
        for k in ("female", "male", "second_female", "second_male"):
            vals = c.get("names", {}).get(k, [])
            if len(vals) != len(set(vals)):
                errors.append(f"{name}: community {c['id']} names.{k} has duplicates")

    for it in items:
        where = f"{name}: item {it['id']}"
        for s in it["sources"]:
            if s not in src_ids:
                errors.append(f"{where}: unknown source {s}")
        if not it["sources"]:
            warnings.append(f"{where}: no source yet")
        if it.get("community") and it["community"] not in comm_ids:
            errors.append(f"{where}: unknown community {it['community']}")
        child = any(g.startswith("child_") for g in it["for"])
        for text in (it["prompt"], it.get("short", "")):
            hits = checker.blocked_terms(text, child)
            if hits:
                errors.append(f"{where}: blocked terms {hits}")
        if child and it["slot"] == "jewellery" and not any(w in it["prompt"] for w in ("stud", "bangle", "kada")):
            errors.append(f"{where}: jewellery for children must be a small stud or a plain bangle/kada")
        if child and "marital" in it.get("meaning", []):
            errors.append(f"{where}: marital item marked for children")
        if "marital" in it.get("meaning", []) and not it.get("requires", {}).get("marital_status"):
            errors.append(f"{where}: marital item needs requires.marital_status")

    by_id = {i["id"]: i for i in items}
    for group, rep in r["best_representation"].items():
        for kind in ("daily", "festive"):
            for outfit in rep.get(kind, []):
                missing = [i for i in outfit if i not in by_id]
                if missing:
                    errors.append(f"{name}: best_representation {group}.{kind} unknown items {missing}")
                    continue
                for i in outfit:
                    if group not in by_id[i]["for"]:
                        errors.append(f"{name}: best_representation {group}.{kind}: {i} is not for {group}")
                    if by_id[i].get("restricted"):
                        errors.append(f"{name}: best_representation {group}.{kind}: {i} is restricted")
                for clash in slot_conflicts([by_id[i] for i in outfit]):
                    errors.append(f"{name}: best_representation {group}.{kind}: {clash}")

    for o in r["occasions"]:
        for cid in o.get("communities", []):
            if cid not in comm_ids:
                errors.append(f"{name}: occasion {o['id']} unknown community {cid}")
        for text in (o["scene"], o.get("scene_short", "")):
            if checker.blocked_terms(text, False):
                errors.append(f"{name}: occasion {o['id']} uses blocked terms")
    sub_ids = {x["id"] for x in r.get("sub_regions", [])}
    for entry in r["settings"] + r["occasions"]:
        for sr in entry.get("sub_regions", []):
            if sr not in sub_ids:
                errors.append(f"{name}: {entry['id']} has unknown sub_region {sr}")
    for s in r["settings"]:
        for cid in s.get("communities", []):
            if cid not in comm_ids:
                errors.append(f"{name}: setting {s['id']} unknown community {cid}")
        if checker.blocked_terms(s["description"] + " " + s.get("short", ""), False):
            errors.append(f"{name}: setting {s['id']} uses blocked terms")

    for h in r.get("heritage", []):
        for s in h["sources"]:
            if s not in src_ids:
                errors.append(f"{name}: heritage {h['id']} unknown source {s}")
        for i in h.get("items", []):
            if i not in by_id:
                errors.append(f"{name}: heritage {h['id']} unknown item {i}")
        if h["decision"] == "not_depicted" and h.get("items"):
            errors.append(f"{name}: heritage {h['id']} is not_depicted but lists wardrobe items")
        if not h["sources"]:
            warnings.append(f"{name}: heritage {h['id']} has no source yet")
    if "heritage" not in r:
        warnings.append(f"{name}: no heritage check recorded (AGENTS.md 2.11)")

    if r["status"] == "reviewed" and not any(rv["kind"] == "maintainer" for rv in r["reviews"]):
        errors.append(f"{name}: status 'reviewed' needs a maintainer entry in reviews")


def check_character(path, c: dict, regions: dict, vocab: dict, cfg: dict, profiles: dict,
                    checker: SafetyChecker, errors: list, warnings: list, seen: set) -> None:
    name = str(path.relative_to(path.parents[2]))
    cid = c["id"]
    if cid in seen:
        errors.append(f"{name}: duplicate id {cid}")
    seen.add(cid)
    if path.stem != cid:
        errors.append(f"{name}: file name must be the id ({cid}.json)")
    region = regions.get(c["region"])
    if not region:
        errors.append(f"{name}: unknown region {c['region']}")
        return
    if not cid.startswith(f"{region['code']}-{GROUP_CODES[c['group']]}-"):
        errors.append(f"{name}: id must start with {region['code']}-{GROUP_CODES[c['group']]}-")
    if c["community"] not in {x["id"] for x in region["communities"]}:
        errors.append(f"{name}: unknown community {c['community']} in {region['name']}")
    if c.get("sub_region") and c["sub_region"] not in {s["id"] for s in region.get("sub_regions", [])}:
        errors.append(f"{name}: unknown sub_region {c['sub_region']}")

    if c.get("occupation"):
        occ = next((o for o in region.get("occupations", []) if o["id"] == c["occupation"]), None)
        if not occ:
            errors.append(f"{name}: unknown occupation {c['occupation']}")
        elif c["group"] not in occ["for"]:
            errors.append(f"{name}: occupation {c['occupation']} is not for {c['group']}")

    bands = vocab["groups"][c["group"]]["age_bands"]
    if c["age_band"] not in bands:
        errors.append(f"{name}: age_band {c['age_band']} not allowed for {c['group']} ({bands})")
    elif not age_in_band(c["age"], c["age_band"]):
        errors.append(f"{name}: age {c['age']} is outside band {c['age_band']}")

    lo, hi = region["look_range"]["skin_tone_mst"]
    for bc in region["look_range"].get("by_community", []):
        if bc["community"] == c["community"] and bc.get("skin_tone_mst"):
            lo, hi = bc["skin_tone_mst"]
    if not lo <= c["look"]["skin_tone_mst"] <= hi:
        warnings.append(f"{name}: skin tone MST {c['look']['skin_tone_mst']} outside expected range {lo}-{hi}")

    items = items_by_id(region)
    for wid in c["wardrobe"]:
        if wid not in items:
            errors.append(f"{name}: wardrobe item {wid} is not in {region['name']}")
            continue
        for p in item_problems(items[wid], c, era=c.get("era")):
            errors.append(f"{name}: cannot wear {wid}: {p}")
    for wid in c.get("always_wear", []):
        if wid not in c["wardrobe"]:
            errors.append(f"{name}: always_wear item {wid} must also be in wardrobe")
    if not any(items.get(w, {}).get("slot") in PRIMARY_SLOTS for w in c["wardrobe"]):
        errors.append(f"{name}: wardrobe needs at least one full or lower garment")

    if is_child(c):
        if c["release"] != "private":
            errors.append(f"{name}: children are always private, release must be 'private'")
        if c["marital_status"] != "single":
            errors.append(f"{name}: children must have marital_status 'single'")
    if c.get("published"):
        if c["release"] != "public":
            errors.append(f"{name}: private characters can never be published")
        missing = [k for k, ok in (("status=approved", c["status"] == "approved"),
                                   ("image_check=passed", c.get("image_check") == "passed"),
                                   ("human_approved=true", c.get("human_approved") is True)) if not ok]
        if missing:
            errors.append(f"{name}: publishing needs {', '.join(missing)}")

    comm = next((x for x in region["communities"] if x["id"] == c["community"]), {})
    for wid in comm.get("always_wear", {}).get(c["group"], []):
        if wid not in c.get("always_wear", []):
            errors.append(f"{name}: {c['community']} {c['group']} must have {wid} in always_wear")

    # Hand-made characters are compiled for every profile. Generated ones are compiled for the
    # longest-prompt profile only: it holds every word the shorter profiles can use, so the safety
    # check still sees everything, and checks stay fast with thousands of characters.
    use = profiles if c.get("origin", "handmade") == "handmade" else {
        k: v for k, v in profiles.items() if k == LONGEST_PROFILE}
    if LONGEST_PROFILE in profiles:
        try:
            compile_prompts.jobs_for(c, region, vocab, checker, profiles[LONGEST_PROFILE], cfg,
                                     stage="festivals", candidates=1)
        except UnsafePrompt as e:
            errors.append(f"{name} [festivals]: {e}")
    for pid, profile in use.items():
        try:
            compile_prompts.jobs_for(c, region, vocab, checker, profile, cfg, stage="all", candidates=1)
        except UnsafePrompt as e:
            errors.append(f"{name} [{pid}]: {e}")
        except (KeyError, IndexError) as e:
            errors.append(f"{name} [{pid}]: cannot build prompts ({type(e).__name__}: {e})")


def validate() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    vocab, cfg, profiles = load_vocab(), load_config(), load_profiles()
    checker = SafetyChecker(load_policy())
    region_v = Draft202012Validator(load_json(SCHEMA / "region.schema.json"))
    char_v = Draft202012Validator(load_json(SCHEMA / "character.schema.json"))

    regions = load_regions()
    codes: dict[str, str] = {}
    valid_regions = {}
    for slug, r in regions.items():
        errs = [f"region {slug}: {e.json_path}: {e.message}" for e in region_v.iter_errors(r)]
        errors += errs
        if errs:
            continue
        if r["code"] in codes:
            errors.append(f"region {slug}: code {r['code']} already used by {codes[r['code']]}")
        codes[r["code"]] = slug
        check_region(slug, r, checker, errors, warnings)
        valid_regions[slug] = r

    from generator import FAMOUS
    seen: set[str] = set()
    for path, c in load_characters():
        if c.get("name") in FAMOUS:
            errors.append(f"{path.name}: {c['name']} is the name of a well-known public figure")
        errs = [f"{path.name}: {e.json_path}: {e.message}" for e in char_v.iter_errors(c)]
        errors += errs
        if not errs:
            check_character(path, c, valid_regions, vocab, cfg, profiles, checker, errors, warnings, seen)

    # cross-state community index: every member must exist, belong to one group, and the group must
    # span at least two regions
    index_path = DATA / "community-index.json"
    if index_path.exists():
        index = json.loads(index_path.read_text(encoding="utf-8"))
        owner: dict[str, str] = {}
        for g in index["groups"]:
            regions_in = set()
            for m in g["members"]:
                slug, _, cid = m.partition(":")
                if slug not in valid_regions or not any(x["id"] == cid for x in valid_regions[slug]["communities"]):
                    errors.append(f"community-index {g['id']}: {m} is not a community in a region file")
                if m in owner:
                    errors.append(f"community-index: {m} is in both {owner[m]} and {g['id']}")
                owner[m] = g["id"]
                regions_in.add(slug)
            if len(regions_in) < 2:
                errors.append(f"community-index {g['id']}: only one region; the index is for communities in several")
    return errors, warnings


def main() -> int:
    errors, warnings = validate()
    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
