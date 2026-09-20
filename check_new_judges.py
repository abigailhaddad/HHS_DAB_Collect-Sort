"""Flag a newly-seen judge name that looks like a corruption of a known one.

build_web_data.py's judge-name cleanup (_JUDGE_ALIASES, _JUDGE_DROP) was built
by hand from the ~195 distinct strings fields.judges() had produced up to
2026-09-19 -- OCR letter-swaps, truncated signature lines, a couple of
mis-matched non-names. That list is frozen at build time; it says nothing
about a new decision that introduces a new corruption of an existing judge's
name, which would otherwise just sit in the corpus as an uninspected 196th
"distinct judge" indistinguishable from an actually-new appointee.

This diffs the roster of an incoming build against known_judges.json (the
canonical set as of the last review) and, for anything not already known,
checks whether it's suspicious close to something that is: same last word
(the surname, almost always) with a small edit distance, or high overall
similarity. A name with no close match is presumably a real new judge and is
added to the roster without complaint. A name that IS close to one already on
the roster gets held for a human, because that's exactly the shape of every
false "new judge" found in the original 195 -- a alias belongs in
build_web_data.py's _JUDGE_ALIASES, not in the roster as its own person.

    python check_new_judges.py web/data/decisions.parquet
    python check_new_judges.py web/data/decisions.parquet --file-issue
"""
from __future__ import annotations

import argparse
import difflib
import json
import subprocess
from pathlib import Path

import pyarrow.parquet as pq

ROSTER_PATH = Path("known_judges.json")
SURNAME_MAX_EDITS = 2
SIMILARITY_MIN = 0.82


def edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[-1]


def surname(name: str) -> str:
    return name.split()[-1] if name.split() else name


def closest_match(name: str, roster: list[str]) -> tuple[str, str] | None:
    """(known_name, reason), or None if nothing in the roster looks related."""
    ns = surname(name)
    for known in roster:
        if surname(known) == ns and known != name:
            return known, "same surname, different rest of name"
    for known in roster:
        ks = surname(known)
        if abs(len(ns) - len(ks)) <= SURNAME_MAX_EDITS and \
                edit_distance(ns, ks) <= SURNAME_MAX_EDITS and ns != ks:
            return known, f"surname \"{ns}\" is {edit_distance(ns, ks)} edit(s) from \"{ks}\""
    for known in roster:
        ratio = difflib.SequenceMatcher(None, name, known).ratio()
        if ratio >= SIMILARITY_MIN and name != known:
            return known, f"{ratio:.0%} similar to an existing entry"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("decisions", type=Path, help="web/data/decisions.parquet")
    ap.add_argument("--roster", type=Path, default=ROSTER_PATH)
    ap.add_argument("--file-issue", action="store_true",
                     help="open a GitHub issue if anything needs review")
    args = ap.parse_args()

    roster = json.loads(args.roster.read_text()) if args.roster.exists() else []
    roster_set = set(roster)

    t = pq.read_table(args.decisions, columns=["judges"])
    seen = set()
    for row in t.column("judges").to_pylist():
        seen.update(row or [])

    new_names = sorted(seen - roster_set)
    if not new_names:
        print("no new judge names")
        return 0

    flagged, clean_new = [], []
    for name in new_names:
        match = closest_match(name, roster)
        (flagged if match else clean_new).append((name, match))

    if clean_new:
        print(f"{len(clean_new)} new judge name(s), no close match in the roster "
              f"-- adding to {args.roster}:")
        for name, _ in clean_new:
            print(f"  {name}")
        roster_set.update(name for name, _ in clean_new)
        args.roster.write_text(json.dumps(sorted(roster_set), indent=2) + "\n")

    if flagged:
        lines = [f'"{name}" -- {reason} (existing: "{known}")'
                 for name, (known, reason) in flagged]
        print(f"\n{len(flagged)} name(s) look like a corruption of an existing "
              f"judge, held for review:")
        for l in lines:
            print(f"  {l}")
        print(f"\n::warning title=New judge names need review::"
              f"{'; '.join(lines)} -- add to _JUDGE_ALIASES in build_web_data.py "
              f"if confirmed, or to {args.roster} directly if it's really a new person.")
        if args.file_issue:
            body = ("These judge names appeared for the first time and look like "
                    "a corruption of one already on the roster:\n\n" +
                    "\n".join(f"- {l}" for l in lines) +
                    "\n\nIf it's the same person, add the alias in "
                    "`build_web_data.py`'s `_JUDGE_ALIASES`. If it's really a "
                    f"different person, add it to `{args.roster.name}` directly.")
            subprocess.run(
                ["gh", "issue", "create", "--title",
                 f"Review {len(flagged)} possibly-duplicate judge name(s)",
                 "--body", body, "--label", "data-quality"],
                check=False)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
