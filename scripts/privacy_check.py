"""Privacy check: fail if anything personal is about to enter the repo.

Checks every tracked/staged file, commit messages and commit identities for:
  * generic patterns (personal emails, home paths, hardware specs, keys, private links)
  * entries in `.privacy-denylist` (git-ignored, one term per line, kept only on the
    maintainer's own machines). Matches from the denylist are reported by entry number,
    never by the term itself, so CI logs cannot leak it.

    uv run scripts/privacy_check.py                  # files + all commits
    uv run scripts/privacy_check.py --commit-msg F   # one commit message file (git hook)
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DENYLIST = ROOT / ".privacy-denylist"

ALLOWED_EMAILS = re.compile(r"(@users\.noreply\.github\.com|^noreply@anthropic\.com)$", re.I)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")

GENERIC = {
    "absolute home path": re.compile(
        r"((?<![\w/])/Users/[A-Za-z][A-Za-z0-9._-]*|(?<![\w/])/home/[A-Za-z][A-Za-z0-9._-]*/|[A-Za-z]:\\Users\\)"),
    "hardware spec": re.compile(
        r"(\b\d{1,3}\s?GB\s+(RAM|of RAM|unified|VRAM|memory)\b|\bMacBook\b|\biMac\b|\bMac (mini|Studio|Pro)\b"
        r"|\bApple M[1-9]\b|\bM[1-9] (Pro|Max|Ultra)\b|\b[RG]TX\s?\d{3,4}\b|\b\d{1,2}-core GPU\b)", re.I),
    "IP address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "secret-like token": re.compile(
        r"(sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}"
        r"|hf_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{10,})"),
    "private session/chat link": re.compile(r"claude\.ai/(code/)?(session|chat)[/_]", re.I),
}
# Generated lock files only get the denylist + secret check (they are full of version numbers).
LOCKFILES = {"uv.lock"}
SKIP_SELF = {"scripts/privacy_check.py", "scripts/test_privacy.py"}  # contain the patterns themselves


def load_denylist() -> list[str]:
    if not DENYLIST.exists():
        return []
    return [ln.strip().lower() for ln in DENYLIST.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")]


def scan_text(text: str, where: str, deny: list[str], generic: bool = True) -> list[str]:
    hits: list[str] = []
    for n, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        for i, term in enumerate(deny, start=1):
            if term in low:
                hits.append(f"{where}:{n}: matches denylist entry #{i}")
        if generic:
            for m in EMAIL.finditer(line):
                if not ALLOWED_EMAILS.search(m.group(0)):
                    hits.append(f"{where}:{n}: email address")
            for label, pat in GENERIC.items():
                if pat.search(line):
                    hits.append(f"{where}:{n}: {label}")
    return hits


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False).stdout


def check_files(deny: list[str]) -> list[str]:
    hits: list[str] = []
    for rel in sorted(set(git("ls-files", "--cached").splitlines())):
        path = ROOT / rel
        if rel in SKIP_SELF or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if rel in LOCKFILES:
            hits += [h for h in scan_text(text, rel, deny, generic=False)]
            hits += [f"{rel}:{n}: secret-like token" for n, ln in enumerate(text.splitlines(), 1)
                     if GENERIC["secret-like token"].search(ln)]
        else:
            hits += scan_text(text, rel, deny)
    return hits


def check_commits(deny: list[str]) -> list[str]:
    hits: list[str] = []
    log = git("log", "--all", "--format=%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%B%x1e")
    for rec in filter(None, (r.strip() for r in log.split("\x1e"))):
        sha, an, ae, cn, ce, body = (rec.split("\x1f") + [""] * 6)[:6]
        short = sha[:8]
        for email in (ae, ce):
            if email and not ALLOWED_EMAILS.search(email):
                hits.append(f"commit {short}: author/committer email is not a noreply address")
        hits += scan_text(f"{an}\n{cn}", f"commit {short} identity", deny, generic=False)
        hits += scan_text(body, f"commit {short} message", deny)
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit-msg", type=Path, help="check only this commit message file")
    ap.add_argument("--files-only", action="store_true")
    args = ap.parse_args()
    deny = load_denylist()

    if args.commit_msg:
        hits = scan_text(args.commit_msg.read_text(encoding="utf-8"), "commit message", deny)
    else:
        hits = check_files(deny)
        if not args.files_only:
            hits += check_commits(deny)

    for h in hits:
        print(f"PRIVACY {h}")
    note = "" if deny else " (no .privacy-denylist found: generic checks only)"
    print(f"\n{len(hits)} privacy problem(s){note}")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
