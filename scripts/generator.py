"""Draft new characters from a region's data, following the library's rules.

Used by scripts/new_character.py. Everything a character gets comes from the region file and from
the hand-made (reviewed) characters of the same community:

1. Clothes: first what hand-made characters of the same community and gender wear (reviewed
   choices), then the community's own items, then the region's best representation, then shared
   clothes. A clear warning is returned when a community has no dress of its own yet.
2. Rules: nothing restricted, marital symbols only for married characters, community items only for
   that community, the community's always-wear items (e.g. a Sikh man's dastar and kara), children
   always private and single, clothes for every festival of the character's own community.
3. Look: skin tone inside the community's real range, face, eyes, hair and build drawn from the
   community's hand-made characters, one fixed signature mark.
4. Name: a given name from the community's `names` list, never a caste or clan surname.
"""
from __future__ import annotations

import random
from collections import Counter

from lib import CHILD_GROUPS, GROUP_CODES, PRIMARY_SLOTS, is_child, item_problems, items_by_id

ORDER = ["schema_version", "id", "name", "region", "sub_region", "community", "group", "age_band", "age",
         "setting", "marital_status", "occupation", "look", "wardrobe", "always_wear", "language",
         "voice_notes", "release", "published", "status", "reference_image", "output_folder",
         "image_check", "human_approved", "origin", "notes"]

FEMALE = {"adult_female", "old_female", "child_girl"}
BAND_WEIGHTS = {"18-25": 22, "26-35": 30, "36-50": 33, "51-64": 15, "65-74": 75, "75+": 25,
                "6-9": 50, "10-12": 50}
MARKS = ["small mole on {p} left cheek", "small mole on {p} right cheek", "small mole above {p} lip",
         "mole on {p} chin", "faint scar on {p} left eyebrow", "small scar on {p} chin",
         "dimple on {p} left cheek", "dimple on {p} right cheek", "small mole near {p} right eye",
         "small birthmark on {p} forehead", "mole near {p} left ear", "small scar on {p} right hand"]
DEFAULT_HAIR = {
    "adult_female": ["long black hair in a plait", "long black hair in a low bun", "shoulder-length black hair",
                     "long straight black hair"],
    "old_female": ["grey hair in a bun", "greying hair in a low bun", "white hair in a small bun"],
    "adult_male": ["short black hair", "short black hair neatly combed", "short wavy black hair"],
    "old_male": ["short grey hair", "thin white hair", "short white hair"],
    "child_girl": ["black hair in two plaits", "black hair in a ponytail", "short black hair in a bob"],
    "child_boy": ["short black hair", "short neatly combed black hair"],
}
DEFAULT_FACIAL = {"adult_male": ["clean-shaven", "trimmed moustache", "light stubble", "short beard"],
                  "old_male": ["white moustache", "clean-shaven", "short white beard"]}


# Full names of well-known public figures that a name list could produce; never given to a character.
FAMOUS = {"Imran Khan", "Salman Khan", "Aamir Khan", "Manmohan Singh", "Bhagat Singh", "Harbhajan Singh",
          "Yuvraj Singh", "Milkha Singh", "Navjot Singh", "Mahendra Singh", "Jaspal Bhatti", "Nitish Kumar",
          "Lalu Prasad", "Kiran Bedi", "Kalpana Chawla", "Sania Mirza", "Mary Kom", "Pema Khandu",
          "Hemant Soren", "Shibu Soren", "Babulal Marandi", "Neiphiu Rio", "Conrad Sangma", "Manik Saha",
          "Biren Singh", "Zoramthanga", "Lalduhoma", "Lalthanhawla", "Omar Abdullah", "Farooq Abdullah",
          "Mehbooba Mufti", "Sharad Pawar", "Uddhav", "Revanth Reddy", "Jagan", "Mamata Banerjee"}


def pronoun(group: str) -> str:
    return "her" if group in FEMALE else "his"


def _pick(rng: random.Random, seq, default=None):
    seq = [s for s in seq if s]
    return rng.choice(seq) if seq else default


def peers(chars: list[dict], region: dict, community: str) -> list[dict]:
    """Hand-made characters of this community (the reviewed examples the generator learns from)."""
    return [c for c in chars if c["region"] == region["slug"] and c["community"] == community
            and c.get("origin", "handmade") == "handmade"]


def own_items(region: dict, community: str) -> list[dict]:
    return [i for i in region["wardrobe"] + region["accessories"]
            if i.get("community") == community and not i.get("restricted")]


def skin_range(region: dict, community: str, ps: list[dict]) -> tuple[int, int]:
    lo, hi = region["look_range"]["skin_tone_mst"]
    for bc in region["look_range"].get("by_community", []):
        if bc["community"] == community and bc.get("skin_tone_mst"):
            lo, hi = bc["skin_tone_mst"]
    tones = [p["look"]["skin_tone_mst"] for p in ps]
    if tones:  # stay near the reviewed examples, but never outside the community's range
        lo, hi = max(lo, min(tones) - 1), min(hi, max(tones) + 1)
    return lo, hi


