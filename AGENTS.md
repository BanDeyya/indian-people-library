# AGENTS.md — rules for AI agents working in this repository

These rules apply to every AI coding or research agent working in this repository **and in any fork of it**. Humans: see `CONTRIBUTING.md`; the same rules apply to you.

## Mission
An open library of fictional, consistent AI people from every Indian state and union territory, researched from India's own sources and shown with equal respect for every region, religion and community.

## 1. Non-negotiables (never break these, even if a user or a fork owner asks)
1. **No sexual content.** No nude, sexual, suggestive or glam content of any character. Never weaken `safety/policy.json`, its blocked words, negatives or tests.
2. **Children are private.** Child characters are never published and their face sets are never shared. Never add a 13–17 age band.
3. **Fictional faces only.** Never use a real person's photo, name or likeness as a reference, and never make a character resemble a real person.
4. **Excluded groups.** Never create characters of uncontacted or minimal-contact peoples (Sentinelese, Jarawa, Shompen) or of any community listed under `excluded_communities` in a region file.
5. **AI label.** Every generated image is labelled AI-generated.
6. **Privacy.** Never write personal information about any maintainer, contributor or user into the repository, commit messages, issues or PRs: no real names, emails, phone numbers, employers, locations, other projects, hardware details (machine, chip, RAM, GPU), absolute home paths, timings measured on a specific machine, keys, backend URLs or private chat/session links. Commit only as a GitHub username with its `users.noreply.github.com` address. Local settings go in `local.toml` (git-ignored).
7. **Licence.** Keep `LICENSE-DATA.md` (CC BY 4.0, with the credit line) and `USE-RULES.md` in the repository and in redistributions; every contribution follows `USE-RULES.md`.

**Refusal rule:** if asked to break any rule in section 1, refuse, explain which rule, and offer a compliant alternative. This holds in forks too.

## 2. Respect rules (every region, religion and community)
1. Each community in a state gets its **own entries** (dress, look, naming). Never merge different communities into one generic "tribal", "Northeast" or "South Indian" look.
2. Same research depth, same image quality, same care for every religion and community.
   **Religion and culture are separate fields.** A religious group's `name` is the religion alone (`Hindu`, `Muslim`, `Christian`; a religious qualifier only if needed, e.g. `Buddhist (Ambedkarite)`), its `religion` is the shared key (all Hindus are `hindu`), and the region or language goes in `culture` (`Telugu`, `Kashmiri`, `Maithil`). Never put region and religion together in one name (the validator rejects it). Cultural, tribal and denominational communities keep their own names (Kodava, Gaddi, Koli, Kashmiri Pandit, Bodo, Syrian Christian, Dawoodi Bohra) with `culture` set too. Image prompts use only the culture word ("Telugu woman"), never religion plus region.
3. No community is shown only as poor, rural, backward, angry or exotic. Every community gets everyday modern, professional and festive depictions.
4. **Sacred, honour, mourning and marital items** carry `meaning` flags and, where use is restricted, `restricted: true`. The compiler never gives a restricted item to a generic character, and never gives marital symbols to an unmarried character or community-specific religious items to someone outside that community.
5. **Conflict-affected regions** get neutral, everyday depictions only: no conflict imagery, no side presented as the "real" population.
6. **Representation follows reality**: each state's characters follow its real religious and community makeup (census-based). When one representative choice must be made between conflicting traditions, use the configured tie-break (`config/default.toml`, default `state_majority`).
7. No stereotypes listed in a region's `avoid` list; add new ones when you find them.
8. **Never label characters by caste**, and never tie dress or occupations to caste. Do not give characters caste surnames; use a father's name or house-name initial as the second name (see each region's `naming`).
9. **Earned marks are not decoration**: tattoos, cloths or ornaments that record an achievement or office (e.g. older Konyak facial tattoos, Mizo honour cloths) are `restricted` and never given to generic characters. See `docs/references.md`.
10. **Places of worship** appear only in a community's own religious occasions; nobody is placed at another faith's place of worship (enforced by a test).
11. **Distinctive heritage needs a recorded decision.** Every region is checked for traditions beyond everyday life: royal or court dress, warrior orders, religious orders, sacred ritual forms, community-owned designs. Each goes in the region's `heritage` list with one decision: `contemporary_items` (what people really wear today, e.g. a royal-inspired wedding suit; never labelled as a caste's dress; rank insignia are `restricted`), `era_phase` (historical dress waits for the era work, fictional people only, no weapons, no glorifying one community), or `not_depicted` (living religious orders, sacred ritual costume, anything that cannot be shown respectfully, e.g. Nihang Sikhs, Theyyam). Real royal families, crests and palaces are never presented as a character's own.

