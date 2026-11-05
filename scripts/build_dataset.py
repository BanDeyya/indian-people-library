"""Build a dataset package of the library for Hugging Face Datasets and Kaggle.

    uv run scripts/build_dataset.py                    # writes dist/dataset/
    uv run scripts/build_dataset.py --out /tmp/dataset

Writes characters.jsonl (one public character per line, with the clothes' names, festivals and a
ready portrait prompt), regions.jsonl (one state or UT per line), README.md (the dataset card,
with the metadata block Hugging Face reads) and dataset-metadata.json (for Kaggle). Children and
any other private characters are never included.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

import build_site
from lib import (ROOT, SafetyChecker, is_child, load_characters, load_config, load_policy, load_profiles,
                 load_regions, load_vocab)

REPO = "https://github.com/BanDeyya/indian-people-library"
SITE = "https://bandeyya.github.io/indian-people-library/"


def region_record(r: dict) -> dict:
    items = r["wardrobe"] + r["accessories"]
    return {
        "region": r["slug"], "name": r["name"], "type": r["type"], "zone": r["zone"], "capital": r.get("capital"),
        "languages": r.get("languages", []),
        "religion_shares_census_2011": r.get("religion_mix", {}).get("shares", {}),
        "communities": [{"id": c["id"], "name": c["name"], "culture": c.get("culture"),
                         "religion": c.get("religion"), "notes": c.get("notes")} for c in r["communities"]],
        "clothes": [{"id": i["id"], "name": i["name"], "for": i["for"], "slot": i["slot"],
                     "occasion": i["occasion"], "community": i.get("community"), "description": i.get("prompt"),
                     "meaning": i.get("meaning", []), "restricted": bool(i.get("restricted"))} for i in items],
        "festivals_and_rites": [{"id": o["id"], "name": o["name"], "when": o.get("when"),
                                 "communities": o.get("communities", [])} for o in r["occasions"]],
        "avoid": r.get("avoid", []),
        "sources": [{"title": s["title"], "url": s["url"]} for s in r.get("sources", []) if s.get("url")],
    }


def card(n_chars: int, n_regions: int, by_group: Counter, by_origin: Counter) -> str:
    return f"""---
license: cc-by-4.0
pretty_name: Indian People Library
language:
- en
task_categories:
- text-to-image
tags:
- india
- synthetic
- characters
- cultural-heritage
- prompt-engineering
- stable-diffusion
size_categories:
- 1K<n<10K
configs:
- config_name: characters
  data_files: characters.jsonl
  default: true
- config_name: regions
  data_files: regions.jsonl
---

# Indian People Library

Fictional, consistent people from every Indian state and union territory, with researched regional
dress, festivals and ready-to-use image prompts. This is a data and prompt library: it contains no
images. Bring your own text-to-image model.

- Catalogue: {SITE}
- Source, prompt compiler for several model families, and checks: {REPO}

## Contents

**characters** ({n_chars:,} rows): one fictional adult or older person per row, 20 per group in each
of the {n_regions} states and union territories. Fields:

- `id`, `name`, `region`, `region_name`, `group` (adult_male, adult_female, old_male, old_female), `age`,
  `setting` (rural or urban), `marital_status`, `occupation`, `sub_region`
- `community`, `community_name`, `culture`, `religion` (null for communities that follow several or
  their own traditions), `cross_state_groups` (peoples who live in several states, e.g. santal, bengali)
- `look`: Monk Skin Tone scale value (1-10) with words, face, eyes, hair, facial hair, build and one
  signature mark that keeps the person recognisable
- `wardrobe`: the character's clothes and accessories, each with its name, slot and occasions
- `languages`, `festivals` (the festivals and rites of the character's own community, with the outfit
  worn for each)
- `prompt` and `negative_prompt`: a head-and-shoulders portrait prompt for long-text models
- `origin`: `handmade` (reviewed one by one, {by_origin.get('handmade', 0):,} rows) or `generated`
  (drafts built from the hand-made characters of the same community, {by_origin.get('generated', 0):,} rows)

