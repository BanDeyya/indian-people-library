"""Draft new characters from the region data (they start as `status: draft`, `origin: generated`).

    uv run scripts/new_character.py --region bihar --community maithil --group adult_female
    uv run scripts/new_character.py --fill 20                  # every region, every group, up to 20 each
    uv run scripts/new_character.py --fill 20 --region goa --dry-run

Rules the generator keeps are listed in scripts/generator.py. In fill mode the new characters of a
group are shared across the region's communities by their hand-made characters, re-weighted so the
religions follow the census shares in the region file. A community is used only
when it has a `names` list and at least one hand-made character to learn from. The same command
always gives the same result (fixed seed per region, group and number).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import zlib
from collections import Counter

from compile_prompts import festival_plan
from generator import draft, peers
from lib import DATA, GROUP_CODES, PRIMARY_SLOTS, load_characters, load_regions, load_vocab


def _seed(*parts) -> int:
    return zlib.crc32("|".join(map(str, parts)).encode())


def next_number(chars: list[dict], region: dict, group: str) -> int:
    prefix = f"{region['code']}-{GROUP_CODES[group]}-"
    nums = [int(c["id"][len(prefix):]) for c in chars if c["id"].startswith(prefix)]
    return max(nums, default=0) + 1


def share(counts: dict[str, float], n: int) -> dict[str, int]:
    """Split n new characters across communities in proportion to counts (largest remainder)."""
    total = sum(counts.values())
    raw = {k: n * v / total for k, v in counts.items()}  # counts may be float weights
    out = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - out[k], reverse=True)[: n - sum(out.values())]:
        out[k] += 1
    return out


def can_dress(region: dict, community: str, group: str) -> bool:
    """Is there a main garment recorded for this group that a member of this community may wear?"""
    return any(group in i["for"] and i["slot"] in PRIMARY_SLOTS and not i.get("restricted")
               and i.get("community") in (None, community) for i in region["wardrobe"])


def usable(region: dict, chars: list[dict], group: str) -> dict[str, float]:
    """Communities that can take new characters, with their weights.

    Each community starts from its number of hand-made characters (all groups). Communities with one
    recorded religion are then re-weighted so that, together, the religions match the census shares
    in `religion_mix` (only religions that have a usable community count). Communities with no single
    religion (many tribal communities) keep their hand-made weight.
    """
    hand = [c for c in chars if c["region"] == region["slug"] and c.get("origin", "handmade") == "handmade"]
    counts = Counter(c["community"] for c in hand)
    comms = {c["id"]: c for c in region["communities"]
             if "names" in c and counts.get(c["id"]) and peers(chars, region, c["id"])
             and can_dress(region, c["id"], group)}
    weights = {cid: float(counts[cid]) for cid in comms}
    by_rel = Counter()
    for cid, c in comms.items():
        if c.get("religion"):
            by_rel[c["religion"]] += counts[cid]
    shares = region.get("religion_mix", {}).get("shares", {})
    known = sum(by_rel.values())
    target_total = sum(shares.get(r, 0) for r in by_rel)
    if known and target_total:
        for cid, c in comms.items():
            rel = c.get("religion")
            if rel and shares.get(rel):
                weights[cid] = counts[cid] / by_rel[rel] * known * shares[rel] / target_total
    return {k: v for k, v in weights.items() if v > 0}


def write(char: dict) -> str:
    folder = DATA / "characters" / char["region"]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{char['id']}.json"
    path.write_text(json.dumps(char, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path.relative_to(DATA.parent))


def make(region: dict, community: str, group: str, vocab: dict, chars: list[dict], *, dry: bool) -> tuple[dict, list[str]]:
    number = next_number(chars, region, group)
    rng = random.Random(_seed(region["slug"], group, number))
    taken = Counter(c["name"] for c in chars if c["region"] == region["slug"])
    char, warnings = draft(rng, region, community, group, vocab, chars, festival_plan, taken, number)
    chars.append(char)
    if not dry:
        write(char)
    return char, warnings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--region")
    ap.add_argument("--community")
    ap.add_argument("--group", choices=sorted(GROUP_CODES))
    ap.add_argument("--fill", type=int, help="bring every group of every (or the given) region up to N")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true", help="also list groups dressed only in shared clothes")
    a = ap.parse_args()

    regions, vocab = load_regions(), load_vocab()
    chars = [c for _, c in load_characters()]
    warnings: set[str] = set()

    if a.fill is None:
        if not (a.region and a.community and a.group):
            ap.error("give --region, --community and --group, or --fill N")
        char, w = make(regions[a.region], a.community, a.group, vocab, chars, dry=a.dry_run)
        warnings |= set(w)
        print(json.dumps(char, ensure_ascii=False, indent=2))
    else:
        made = Counter()
        for slug in ([a.region] if a.region else sorted(regions)):
            region = regions[slug]
            for group in GROUP_CODES:
                if a.group and group != a.group:
                    continue
                have = sum(1 for c in chars if c["region"] == slug and c["group"] == group)
                if have >= a.fill:
                    continue
                pool = usable(region, chars, group)
                if a.community:
                    pool = {k: v for k, v in pool.items() if k == a.community}
                if not pool:
                    warnings.add(f"{slug}/{group}: no community with names and hand-made examples")
                    continue
                for comm, n in share(pool, a.fill - have).items():
                    for _ in range(n):
                        _, w = make(region, comm, group, vocab, chars, dry=a.dry_run)
                        warnings |= set(w)
                        made[slug] += 1
        print(f"{'would draft' if a.dry_run else 'drafted'} {sum(made.values())} characters in {len(made)} regions")
    shared = sorted(w for w in warnings if "no dress of its own" in w)
    for w in sorted(set(warnings) - set(shared)) + (shared if a.verbose else []):
        print("warning:", w, file=sys.stderr)
    if shared and not a.verbose:
        print(f"note: {len(shared)} community groups wear only shared regional clothes (--verbose lists them)",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
