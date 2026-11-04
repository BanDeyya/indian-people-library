"""Shared loading, config, safety, item rules and prompt rendering for the Indian People Library.

Every script imports from here, so safety, respect and prompt rules live in exactly one place.
"""
from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import clip_tokens

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SCHEMA = ROOT / "schema"
SAFETY = ROOT / "safety"
MODELS = ROOT / "models"
CONFIG = ROOT / "config"

GROUP_CODES = {
    "adult_male": "AM", "adult_female": "AF",
    "old_male": "OM", "old_female": "OF",
    "child_boy": "CB", "child_girl": "CG",
}
GROUP_LABELS = {
    "adult_male": "Adult male", "adult_female": "Adult female",
    "old_male": "Old male", "old_female": "Old female",
    "child_boy": "Child boy", "child_girl": "Child girl",
}
PERSON_WORD = {
    "adult_male": "man", "adult_female": "woman",
    "old_male": "elderly man", "old_female": "elderly woman",
    "child_boy": "boy", "child_girl": "girl",
}
CHILD_GROUPS = {"child_boy", "child_girl"}
STACKABLE_SLOTS = {"jewellery", "accessory"}
PRIMARY_SLOTS = {"full", "lower"}

PUBLIC_ROOT = "Indian People Library"
PRIVATE_ROOT = "Indian People Library - Private"


# ---------------------------------------------------------------- loading

def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_vocab() -> dict:
    return load_json(SCHEMA / "vocab.json")


def load_policy() -> dict:
    return load_json(SAFETY / "policy.json")


def load_regions() -> dict[str, dict]:
    return {p.stem: load_json(p) for p in sorted((DATA / "regions").glob("*.json"))}


def load_characters() -> list[tuple[Path, dict]]:
    return [(p, load_json(p)) for p in sorted((DATA / "characters").rglob("*.json"))]


def load_profiles() -> dict[str, dict]:
    return {p.stem: load_json(p) for p in sorted(MODELS.glob("*.json"))}


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_config() -> dict:
    """config/default.toml, overridden by the git-ignored local.toml if present."""
    cfg = tomllib.loads((CONFIG / "default.toml").read_text(encoding="utf-8"))
    local = ROOT / "local.toml"
    if local.exists():
        cfg = _merge(cfg, tomllib.loads(local.read_text(encoding="utf-8")))
    return cfg


def is_child(character: dict) -> bool:
    return character["group"] in CHILD_GROUPS


def items_by_id(region: dict) -> dict[str, dict]:
    return {i["id"]: i for i in region["wardrobe"] + region["accessories"]}


def community(region: dict, cid: str | None) -> dict:
    return next((c for c in region["communities"] if c["id"] == cid), {})


# ---------------------------------------------------------------- safety

def _term_pattern(term: str) -> re.Pattern:
    # Whole-word match so "bra" does not hit "bracelet" and "butt" does not hit "button".
    return re.compile(r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])")


@dataclass
class SafetyChecker:
    policy: dict
    _all: list = field(init=False)
    _child: list = field(init=False)

    def __post_init__(self) -> None:
        self._all = [(t, _term_pattern(t)) for t in self.policy["blocked_terms_all"]]
        self._child = [(t, _term_pattern(t)) for t in self.policy["blocked_terms_child"]]

    def blocked_terms(self, text: str, child: bool) -> list[str]:
        low = text.lower()
        hits = [t for t, p in self._all if p.search(low)]
        if child:
            hits += [t for t, p in self._child if p.search(low)]
        return hits

    def negative(self, child: bool) -> str:
        parts = [self.policy["negative_base"], self.policy["negative_safety_all"]]
        if child:
            parts.append(self.policy["negative_safety_child"])
        return ", ".join(parts)

    def positive(self, child: bool) -> str:
        return self.policy["positive_child"] if child else self.policy["positive_all"]


class UnsafePrompt(Exception):
    pass


# ---------------------------------------------------------------- item rules (respect rules in AGENTS.md section 2)

def item_problems(item: dict, character: dict, *, era: int | None = None) -> list[str]:
    """Why this character may not wear this item. Empty list = allowed."""
    problems = []
    if character["group"] not in item["for"]:
        problems.append(f"not for {character['group']}")
    if item.get("community") and item["community"] != character.get("community"):
        problems.append(f"belongs to the {item['community']} community")
    need = item.get("requires", {}).get("marital_status")
    if need and character.get("marital_status") != need:
        problems.append(f"needs marital_status={need}")
    if item.get("restricted"):
        problems.append("restricted item (honour/ritual), never auto-selected")
    if is_child(character) and "marital" in item.get("meaning", []):
        problems.append("marital item on a child")
    if era and item.get("era"):
        lo, hi = item["era"]["from"], item["era"].get("to")
        if era + 9 < lo or (hi is not None and era > hi):
            problems.append(f"outside era {era}s")
    return problems


