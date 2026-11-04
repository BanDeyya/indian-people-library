"""Turn character files into a batch of image jobs (JSON Lines) for an image backend.

Stages, in order:
  candidates  N front portraits per character with different seeds; a reviewer picks the best
              face and saves it as the character's `reference_image`.
  views       front / three-quarter / side / smile / serious, using the locked reference face.
  outfits     one image per outfit in the character's wardrobe, in a fitting setting or occasion.
  festivals   the character at each festival or rite of their own community (and region-wide ones),
              in the outfit from their wardrobe that is meant for that occasion; festivals with no
              fitting outfit are skipped and listed, never filled with borrowed clothes.

Prompts are written for one model profile (models/<id>.json, default from config). Every prompt
passes the safety check; if one fails, nothing is written.

    uv run scripts/compile_prompts.py --stage candidates --region kerala
    uv run scripts/compile_prompts.py --stage outfits --profile flux
    uv run scripts/compile_prompts.py --stage festivals --region bihar
"""
from __future__ import annotations

import argparse
import json
import sys
import zlib
from datetime import datetime
from pathlib import Path

from lib import (ROOT, SafetyChecker, UnsafePrompt, community, folder_for, is_child, item_problems,
                 items_by_id, load_characters, load_config, load_policy, load_profiles, load_regions,
                 load_vocab, outfits_for, render, representative_outfit)

PLAIN_BG = "plain light grey studio background, soft even light"
PLAIN_BG_SHORT = "plain grey background"

CHILD_SCENES = {
    "home_family": ("at home sitting with their parents and grandparents, ordinary family moment", "at home with family"),
    "school": ("in a simple school classroom with classmates, daytime", "school classroom with classmates"),
    "playing_outdoors": ("playing outdoors in daylight with siblings, parents nearby", "playing outdoors, parents nearby"),
}
# Places of worship are never generic backdrops: they appear only through a community's own
# occasions (festivals, temple/church/mosque/gurdwara visits), so nobody is placed at another faith's site.
SETTING_TYPES = {"rural": {"rural", "home", "nature"}, "urban": {"urban", "work", "home"}}


def seed_for(key: str, n: int) -> int:
    return zlib.crc32(f"{key}-{n}".encode()) % 2_000_000_000


def occasions_for(c: dict, region: dict) -> list[dict]:
    """Festivals this character's community celebrates (empty `communities` = everyone).
    The community's own festivals come first, so a Mising character gets Ali-Aye-Ligang before a
    region-wide festival."""
    def fits(o: dict) -> bool:
        if o.get("marital_status") and c.get("marital_status") not in o["marital_status"]:
            return False
        if o.get("for") and c.get("group") not in o["for"]:
            return False
        return not o.get("sub_regions") or not c.get("sub_region") or c["sub_region"] in o["sub_regions"]
    own = [o for o in region["occasions"] if c.get("community") in o.get("communities", []) and fits(o)]
    shared = [o for o in region["occasions"] if not o.get("communities") and fits(o)]
    return own + shared


FESTIVE = {"festive", "ceremonial", "wedding_guest", "religious_visit"}


def is_festive_outfit(region: dict, outfit: list[str]) -> bool:
    """An outfit is festive if any of its garments (incl. a drape such as a shawl over plain clothes)
    is festive wear that is never everyday, work or school wear."""
    items = items_by_id(region)
    for i in outfit:
        it = items[i]
        if it["slot"] not in ("full", "upper", "lower", "drape"):
            continue
        occ = set(it["occasion"])
        if occ & FESTIVE and not occ & {"daily", "work", "school"}:
            return True
    return False


