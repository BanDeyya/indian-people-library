"""Per-state diversity report: are characters spread across the region's real range?

Warns (never fails) when a state is skewed: a large community with no characters, all characters
on one end of the skin-tone range, only rural or only urban, or groups missing.

    uv run scripts/diversity_report.py
"""
from __future__ import annotations

import sys
from collections import Counter

from lib import GROUP_LABELS, community, load_characters, load_regions

BIG_COMMUNITY = 10.0  # % of a state's population


def report() -> tuple[list[str], list[str]]:
    regions = load_regions()
    lines, warnings = [], []
    chars: dict[str, list[dict]] = {}
    for _, c in load_characters():
        chars.setdefault(c["region"], []).append(c)

    for slug, r in regions.items():
        cs = chars.get(slug, [])
        lines.append(f"\n## {r['name']} ({len(cs)} characters)")
        if not cs:
            warnings.append(f"{r['name']}: no characters yet")
            continue
        lo, hi = r["look_range"]["skin_tone_mst"]
        tones = sorted(c["look"]["skin_tone_mst"] for c in cs)
        lines.append(f"skin tone MST: {tones} (range {lo}-{hi})")
        if len(cs) >= 4 and (max(tones) - min(tones)) < (hi - lo) / 2:
            warnings.append(f"{r['name']}: skin tones cover less than half of the range {lo}-{hi}")

        settings = Counter(c["setting"] for c in cs)
        lines.append(f"setting: {dict(settings)}")
        if len(cs) >= 4 and len(settings) < 2:
            warnings.append(f"{r['name']}: all characters are {next(iter(settings))}")

        groups = Counter(c["group"] for c in cs)
        lines.append("groups: " + ", ".join(f"{GROUP_LABELS[g]} {groups.get(g, 0)}" for g in GROUP_LABELS))

        by_rel = Counter(community(r, c["community"]).get("religion") or "unspecified" for c in cs)
        lines.append(f"religion of characters: {dict(by_rel)}")
        shares = r["religion_mix"]["shares"]
        lines.append("population share: " + ", ".join(f"{k} {v:.1f}%" for k, v in sorted(shares.items(), key=lambda x: -x[1])))
        # Compare only characters whose community has one recorded religion (many tribal communities
        # follow several or their own traditions, so they are left out of this comparison).
        known = sum(n for rel, n in by_rel.items() if rel != "unspecified")
        if known >= 6:
            for rel, share in shares.items():
                have = 100 * by_rel.get(rel, 0) / known
                if rel != "other" and abs(have - share) > 20:
                    warnings.append(f"{r['name']}: {rel} is {have:.0f}% of characters but {share:.1f}% of the population")
        for rel, share in shares.items():
            if rel != "other" and share >= BIG_COMMUNITY and by_rel.get(rel, 0) == 0:
                has_comm = any(x.get("religion") == rel for x in r["communities"])
                warnings.append(f"{r['name']}: {rel} ({share:.1f}% of the population) has no characters"
                                + ("" if has_comm else " and no community entry"))
    return lines, warnings


def main() -> int:
    lines, warnings = report()
    print("# Diversity report", *lines, sep="\n")
    print()
    for w in warnings:
        print(f"WARN  {w}")
    print(f"\n{len(warnings)} warning(s) (warnings only, nothing fails)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
