"""Lint every prompt for every model profile: token budget, dropped segments, repeated words,
outfit conflicts. Errors fail the run; warnings point at data worth tightening.

    uv run scripts/lint_prompts.py                 # all profiles
    uv run scripts/lint_prompts.py --profile sdxl  # one profile
    uv run scripts/lint_prompts.py --verbose       # also list every warning
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter

import compile_prompts
from lib import (SafetyChecker, UnsafePrompt, items_by_id, load_characters, load_config, load_policy,
                 load_profiles, load_regions, load_vocab, outfits_for, slot_conflicts)

STOP = {"a", "an", "the", "of", "and", "with", "in", "on", "at", "to", "from", "her", "his", "their",
        "photo", "wearing", "small", "white", "gold", "light", "natural", "plain"}


def repeated_words(text: str) -> list[str]:
    words = [w for w in re.findall(r"[a-z]+", text.lower()) if w not in STOP and len(w) > 2]
    return sorted(w for w, n in Counter(words).items() if n >= 3)


GENERATED_PROFILES = {"generic-long", "sdxl"}


def lint(profile_ids: list[str] | None = None) -> tuple[list[str], list[str], dict]:
    cfg, vocab, regions, profiles = load_config(), load_vocab(), load_regions(), load_profiles()
    checker = SafetyChecker(load_policy())
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict[str, dict] = {}
    for pid in profile_ids or list(profiles):
        profile = profiles[pid]
        st = stats.setdefault(pid, {"prompts": 0, "max": 0, "over": 0, "setting_dropped": 0, "total": 0})
        for _, c in load_characters():
            # Generated characters: the longest profile (every word) and one tight CLIP profile
            # (the token budget); the other profiles share their tokenizer and budget.
            if c.get("origin") == "generated" and pid not in GENERATED_PROFILES:
                continue
            region = regions[c["region"]]
            items = items_by_id(region)
            for outfit in outfits_for(c, region):
                for clash in slot_conflicts([items[i] for i in outfit]):
                    errors.append(f"{c['id']}: outfit conflict: {clash}")
            try:
                jobs = compile_prompts.jobs_for(c, region, vocab, checker, profile, cfg, stage="all", candidates=1)
            except UnsafePrompt as e:
                errors.append(f"[{pid}] {e}")
                continue
            for j in jobs:
                st["prompts"] += 1
                st["total"] += j["tokens"]
                st["max"] = max(st["max"], j["tokens"])
                if j["over_budget"]:
                    st["over"] += 1
                    errors.append(f"[{pid}] {j['job_id']}: {j['tokens']} tokens > budget {j['token_budget']} "
                                  "even after dropping optional parts; shorten look or item 'short' texts")
                if j["stage"].startswith("outfit") and "setting" in j["dropped"]:
                    st["setting_dropped"] += 1
                    warnings.append(f"[{pid}] {j['job_id']}: setting dropped to fit the budget")
                rep = repeated_words(j["prompt"])
                if rep:
                    warnings.append(f"[{pid}] {j['job_id']}: repeated words {rep}")
    return errors, warnings, stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", action="append", help="profile id (repeatable); default all")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    errors, warnings, stats = lint(args.profile)

    print(f"{'profile':<16}{'prompts':>8}{'max tok':>9}{'avg tok':>9}{'over':>6}{'setting lost':>14}")
    for pid, s in stats.items():
        avg = s["total"] / s["prompts"] if s["prompts"] else 0
        print(f"{pid:<16}{s['prompts']:>8}{s['max']:>9}{avg:>9.0f}{s['over']:>6}{s['setting_dropped']:>14}")
    if args.verbose:
        for w in warnings:
            print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)" + ("" if args.verbose else " (use --verbose to list warnings)"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