def _same_sex(group: str, other: str) -> bool:
    return (group in FEMALE) == (other in FEMALE)


def _stage(group: str) -> str:
    return "child" if group in CHILD_GROUPS else ("old" if group.startswith("old") else "adult")


def look_for(rng: random.Random, region: dict, community: str, group: str, ps: list[dict]) -> dict:
    same = [p for p in ps if _same_sex(group, p["group"])]
    same_stage = [p for p in same if _stage(p["group"]) == _stage(group)]
    lo, hi = skin_range(region, community, ps)
    hair_pool = [p["look"]["hair"] for p in same_stage] or DEFAULT_HAIR[group]
    look = {
        "skin_tone_mst": rng.randint(lo, hi),
        "face": _pick(rng, [p["look"]["face"] for p in same or ps], "oval face"),
        "eyes": _pick(rng, [p["look"].get("eyes") for p in ps], "dark eyes"),
        "hair": rng.choice(hair_pool),
        "build": _pick(rng, [p["look"]["build"] for p in same_stage or same], "average"),
        "signature_mark": rng.choice(MARKS).format(p=pronoun(group)),
    }
    if group in ("adult_male", "old_male"):
        look["facial_hair"] = _pick(rng, [p["look"].get("facial_hair") for p in same_stage],
                                    None) or rng.choice(DEFAULT_FACIAL[group])
    return look


def age_for(rng: random.Random, vocab: dict, group: str) -> tuple[str, int]:
    bands = vocab["groups"][group]["age_bands"]
    band = rng.choices(bands, weights=[BAND_WEIGHTS.get(b, 10) for b in bands])[0]
    if band.endswith("+"):
        lo = int(band[:-1]); hi = lo + 13
    else:
        lo, hi = (int(x) for x in band.split("-"))
    return band, rng.randint(lo, hi)


def marital_for(rng: random.Random, group: str, band: str) -> str:
    """Rough shares by age; widowhood is far more common for women than for men in India."""
    if group in CHILD_GROUPS:
        return "single"
    women = group in FEMALE
    table = {"18-25": [("single", 70), ("married", 30)] if women else [("single", 85), ("married", 15)],
             "26-35": [("single", 20), ("married", 80)] if women else [("single", 35), ("married", 65)],
             "36-50": [("single", 4), ("married", 88), ("widowed", 8)] if women else
                      [("single", 4), ("married", 94), ("widowed", 2)],
             "51-64": [("married", 78), ("widowed", 20), ("single", 2)] if women else
                      [("married", 92), ("widowed", 6), ("single", 2)],
             "65-74": [("married", 58), ("widowed", 42)] if women else [("married", 85), ("widowed", 15)],
             "75+": [("married", 35), ("widowed", 65)] if women else [("married", 70), ("widowed", 30)]}
    opts = table[band]
    return rng.choices([o for o, _ in opts], weights=[w for _, w in opts])[0]


def name_for(rng: random.Random, comm: dict, group: str, taken, marital: str = "single") -> str:
    """A full name from the community list; prefers one not yet used in the region. `taken` may be a
    set or a Counter of names already used. Devi/Kumari follow marital status (Kumari before marriage)."""
    names = comm["names"]
    female = group in FEMALE
    used = taken if isinstance(taken, Counter) else Counter(taken)
    tries = []
    for _ in range(60):
        given = rng.choice(names["female" if female else "male"])
        second = None
        pool = names.get("second_female" if female else "second_male") or []
        if pool and (names.get("second_always") or rng.random() < 0.4):
            second = rng.choice(pool)
        elif names.get("second_father") and rng.random() < 0.4 and group not in CHILD_GROUPS:
            second = rng.choice(names["male"])
        pool2 = names.get("second_female") or []
        if female and second == "Devi" and marital == "single":
            second = "Kumari" if "Kumari" in pool2 else None  # Devi is taken on after marriage
        elif female and second == "Kumari" and marital != "single" and "Devi" in pool2:
            second = "Devi"
        full = f"{given} {second}" if second and second != given else given
        if full in FAMOUS:
            continue
        if not used[full]:
            return full
        tries.append(full)
    return min(tries, key=lambda n: used[n]) if tries else given  # every combination used: real people share names too


def _fits_setting(item: dict, setting: str) -> bool:
    return item["setting"] in ("both", setting)