def pick_setting(c: dict, region: dict, outfit: list[str], k: int, fest_i: int) -> tuple[str, str]:
    """k = outfit number (rotates everyday places); fest_i = festive-outfit number (rotates festivals,
    the character's own community festivals first)."""
    festive = is_festive_outfit(region, outfit)
    items = items_by_id(region)
    worn_for = set().union(*(set(items[i]["occasion"]) for i in outfit
                             if items[i]["slot"] in ("full", "upper", "lower", "drape")))

    def suits(o: dict) -> bool:
        """A scene only fits clothes meant for it (no silk lehenga at an ancestor rite)."""
        return o.get("occasion", "festive") in worn_for

    if is_child(c):
        fests = [f for f in occasions_for(c, region) if f["type"] == "festival" and suits(f)]
        if festive and fests:
            f = fests[fest_i % len(fests)]
            return f"{f['scene']}, the child standing with their parents", f"{f.get('scene_short', f['scene'])}, with parents"
        key = ["home_family", "playing_outdoors", "school"][k % 3]
        return CHILD_SCENES[key]
    if festive:
        fests = [f for f in occasions_for(c, region) if suits(f)]
        if fests:
            f = fests[fest_i % len(fests)]
            return f["scene"], f.get("scene_short", f["scene"])
    occ_entry = next((o for o in region.get("occupations", []) if o["id"] == c.get("occupation")), {})
    if outfit[0] in occ_entry.get("outfit", []) and occ_entry.get("scene"):
        return occ_entry["scene"], occ_entry["scene"]  # work clothes go with the character's own workplace
    allowed = SETTING_TYPES[c["setting"]]
    fits = [s for s in region["settings"] if s["type"] in allowed
            and (not s.get("communities") or c.get("community") in s["communities"])
            and (not s.get("lives_in") or s["lives_in"] == c["setting"])]
    here = [s for s in fits
            if not s.get("sub_regions") or not c.get("sub_region") or c["sub_region"] in s["sub_regions"]]
    places = here or [s for s in fits if not s.get("sub_regions")] or fits or region["settings"]
    s = places[k % len(places)]
    return s["description"], s.get("short", s["description"])


def festival_outfit(c: dict, region: dict, occasion: dict) -> list[str] | None:
    """The character's own outfit for one occasion: its main garment must be meant for that occasion
    (festive, religious_visit, wedding_guest, mourning ...); for a festive occasion a festive-only
    outfit wins over everyday clothes that are also allowed there."""
    items = items_by_id(region)
    want = occasion.get("occasion", "festive")
    fits = [o for o in outfits_for(c, region)
            if want in items[o[0]]["occasion"] and not any(item_problems(items[i], c) for i in o)]
    if not fits:
        return None
    if want in ("festive", "wedding_guest", "ceremonial"):
        fits.sort(key=lambda o: 0 if is_festive_outfit(region, o) else 1)
    return fits[0]


def festival_plan(c: dict, region: dict) -> tuple[list[tuple[dict, list[str]]], list[str]]:
    """(occasion, outfit) pairs for every festival or rite this character takes part in, and the ids
    of those skipped because nothing in the wardrobe is meant for them."""
    plan, skipped = [], []
    for o in occasions_for(c, region):
        if o.get("type") != "festival" and o.get("occasion") != "mourning":
            continue
        outfit = festival_outfit(c, region, o)
        if outfit:
            plan.append((o, outfit))
        else:
            skipped.append(o["id"])
    return plan, skipped