Rows per group: {", ".join(f"{k} {v:,}" for k, v in sorted(by_group.items()))}.

**regions** ({n_regions} rows): one state or union territory per row, with its communities and
Census 2011 religion shares, clothes and accessories (with their meaning: marital, religious, honour),
festivals and rites, things never to show, and the sources used.

## How it was made

Region files were researched from India's own sources (state tourism and culture departments, the
census, museums and community sources) and cross-checked against a second source. Every region and
religion is treated with the same care: marital, religious and honour items appear only on the people
they belong to, and no character carries a caste surname. Generated characters were drafted by a
script from the reviewed characters of the same community, with community shares following the
census.

## Use rules

Licensed under CC BY 4.0: credit "Indian People Library" with a link to {REPO}. Please also follow
the project's use rules: no sexual content of any character; no impersonation of real people or
deepfakes; no stereotyping or hate against any religion, community, caste, tribe or region; label
every image made with the data as AI-generated. Every person in this dataset is fictional.

## Limitations

The research is a best effort and may contain mistakes. Generated characters are drafts. Native
reviews are welcome: open an issue at {REPO}/issues.
"""


def build(out: Path) -> dict:
    regions, vocab, cfg, profiles = load_regions(), load_vocab(), load_config(), load_profiles()
    checker = SafetyChecker(load_policy())
    profile = profiles[build_site.PROFILE]
    index = json.loads((ROOT / "data" / "community-index.json").read_text(encoding="utf-8"))
    groups_by_member: dict[str, list[str]] = {}
    for g in index["groups"]:
        for m in g["members"]:
            groups_by_member.setdefault(m, []).append(g["id"])
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    by_group, by_origin, n = Counter(), Counter(), 0
    with (out / "characters.jsonl").open("w", encoding="utf-8") as f:
        for _, c in sorted(load_characters(), key=lambda pc: pc[1]["id"]):
            if is_child(c) or c.get("release") != "public":
                continue
            r = regions[c["region"]]
            rec = build_site.char_record(c, r, vocab, checker, profile, cfg, groups_by_member)
            row = {"id": rec["id"], "name": rec["name"], "region": r["slug"], "region_name": r["name"],
                   "group": rec["group"], "age": rec["age"], "setting": rec["setting"],
                   "marital_status": rec["marital_status"], "occupation": rec["occupation"],
                   "sub_region": rec["sub_region"], "community": rec["community"],
                   "community_name": rec["community_name"], "culture": rec["culture"], "religion": rec["religion"],
                   "cross_state_groups": rec["groups"], "look": rec["look"], "wardrobe": rec["wardrobe"],
                   "languages": rec["language"], "festivals": rec["festivals"], "prompt": rec["prompt"],
                   "negative_prompt": rec["negative_prompt"], "origin": rec["origin"]}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            by_group[row["group"]] += 1
            by_origin[row["origin"]] += 1
            n += 1
    with (out / "regions.jsonl").open("w", encoding="utf-8") as f:
        for slug in sorted(regions):
            f.write(json.dumps(region_record(regions[slug]), ensure_ascii=False) + "\n")
    (out / "README.md").write_text(card(n, len(regions), by_group, by_origin), encoding="utf-8")
    (out / "dataset-metadata.json").write_text(json.dumps({
        "title": "Indian People Library",
        "id": "bandeyya/indian-people-library",
        "subtitle": "Fictional people from every Indian state with researched dress and prompts",
        "description": "See README.md. Source: " + REPO,
        "licenses": [{"name": "CC-BY-4.0"}],
        "keywords": ["india", "culture", "text-to-image"],
    }, indent=2) + "\n", encoding="utf-8")
    return {"characters": n, "regions": len(regions)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ROOT / "dist" / "dataset")
    a = ap.parse_args()
    stats = build(a.out.resolve())
    print(f"dataset: {stats['characters']} characters, {stats['regions']} regions -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
