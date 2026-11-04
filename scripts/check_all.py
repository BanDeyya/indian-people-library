"""Run every check in order. Use before every commit (AGENTS.md section 4).

    uv run scripts/check_all.py            # all checks
    uv run scripts/check_all.py --ci       # same, but the privacy check skips the local denylist hint
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

STEPS = [
    ("validate", [PY, "scripts/validate.py"], True),
    ("tests", [PY, "-m", "unittest", "discover", "-s", "scripts", "-p", "test_*.py"], True),
    ("prompt lint", [PY, "scripts/lint_prompts.py"], True),
    ("snapshots", [PY, "scripts/snapshots.py"], True),
    ("privacy", [PY, "scripts/privacy_check.py"], True),
    ("diversity", [PY, "scripts/diversity_report.py"], False),
]


def main() -> int:
    failed = []
    for name, cmd, must_pass in STEPS:
        print(f"\n===== {name} =====", flush=True)
        res = subprocess.run(cmd, cwd=ROOT)
        if res.returncode != 0 and must_pass:
            failed.append(name)
    print("\n===== summary =====")
    print("FAILED: " + ", ".join(failed) if failed else "all checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