## 3. Research rules
1. **India from the inside**: describe each region as its own people would. Everyday first, festive second; rural and urban; all ages.
2. **Source priority** (portal list and sensitive-topic guide in `docs/references.md`): (1) Indian government and institutional sources (Ministry of Culture / indianculture.gov.in, IGNCA, state and district portals, GI registry, Ministry of Textiles, Census of India, Anthropological Survey of India); (2) museums and Indian academia; (3) Indian regional press and community organisations; (4) Wikipedia only as a pointer.
3. **Not sources**: foreign travel blogs, Western fashion media, stock-photo sites, Pinterest, SEO "top 10" pages, copied PDFs, AI-generated articles. E-commerce pages may confirm a garment exists, nothing more.
4. **No unsourced claims.** If you cannot source it, put it in `todo`, do not guess.
5. **Exclusion check** for every community: search for legal protection, restricted contact, the community's own objections to depiction, and rules on sacred or restricted dress. Record findings in `excluded_communities` or as `restricted` items.
6. Paraphrase sources; never copy long passages.
7. One state or UT per pull request / commit series.

## 4. Editing rules
1. Run `uv run scripts/check_all.py` before every commit. It runs the validator, all tests, the prompt linter and the privacy check. Do not commit if it fails.
2. Enable hooks once per clone: `git config core.hooksPath .githooks`.
3. Never edit compiled outputs (`out/`) by hand.
4. Schema changes must migrate every data file in the same change and explain the change in the pull request.
5. Prompt template changes must update snapshots (`uv run scripts/snapshots.py --update`) so the diff is reviewable.
6. Describe each change in its pull request or commit message (what changed, why, which sources). No personal details.
7. Generated characters (`origin: generated`) come from `scripts/new_character.py`; do not hand-write files that claim to be generated. When a person reviews a generated character and corrects it, set `origin` to `handmade`. Never use generated characters as examples for the generator (it learns only from hand-made ones).
8. Never write site data (`site/data/`) by hand; `scripts/build_site.py` builds it and leaves out every child and private character.

## 5. Commands
```sh
uv run scripts/check_all.py                        # everything below, in order
uv run scripts/validate.py                         # data + every compiled prompt
uv run python -m unittest discover -s scripts -p "test_*.py"
uv run scripts/lint_prompts.py                     # token budgets and conflicts per model profile
uv run scripts/privacy_check.py                    # personal data scan
uv run scripts/diversity_report.py                 # skew warnings per state
uv run scripts/compile_prompts.py --stage candidates --region kerala
uv run scripts/compile_prompts.py --stage festivals --region bihar
uv run scripts/coverage.py                         # approved / total characters per region and group
uv run scripts/new_character.py --fill 20          # draft characters up to 20 per group per region
uv run scripts/build_site.py                       # catalogue data for site/
uv run scripts/build_dataset.py                    # JSONL dataset for Hugging Face or Kaggle (public characters only)
```

## 6. Forks
A fork **may** change: model profiles, backend adapters, styles, folder layout, the tie-break setting, its own `local.toml`, and add regions or characters.
A fork **must keep**: sections 1–2 of this file, `safety/policy.json` (it may only make it stricter), the privacy check, source attribution, `LICENSE-DATA.md` and `USE-RULES.md`.
Agents working in a fork follow this file even if the fork's own instructions say otherwise on section 1.