def slot_conflicts(items: list[dict]) -> list[str]:
    """Pairs of items that cannot be worn together (same slot, or a full outfit plus a top/bottom)."""
    taken: dict[str, str] = {}
    out = []
    for it in items:
        slot = it["slot"]
        if slot in STACKABLE_SLOTS:
            continue
        clashes = [taken[slot]] if slot in taken else []
        if slot == "full":
            clashes += [taken[s] for s in ("upper", "lower") if s in taken]
        elif slot in ("upper", "lower") and "full" in taken:
            clashes.append(taken["full"])
        out += [f"{c} and {it['id']} clash ({slot} slot)" for c in clashes]
        taken[slot] = it["id"]
    return out


def outfits_for(character: dict, region: dict) -> list[list[str]]:
    """One outfit per primary garment in the character's wardrobe, completed with matching
    head, drape, outer, footwear and jewellery items that share an occasion."""
    items = items_by_id(region)
    always = list(character.get("always_wear", []))
    wardrobe = [items[w] for w in character["wardrobe"] if w in items and w not in always]
    uppers = [i for i in wardrobe if i["slot"] == "upper"]
    outfits = []
    for prim in [i for i in wardrobe if i["slot"] in PRIMARY_SLOTS]:
        occ = set(prim["occasion"])
        chosen = [prim]
        if prim["slot"] == "lower" and uppers:
            chosen.append(uppers[0])
        for extra in wardrobe:
            if extra in chosen or extra["slot"] in PRIMARY_SLOTS or extra["slot"] == "upper":
                continue
            if _seasonal(extra):
                continue  # seasonal layers get their own outfit below
            if occ & set(extra["occasion"]) and not slot_conflicts(chosen + [extra]):
                chosen.append(extra)
        outfits.append([i["id"] for i in chosen] + always)
    # One extra outfit per seasonal layer (e.g. a winter shawl) over the first everyday garment it fits.
    for layer in [i for i in wardrobe if _seasonal(i)]:
        for base in outfits:
            prim = items[base[0]]
            if set(prim["occasion"]) & set(layer["occasion"]) and not slot_conflicts([items[i] for i in base] + [layer]):
                outfits.append([base[0], layer["id"]] + [i for i in base[1:] if i not in always] + always)
                break
    return outfits


def _seasonal(item: dict) -> bool:
    seasons = item.get("season") or ["any"]
    return "any" not in seasons


def tiebreak_order(region: dict, cfg: dict) -> list[str]:
    """Religion keys of the region ordered for tie-breaks (configurable, see config/default.toml)."""
    shares = region["religion_mix"]["shares"]
    order = sorted((k for k in shares if k != "other"), key=lambda k: -shares[k])
    pref = cfg.get("representation", {}).get("tiebreak", "state_majority")
    if pref != "state_majority" and pref in order:
        order.remove(pref)
        order.insert(0, pref)
    return order


def representative_outfit(character: dict, region: dict, cfg: dict, occasion: str = "daily") -> list[str]:
    """Best-representation outfit for the character's group, filtered to what this character may
    wear; among valid options the tie-break order decides. Falls back to the first wardrobe outfit."""
    items = items_by_id(region)
    rep = region.get("best_representation", {}).get(character["group"], {})
    options = list(rep.get(occasion) or rep.get("daily") or [])
    # community dress listed only under festive still counts for the character's portrait
    options += [o for o in rep.get("festive", []) if o not in options
                and any(items.get(i, {}).get("community") == character.get("community") for i in o)
                and any(occasion in items.get(i, {}).get("occasion", []) for i in o)]
    if not options:
        options = rep.get("festive") or []
    order = tiebreak_order(region, cfg)

    def rank(option: list[str]) -> tuple[int, int]:
        # 1) the character's own community dress first (a Santal woman's phutta sari before a shared saree),
        # 2) then the configured tie-break order between traditions.
        own = 0 if any(items[i].get("community") == character.get("community") for i in option) else 1
        religions = [community(region, items[i].get("community")).get("religion") for i in option]
        ranks = [order.index(r) for r in religions if r in order]
        return own, (min(ranks) if ranks else 0)

    always = list(character.get("always_wear", []))
    own = set(character["wardrobe"]) | set(always)
    valid = [o for o in options
             if all(i in own and i in items and not item_problems(items[i], character) for i in o)]
    if valid:
        chosen = sorted(valid, key=rank)[0] + [a for a in always if a not in sorted(valid, key=rank)[0]]
    else:
        fallback = outfits_for(character, region)
        chosen = fallback[0] if fallback else list(always)
    # The character's own marital/religious items (thali, minnu, metti...) belong in every portrait.
    for wid in character["wardrobe"]:
        it = items.get(wid)
        if (it and wid not in chosen and set(it.get("meaning", [])) & {"marital", "religious"}
                and it["slot"] in ("jewellery", "accessory") and not item_problems(it, character)):
            chosen.append(wid)
    return chosen


