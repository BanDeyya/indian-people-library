"""Snapshot every compiled prompt per model profile, so changes to templates or data show up as a
readable diff in review.

    uv run scripts/snapshots.py            # check: fail if prompts changed
    uv run scripts/snapshots.py --update   # rewrite snapshots after an intended change
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys

import compile_prompts
from lib import (ROOT, SafetyChecker, load_characters, load_config, load_policy, load_profiles,
                 load_regions, load_vocab)

SNAP = ROOT / "tests" / "snapshots"


def render_all() -> dict[str, str]:
    # Snapshots use the shipped defaults only, never local.toml, so they are the same on every machine.
    import tomllib
    from lib import CONFIG
    cfg = tomllib.loads((CONFIG / "default.toml").read_text(encoding="utf-8"))
    vocab, regions, profiles = load_vocab(), load_regions(), load_profiles()
    checker = SafetyChecker(load_policy())
    out = {}
    for pid, prof in profiles.items():
        lines = []
        for _, c in load_characters():
            if c.get("origin", "handmade") != "handmade" or c.get("release") != "public":
                continue  # generated and private (children's) characters are covered by the validator and tests
            for j in compile_prompts.jobs_for(c, regions[c["region"]], vocab, checker, prof, cfg,
                                              stage="all", candidates=1):
                lines.append(json.dumps({"job_id": j["job_id"], "tokens": j["tokens"], "dropped": j["dropped"],
                                         "prompt": j["prompt"]}, ensure_ascii=False))
        out[pid] = "\n".join(lines) + "\n"
    # Festival scenes: one profile is enough to show which outfit each festival gets.
    fest_profile = "generic-long" if "generic-long" in profiles else next(iter(profiles))
    lines = []
    for _, c in load_characters():
        if c.get("origin", "handmade") != "handmade" or c.get("release") != "public":
            continue
        r = regions[c["region"]]
        for j in compile_prompts.jobs_for(c, r, vocab, checker, profiles[fest_profile], cfg,
                                          stage="festivals", candidates=1):
            lines.append(json.dumps({"job_id": j["job_id"], "tokens": j["tokens"], "dropped": j["dropped"],
                                     "prompt": j["prompt"]}, ensure_ascii=False))
        for oid in compile_prompts.festival_plan(c, r)[1]:
            lines.append(json.dumps({"job_id": f"{c['id']}-festival-{oid}", "skipped": "no outfit in the wardrobe is meant for this occasion"}))
    out[f"festivals-{fest_profile}"] = "\n".join(lines) + "\n"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true")
    args = ap.parse_args()
    current = render_all()
    SNAP.mkdir(parents=True, exist_ok=True)
    if args.update:
        for old in SNAP.glob("*.jsonl"):
            if old.stem not in current:
                old.unlink()
        for pid, text in current.items():
            (SNAP / f"{pid}.jsonl").write_text(text, encoding="utf-8")
        print(f"updated {len(current)} snapshot(s)")
        return 0
    changed = 0
    for pid, text in current.items():
        path = SNAP / f"{pid}.jsonl"
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        if old != text:
            changed += 1
            diff = difflib.unified_diff(old.splitlines(), text.splitlines(), f"snapshot/{pid}", f"now/{pid}", lineterm="", n=0)
            print("\n".join(list(diff)[:40]))
    if changed:
        print(f"\n{changed} profile snapshot(s) changed. If intended: uv run scripts/snapshots.py --update")
        return 1
    print("snapshots match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
