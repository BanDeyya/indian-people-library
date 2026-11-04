# Contributing

Thank you for helping. The rules in [AGENTS.md](AGENTS.md) apply to people too: please read sections 1–3 first.

## Ways to help
- **Review your own state.** If you grew up in a state or belong to a community, reviewing its region file is the most valuable help there is. Open an issue with the "Native review" template, or comment on the state's issue. You are credited by GitHub username or a pseudonym, never by real name unless you ask.
- **Research a state** that is not done yet (run `uv run scripts/coverage.py` and see the issues labelled `research`).
- **Improve prompts** for a model you use, by adding or tuning a profile in `models/`.
- **Add a backend adapter** for a server you run.

## Adding or updating a state
1. Take the state's issue and follow its checklist.
2. Use the source priority in `AGENTS.md` section 3. Every fact needs a source; unsure things go in `todo`.
3. Check every community for exclusion or restricted items (AGENTS.md 3.5).
4. Run `uv run scripts/check_all.py`.
5. Open a pull request using the template.

## Privacy
Never put personal details (yours or anyone's) in files, commit messages, issues or PRs. Commit with your GitHub noreply email. Run `git config core.hooksPath .githooks` once so the privacy check runs before each commit. Your own private terms can go in `.privacy-denylist` (git-ignored).

## Licence
Code contributions are MIT (`LICENSE`). Data contributions are under `LICENSE-DATA.md` (CC BY 4.0) and must follow `USE-RULES.md`.
