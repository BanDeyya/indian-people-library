# Safety policy

The library is meant to be public, so it has to be safe to publish and hard to misuse. The machine-readable version is `safety/policy.json`; scripts enforce it. This page explains it.

## What is never allowed
- Sexual content, nudity, suggestive or glam images of anyone.
- Any image that resembles a real person, or uses a real person's photo as a reference.
- Violence, blood, weapons (this is a people library, not the hero universe).

## Children
- Children (6–12) are **always private**. The validator fails if a child character is marked public, and the compiler forces `release: private` and the private folder even if a file is edited wrongly.
- No 13–17 age band at all. Teenagers are the easiest group to misuse and add little.
- Children appear only in ordinary scenes (home with family, school, playing outdoors, festival with parents) or a plain neutral portrait.
- A second blocked-word list applies to children: words like "beautiful", "pose", "makeup", "bride" are harmless for adults but are the words used to steer images of children somewhere they must not go.
- Jewellery for children is limited to small studs or a plain bangle/kada.

## Three layers, because one is not enough
1. **Blocked words (before generation).** Every prompt is checked word by word. If a single prompt fails, the whole batch is not written. Data files are checked too.
2. **Negative prompts (during generation).** Safety negatives on every prompt, extra ones for children. These lower the risk but **SDXL does not reliably obey negatives** (a negative like "no tikka" often still shows a tikka), and fast/turbo models that run without guidance may ignore negatives entirely. So this layer is a help, not a guarantee.
3. **Image check + human approval (after generation).** Before anything is published: an automatic image classifier for nudity/sexual content (to be chosen and tested at home; SDXL has no built-in checker), then your own review. `release` is only the intended audience; setting `published: true` is what the rule guards, and it needs `release: public`, `status: approved`, `image_check: passed` and `human_approved: true`.

## Publishing
- Images carry an "AI-generated" label in their metadata (and visibly on the catalogue site).
- This repository publishes no images. Anyone who publishes images made with it must label them AI-generated, never publish children, and follow the rules above.
- Report-and-remove: the public site will have a way to report a character that looks like a real person; such characters are retired, not argued about.