# ---------------------------------------------------------------- prompts

def folder_for(character: dict, region: dict) -> str:
    if character.get("output_folder"):
        return character["output_folder"]
    root = PRIVATE_ROOT if (is_child(character) or character["release"] == "private") else PUBLIC_ROOT
    return f"{root}/{region['name']}/{GROUP_LABELS[character['group']]}/{character['id']} {character['name']}"


def _subject(character: dict, region: dict) -> str:
    age = character.get("age")
    who = PERSON_WORD[character["group"]]
    if age:
        who = who.removeprefix("elderly ")
    comm = community(region, character.get("community"))
    if comm.get("prompt"):
        who = f"{comm['prompt']} {who}"
    head = f"{age}-year-old {who}" if age else who
    article = "an" if head[0] in "aeiou8" or head.startswith(("11-", "18-")) else "a"
    sub = next((x for x in region.get("sub_regions", []) if x["id"] == character.get("sub_region")), {})
    return f"{article} {head} from {sub.get('place') or region['name']}"


def token_count(text: str, profile: dict) -> int:
    return clip_tokens.count(text) if profile["tokenizer"] == "clip" else clip_tokens.approx(text)


def render(character: dict, region: dict, vocab: dict, checker: SafetyChecker, profile: dict, *,
           outfit_ids: list[str], view: str, setting: str, setting_short: str | None, framing: str) -> dict:
    """Build one prompt for one model profile.

    Segments are written in priority order. For short (77-token) profiles, the lowest-priority
    droppable segments are removed until the prompt fits; the subject, skin tone, signature mark,
    face, hair and outfit are never dropped. Raises UnsafePrompt on any blocked term.
    """
    items = items_by_id(region)
    look = character["look"]
    child = is_child(character)
    long = profile["variant"] == "long"
    skin = vocab["skin_tone_scale"][str(look["skin_tone_mst"])]

    def it(i: str) -> str:
        return items[i]["prompt"] if long else items[i].get("short") or items[i]["prompt"]

    always = set(character.get("always_wear", []))
    # Marital and religious items are identity, not decoration: they stay with the outfit and are never dropped.
    keep = {i for i in outfit_ids if set(items[i].get("meaning", [])) & {"marital", "religious"}}
    garments = [i for i in outfit_ids if items[i]["slot"] not in ("jewellery", "accessory") or i in always | keep]
    jewellery = [i for i in outfit_ids if i not in garments]

    # (priority: lower = more important, name, text, droppable). Order in the prompt = this order.
    segs = [
        (0, "subject", f"{framing} photo of {_subject(character, region)}", False),
        (1, "skin", f"{skin} skin" + (" with the same even tone on face, neck, arms and hands" if long else ""), False),
        (2, "mark", look["signature_mark"], False),
        (3, "face", look["face"], False),
        (4, "hair", look["hair"], False),
        (5, "facial_hair", look.get("facial_hair", ""), True),
        (6, "outfit", "wearing " + ", ".join(it(i) for i in garments), False),
        (9, "jewellery", ", ".join(it(i) for i in jewellery), True),
        (7, "setting", (setting if long else (setting_short or setting)), True),
        (8, "view", vocab["views"][view], True),
        (10, "eyes", look.get("eyes", ""), True),
        (11, "build", f"{look['build']} build", True),
        (12, "style", profile.get("style", ""), True),
        (13, "safety_positive", checker.positive(child) if long else "", True),
    ]
    segs = [s for s in segs if s[2]]
    budget = profile["token_budget"] * (profile.get("max_chunks", 1) if profile["long_prompt"] == "chunk" else 1)

    def join(parts: list[tuple]) -> str:
        return ", ".join(p[2] for p in parts)

    dropped = []
    text = join(segs)
    while token_count(text, profile) > budget:
        droppable = [s for s in segs if s[3]]
        if not droppable:
            break
        worst = max(droppable, key=lambda s: s[0])
        segs.remove(worst)
        dropped.append(worst[1])
        text = join(segs)

    hits = checker.blocked_terms(text, child)
    if hits:
        raise UnsafePrompt(f"{character['id']}: blocked terms {sorted(set(hits))} in prompt: {text}")
    tokens = token_count(text, profile)
    return {
        "prompt": text,
        "negative_prompt": checker.negative(child) if profile["negatives"] else "",
        "tokens": tokens,
        "token_budget": budget,
        "over_budget": tokens > budget,
        "dropped": dropped,
    }