def wardrobe_for(rng: random.Random, region: dict, char: dict, ps: list[dict], best: dict,
                 plan_fn) -> tuple[list[str], list[str], list[str]]:
    """(wardrobe, always_wear, warnings). plan_fn(char, region) -> (plan, skipped festival ids)."""
    items = items_by_id(region)
    group, comm_id = char["group"], char["community"]
    warnings = []

    def ok(i: dict) -> bool:
        if ("marital" in i.get("meaning", []) and not i.get("requires")
                and char["marital_status"] != "married"):
            return False  # a marital symbol with no stated requirement: only while married
        return not item_problems(i, char) and _fits_setting(i, char["setting"])

    chosen: list[str] = []

    def add(iid: str) -> None:
        if iid in items and iid not in chosen and ok(items[iid]):
            chosen.append(iid)

    comm = next(c for c in region["communities"] if c["id"] == comm_id)
    always = [i for i in comm.get("always_wear", {}).get(group, []) if i in items and ok(items[i])]
    for a in always:
        add(a)

    # 1) what reviewed characters of this community and sex wear
    same = [p for p in ps if _same_sex(group, p["group"]) and _stage(p["group"]) == _stage(group)] or \
           [p for p in ps if _same_sex(group, p["group"])]
    pool = Counter(w for p in same for w in p["wardrobe"])
    primaries = [w for w, _ in pool.most_common() if w in items and items[w]["slot"] in PRIMARY_SLOTS and ok(items[w])]
    rng.shuffle(primaries)
    for w in primaries[: rng.randint(2, 3)]:
        add(w)
    # 2) the community's own dress
    own = [i for i in own_items(region, comm_id) if ok(i)]
    own_primary = [i["id"] for i in own if i["slot"] in PRIMARY_SLOTS]
    others_have = any(i.get("community") and i.get("community") != comm_id and group in i["for"]
                      for i in region["wardrobe"])
    if others_have and not any(group in i["for"] for i in region["wardrobe"] if i.get("community") == comm_id):
        warnings.append(f"{region['slug']}/{comm_id}/{group}: no dress of its own yet; used shared clothes")
    for iid in own_primary:
        if rng.random() < 0.8 or items[iid].get("representative"):
            add(iid)
    # 3) best representation for the group, daily then festive
    rep = region.get("best_representation", {}).get(group, {})
    for occ in ("daily", "festive"):
        opts = [o for o in rep.get(occ, []) if all(i in items and ok(items[i]) for i in o)]
        opts.sort(key=lambda o: 0 if any(items[i].get("community") == comm_id for i in o) else 1)
        if opts and not any(occ in items[c]["occasion"] for c in chosen if items[c]["slot"] in PRIMARY_SLOTS):
            for i in opts[0]:
                add(i)

    # an upper garment when only a lower one was chosen
    if any(items[c]["slot"] == "lower" for c in chosen) and not any(items[c]["slot"] == "upper" for c in chosen):
        ups = [w for w in pool if w in items and items[w]["slot"] == "upper" and ok(items[w])] or \
              [i["id"] for i in region["wardrobe"] if i["slot"] == "upper" and ok(i)]
        if ups:
            add(ups[0])

    # 4) shared clothes until there is an everyday and a festive garment
    def has(occs: set[str]) -> bool:
        return any(set(items[c]["occasion"]) & occs for c in chosen if items[c]["slot"] in PRIMARY_SLOTS)
    for need in ({"daily"}, {"festive"}):
        if not has(need):
            cand = [i for i in region["wardrobe"] if i["slot"] in PRIMARY_SLOTS and ok(i) and set(i["occasion"]) & need]
            cand.sort(key=lambda i: (0 if i.get("community") == comm_id else 1, 0 if i.get("representative") else 1))
            if cand:
                add(cand[0]["id"])

    # accessories, head and outer layers that reviewed peers or the community use
    extras = [w for w, _ in pool.most_common() if w in items and items[w]["slot"] not in PRIMARY_SLOTS
              and items[w]["slot"] != "upper" and ok(items[w])]
    extras += [i["id"] for i in own if i["slot"] not in PRIMARY_SLOTS and i["id"] not in extras]
    for w in extras:
        it = items[w]
        marital = "marital" in it.get("meaning", []) or it.get("requires")
        if marital or rng.random() < 0.6:
            add(w)
    # marital items of the community for married characters even if no peer showed one
    if char["marital_status"] == "married":
        for i in region["accessories"]:
            if "marital" in i.get("meaning", []) and ok(i) and (i.get("community") == comm_id):
                add(i["id"])
    # seasonal layer from the region if none yet
    if not any(set(items[c].get("season", ["any"])) - {"any"} for c in chosen):
        layers = [i for i in region["wardrobe"] if i["slot"] in ("outer", "drape") and ok(i)
                  and set(i.get("season", ["any"])) - {"any"} and not i.get("community")]
        if layers and rng.random() < 0.6:
            add(layers[0]["id"])

    # a second garment so the character is not stuck in one outfit
    if sum(1 for c in chosen if items[c]["slot"] in PRIMARY_SLOTS) < 2:
        cand = [i for i in region["wardrobe"] if i["slot"] in PRIMARY_SLOTS and ok(i) and i["id"] not in chosen]
        cand.sort(key=lambda i: (0 if i["id"] in pool else 1, 0 if i.get("community") == comm_id else 1,
                                 1 if i.get("community") else 0, 0 if i.get("representative") else 1))
        if cand:
            add(cand[0]["id"])

    # festivals of the character's own community must have clothes meant for them
    char = {**char, "wardrobe": chosen, "always_wear": always}
    for _ in range(4):
        _, skipped = plan_fn(char, region)
        added = False
        for oid in skipped:
            o = next(x for x in region["occasions"] if x["id"] == oid)
            want = o.get("occasion", "festive")
            if want == "mourning":
                continue
            cand = [i for i in region["wardrobe"] if i["slot"] in PRIMARY_SLOTS and ok(i) and want in i["occasion"]]
            cand.sort(key=lambda i: (0 if i["id"] in pool else 1, 0 if i.get("community") == comm_id else 1,
                                     0 if i.get("representative") else 1))
            if cand and cand[0]["id"] not in chosen:
                add(cand[0]["id"]); added = True
        if not added:
            break
    return chosen, always, warnings


