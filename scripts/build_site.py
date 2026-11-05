"""Build the data files for the static catalogue site (site/).

    uv run scripts/build_site.py                 # writes site/data/
    uv run scripts/build_site.py --out /tmp/site # elsewhere (the page files are copied too)

Only public characters are included. Children (release: private) never appear on the site, not even
as counts per character. Each character gets its look, clothes (with the item names from the region
file), languages, festivals of their own community, and the first-portrait prompt for the
`generic-long` profile, so anyone can paste it into their own model.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

import compile_prompts
from lib import (DATA, GROUP_LABELS, ROOT, SafetyChecker, UnsafePrompt, community, is_child, items_by_id,
                 load_characters, load_config, load_policy, load_profiles, load_regions, load_vocab)

SITE = ROOT / "site"
PROFILE = "generic-long"
SKIN_WORDS = {1: "very light", 2: "very light", 3: "light", 4: "light to wheatish", 5: "wheatish", 6: "medium brown",
              7: "medium to dark brown", 8: "dark brown", 9: "deep brown", 10: "very deep brown"}


def char_record(c: dict, region: dict, vocab: dict, checker: SafetyChecker, profile: dict, cfg: dict,
                groups_by_member: dict[str, list[str]]) -> dict:
    comm = community(region, c["community"])
    items = items_by_id(region)
    occ_names = {o["id"]: o["name"] for o in region.get("occupations", [])}
    sub_names = {s["id"]: s["name"] for s in region.get("sub_regions", [])}
    plan, _ = compile_prompts.festival_plan(c, region)
    try:
        job = compile_prompts.jobs_for(c, region, vocab, checker, profile, cfg, stage="candidates", candidates=1)[0]
        prompt, negative = job["prompt"], job["negative_prompt"]
    except UnsafePrompt:
        prompt = negative = None
    return {
        "id": c["id"], "name": c["name"], "group": c["group"], "age": c["age"], "age_band": c["age_band"],
        "setting": c["setting"], "marital_status": c["marital_status"],
        "sub_region": sub_names.get(c.get("sub_region"), None),
        "occupation": occ_names.get(c.get("occupation")),
        "community": c["community"], "community_name": comm.get("name"), "culture": comm.get("culture"),
        "religion": comm.get("religion"), "groups": groups_by_member.get(f"{region['slug']}:{c['community']}", []),
        "look": {**c["look"], "skin_words": SKIN_WORDS.get(c["look"]["skin_tone_mst"], "")},
        "wardrobe": [{"id": i, "name": items[i]["name"], "short": items[i].get("short", items[i]["name"]),
                      "slot": items[i]["slot"], "occasion": items[i]["occasion"]} for i in c["wardrobe"]],
        "language": c.get("language", []),
        "festivals": [{"id": o["id"], "name": o["name"], "when": o.get("when"),
                       "outfit": [items[i]["name"] for i in outfit]} for o, outfit in plan],
        "origin": c.get("origin", "handmade"), "status": c["status"],
        "prompt": prompt, "negative_prompt": negative,
    }


def build(out: Path) -> dict:
    regions, vocab, cfg, profiles = load_regions(), load_vocab(), load_config(), load_profiles()
    checker = SafetyChecker(load_policy())
    profile = profiles[PROFILE]
    index_file = DATA / "community-index.json"
    cindex = json.loads(index_file.read_text(encoding="utf-8")) if index_file.exists() else {"groups": []}
    groups_by_member: dict[str, list[str]] = {}
    for g in cindex["groups"]:
        for m in g["members"]:
            groups_by_member.setdefault(m, []).append(g["id"])

    by_region: dict[str, list[dict]] = {}
    for _, c in load_characters():
        if is_child(c) or c.get("release") != "public":
            continue  # children and anything private never reach the site
        by_region.setdefault(c["region"], []).append(c)

    out = out.resolve()
    if out == ROOT or out in ROOT.parents or (ROOT in out.parents and out != SITE):
        raise SystemExit(f"build_site: refusing to write into {out}; use site/ or a folder outside the repository")
    data = out / "data"
    marker = data / ".built-by-build_site"
    if data.exists():
        if not marker.exists():
            raise SystemExit(f"build_site: {data} exists and was not made by this script; remove it yourself first")
        shutil.rmtree(data)
    (data / "regions").mkdir(parents=True)
    marker.write_text("built by scripts/build_site.py; safe to delete\n", encoding="utf-8")
    summary = []
    rows = []
    for slug, region in sorted(regions.items(), key=lambda kv: kv[1]["name"]):
        recs = [char_record(c, region, vocab, checker, profile, cfg, groups_by_member)
                for c in sorted(by_region.get(slug, []), key=lambda c: c["id"])]
        detail = {
            "slug": slug, "name": region["name"], "type": region["type"], "zone": region["zone"],
            "capital": region.get("capital"), "status": region["status"],
            "languages": region.get("languages", []),
            "religion_mix": region.get("religion_mix", {}),
            "communities": [{"id": c["id"], "name": c["name"], "culture": c.get("culture"),
                             "religion": c.get("religion"), "notes": c.get("notes")} for c in region["communities"]],
            "sources": [{"title": s["title"], "url": s["url"]} for s in region.get("sources", []) if s.get("url")],
            "characters": recs,
        }
        (data / "regions" / f"{slug}.json").write_text(json.dumps(detail, ensure_ascii=False, separators=(",", ":")),
                                                       encoding="utf-8")
        summary.append({"slug": slug, "name": region["name"], "type": region["type"], "zone": region["zone"],
                        "characters": len(recs)})
        for r in recs:
            rows.append([r["id"], r["name"], slug, r["group"], r["age"], r["setting"], r["community"],
                         r["community_name"], r["culture"], r["religion"], r["groups"], r["origin"],
                         [f["id"] for f in r["festivals"]], r["look"]["skin_tone_mst"]])
    index = {
        "fields": ["id", "name", "region", "group", "age", "setting", "community", "community_name", "culture",
                   "religion", "groups", "origin", "festivals", "skin"],
        "regions": summary,
        "groups": GROUP_LABELS,
        "cross_state": [{"id": g["id"], "name": g["name"]} for g in cindex["groups"]],
        "festivals": {slug: {o["id"]: o["name"] for o in r["occasions"]} for slug, r in regions.items()},
        "rows": rows,
    }
    (data / "index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if out != SITE:
        for f in ("index.html", "app.js", "style.css", "social-preview.png", "robots.txt", "sitemap.xml"):
            shutil.copy(SITE / f, out / f)
    return {"characters": len(rows), "regions": len(summary),
            "religions": dict(Counter(r[9] or "unspecified" for r in rows))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=SITE)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    stats = build(a.out)
    print(f"site data: {stats['characters']} public characters in {stats['regions']} regions -> {a.out / 'data'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