def jobs_for(c: dict, region: dict, vocab: dict, checker: SafetyChecker, profile: dict, cfg: dict, *,
             stage: str, candidates: int) -> list[dict]:
    child = is_child(c)
    base = {
        "character_id": c["id"],
        "profile": profile["id"],
        "folder": folder_for(c, region),
        "release": "private" if child else c["release"],
        "reference_image": c.get("reference_image"),
    }
    jobs: list[dict] = []

    def add(stage_name: str, n: int, size: str, uses_ref: bool, **kw) -> None:
        p = render(c, region, vocab, checker, profile, **kw)
        w, h = profile["sizes"][size]
        jobs.append({**base, "job_id": f"{c['id']}-{stage_name}-{n:02d}", "stage": stage_name,
                     "uses_reference": uses_ref, "width": w, "height": h,
                     "seed": seed_for(f"{c['id']}-{stage_name}", n), **p})

    portrait = representative_outfit(c, region, cfg, "daily")
    if stage in ("candidates", "all"):
        for k in range(candidates):
            add("candidate", k + 1, "portrait", False, outfit_ids=portrait, view="front",
                setting=PLAIN_BG, setting_short=PLAIN_BG_SHORT, framing="head and shoulders portrait")
    if stage in ("views", "all"):
        for k, view in enumerate(vocab["views"], start=1):
            add(f"view-{view}", k, "portrait", True, outfit_ids=portrait, view=view,
                setting=PLAIN_BG, setting_short=PLAIN_BG_SHORT, framing="head and shoulders portrait")
    if stage == "festivals":
        for k, (o, outfit) in enumerate(festival_plan(c, region)[0], start=1):
            scene, short = o["scene"], o.get("scene_short", o["scene"])
            if child:
                scene, short = f"{scene}, the child standing with their parents", f"{short}, with parents"
            add(f"festival-{o['id']}", k, "full", True, outfit_ids=outfit, view="three_quarter",
                setting=scene, setting_short=short, framing="waist-up")
    if stage in ("outfits", "all"):
        fest_i = 0
        for k, outfit in enumerate(outfits_for(c, region), start=1):
            setting, short = pick_setting(c, region, outfit, k, fest_i)
            fest_i += is_festive_outfit(region, outfit)
            add(f"outfit-{outfit[0]}", k, "full", True, outfit_ids=outfit, view="three_quarter",
                setting=setting, setting_short=short, framing="waist-up")
    return jobs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=["candidates", "views", "outfits", "festivals"], required=True)
    ap.add_argument("--profile", help="model profile id (default from config)")
    ap.add_argument("--region", help="only this region slug")
    ap.add_argument("--character", help="only this character id")
    ap.add_argument("--candidates", type=int, help="face candidates per character (default from config)")
    ap.add_argument("--include-private", action="store_true", help="also compile private (child) characters")
    ap.add_argument("--out", type=Path, help="output .jsonl (default out/<stage>-<profile>-<time>.jsonl)")
    args = ap.parse_args()

    cfg, vocab, regions, profiles = load_config(), load_vocab(), load_regions(), load_profiles()
    profile_id = args.profile or cfg["generation"]["profile"]
    if profile_id not in profiles:
        print(f"unknown profile {profile_id}; available: {', '.join(profiles)}", file=sys.stderr)
        return 1
    profile = profiles[profile_id]
    n_cand = args.candidates or cfg["generation"]["candidates"]
    checker = SafetyChecker(load_policy())
    jobs, skipped = [], []
    for _, c in load_characters():
        if args.region and c["region"] != args.region or args.character and c["id"] != args.character:
            continue
        if c["status"] == "retired":
            continue
        if (is_child(c) or c["release"] == "private") and not args.include_private:
            skipped.append(f"{c['id']} (private; use --include-private)")
            continue
        if args.stage != "candidates" and not c.get("reference_image"):
            skipped.append(f"{c['id']} (no reference_image yet; run candidates and pick one)")
            continue
        try:
            jobs += jobs_for(c, regions[c["region"]], vocab, checker, profile, cfg,
                             stage=args.stage, candidates=n_cand)
        except UnsafePrompt as e:
            print(f"BLOCKED, nothing written: {e}", file=sys.stderr)
            return 1

    over = [j["job_id"] for j in jobs if j["over_budget"]]
    out = args.out or ROOT / "out" / f"{args.stage}-{profile_id}-{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for j in jobs:
            f.write(json.dumps(j, ensure_ascii=False) + "\n")
    for s in skipped:
        print(f"skipped {s}")
    if over:
        print(f"WARNING {len(over)} prompt(s) over the token budget; run scripts/lint_prompts.py")
    print(f"{len(jobs)} job(s) -> {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