def language_for(rng: random.Random, region: dict, ps: list[dict]) -> list[str]:
    lists = [p["language"] for p in ps if p.get("language")]
    if lists:
        return list(rng.choice(lists))
    langs = [l.split(" (")[0] for l in region.get("languages", [])]
    return langs[:2] or ["Hindi"]


def occupation_for(rng: random.Random, region: dict, group: str, setting: str, ps: list[dict]) -> str | None:
    if group in CHILD_GROUPS:
        return None
    occs = [o for o in region.get("occupations", []) if group in o["for"] and o["setting"] in ("both", setting)]
    if group.startswith("old") and rng.random() < 0.45:
        return None
    if not occs:
        return None
    seen = Counter(p.get("occupation") for p in ps if p.get("occupation"))
    weights = [1 + 2 * seen.get(o["id"], 0) for o in occs]
    return rng.choices(occs, weights=weights)[0]["id"]


def draft(rng: random.Random, region: dict, community_id: str, group: str, vocab: dict,
          chars: list[dict], plan_fn, taken_names: set[str], number: int) -> tuple[dict, list[str]]:
    comm = next(c for c in region["communities"] if c["id"] == community_id)
    if "names" not in comm:
        raise ValueError(f"{region['slug']}/{community_id} has no `names` list")
    ps = peers(chars, region, community_id)
    band, age = age_for(rng, vocab, group)
    settings_seen = [p["setting"] for p in ps] or ["urban", "rural"]
    setting = rng.choice(settings_seen)
    subs = comm.get("sub_regions") or [p.get("sub_region") for p in ps if p.get("sub_region")] or \
        [s["id"] for s in region.get("sub_regions", [])]
    char = {
        "schema_version": 2,
        "id": f"{region['code']}-{GROUP_CODES[group]}-{number:04d}",
        "name": "",
        "region": region["slug"],
        "community": community_id,
        "group": group,
        "age_band": band,
        "age": age,
        "setting": setting,
        "marital_status": marital_for(rng, group, band),
    }
    char["name"] = name_for(rng, comm, group, taken_names, char["marital_status"])
    if subs:
        char["sub_region"] = rng.choice(subs)
    occ = occupation_for(rng, region, group, setting, ps)
    if occ:
        char["occupation"] = occ
    char["look"] = look_for(rng, region, community_id, group, ps)
    wardrobe, always, warnings = wardrobe_for(rng, region, char, ps, region.get("best_representation", {}), plan_fn)
    items = items_by_id(region)
    if not any(items[w]["slot"] in PRIMARY_SLOTS for w in wardrobe) and char["marital_status"] == "widowed":
        # the community's dress is split by marital status with nothing recorded for widows (e.g.
        # Lotha skirts): do not guess, make the character married instead
        char["marital_status"] = "married"
        wardrobe, always, warnings = wardrobe_for(rng, region, char, ps, {}, plan_fn)
    if not any(items[w]["slot"] in PRIMARY_SLOTS for w in wardrobe):
        raise ValueError(f"{char['id']}: no garment fits a {group} of {community_id}")
    char["wardrobe"] = wardrobe
    if always:
        char["always_wear"] = always
    char["language"] = language_for(rng, region, ps)
    char.update(release="private" if is_child(char) else "public", status="draft", image_check="not_run",
                human_approved=False, origin="generated")
    if is_child(char):
        char["notes"] = "Private: children are never published."
    return {k: char[k] for k in ORDER if k in char}, warnings
