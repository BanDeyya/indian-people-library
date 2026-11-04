"""Print a coverage table: approved / total characters per region and group.

Cells show approved / total characters. Children are counted but marked private.

    uv run scripts/coverage.py
"""
from __future__ import annotations

import sys

from lib import GROUP_LABELS, load_characters, load_regions

TARGET_PER_CELL = 3  # "a few per state per group" before claiming coverage


def table() -> str:
    regions = load_regions()
    chars = [c for _, c in load_characters()]
    # child columns are shown only where child character files exist
    groups = [g for g in GROUP_LABELS if not g.startswith("child_") or any(c["group"] == g for c in chars)]
    counts = {(r, g): [0, 0] for r in regions for g in groups}
    for c in chars:
        cell = counts.get((c["region"], c["group"]))
        if cell is None:
            continue
        cell[1] += 1
        if c["status"] == "approved":
            cell[0] += 1

    head = "| Region | Status | " + " | ".join(
        GROUP_LABELS[g] + (" 🔒" if g.startswith("child_") else "") for g in groups) + " |"
    sep = "|---|---|" + "---|" * len(groups)
    rows = []
    for slug, r in regions.items():
        cells = []
        for g in groups:
            ok, total = counts[(slug, g)]
            mark = " ✅" if ok >= TARGET_PER_CELL else ""
            cells.append(f"{ok}/{total}{mark}")
        rows.append(f"| {r['name']} | {r['status']} | " + " | ".join(cells) + " |")
    note = (f"\nCells are approved / total. ✅ = at least {TARGET_PER_CELL} approved. "
            + ("🔒 = private, never published. " if any(g.startswith("child_") for g in groups) else "")
            + "Regions: "
            f"{len(regions)} of 36 states and UTs.\n")
    return "\n".join([head, sep, *rows]) + "\n" + note


def main() -> int:
    print(table())
    return 0


if __name__ == "__main__":
    sys.exit(main())
