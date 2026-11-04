# Running jobs on an image backend

This repository does not generate images and includes no backend adapter. It is backend- and model-agnostic: it compiles **jobs**, and you send them to whatever image backend you use with your own adapter. Your backend's address and settings go in `local.toml`, which is git-ignored and never committed.

## Job format (JSON Lines, from `scripts/compile_prompts.py`)

| field | meaning |
|---|---|
| `job_id` | e.g. `KL-AF-0001-candidate-03` |
| `character_id`, `stage` | `candidate`, `view-<name>`, `outfit-<item id>` |
| `folder` | folder to save into (backend folder or local directory) |
| `release` | `public` or `private` |
| `uses_reference`, `reference_image` | if true, pass the locked face to the backend's identity method (IP-Adapter, InstantID, character LoRA...) |
| `profile` | model profile the prompt was written for (`models/<id>.json`) |
| `prompt`, `negative_prompt` | already safety-checked; `negative_prompt` is empty for profiles that do not use negatives |
| `tokens`, `token_budget`, `dropped` | token count, budget for the profile, and optional prompt parts removed to fit |
| `width`, `height`, `seed` | fixed seed so a job can be re-run exactly |

## What every adapter must do
1. Re-run the safety check on every line before sending (never trust a file that may have been edited by hand).
2. Send jobs one at a time (or in the batch size the backend supports).
3. Save into the job's folder with the `job_id` and a stage tag.
4. Skip jobs already done (resume after a stop).
5. Write a results file: job_id → image id or path, status.
6. Never publish. Publishing is a separate step after the image check and human approval.

## Notes
- Some fast/turbo models run without classifier-free guidance and may ignore `negative_prompt`; for those, rely on the image check.
