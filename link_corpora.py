"""Link the two corpora: which ALJ decisions were appealed, and to what.

The Appellate Division reviews Civil Remedies decisions, and says which one it
is reviewing -- fields.reviews_decision_no reads that off the Appellate record.
The other direction is the useful one and cannot be read off a single decision:
an ALJ has no way of knowing, at the time, whether anyone will appeal.

So this is a join, done after both corpora are built, and it is exact rather
than inferred: an ALJ decision is appealed if some Appellate decision names it.

    python link_corpora.py out/dab.parquet out/alj.parquet

What it cannot tell you: an appeal that was filed and settled, withdrawn, or is
still pending produces no Appellate decision, so an empty appealed_in means "no
Appellate decision in this corpus names it", not "nobody appealed".
"""
from __future__ import annotations

import argparse
import collections
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("appellate", type=Path)
    ap.add_argument("alj", type=Path)
    args = ap.parse_args()

    dab = pq.read_table(args.appellate)
    reviewed: dict[str, list[str]] = collections.defaultdict(list)
    for number, reviews in zip(dab.column("decision_no").to_pylist(),
                               dab.column("reviews_decision_no").to_pylist()):
        if reviews and number:
            reviewed[reviews].append(number)

    alj = pq.read_table(args.alj)
    nos = alj.column("decision_no").to_pylist()
    appealed_in = [sorted(reviewed.get(n, [])) if n else [] for n in nos]

    field = pa.field("appealed_in", pa.list_(pa.string()))
    if "appealed_in" in alj.column_names:
        alj = alj.set_column(alj.schema.get_field_index("appealed_in"), field,
                             pa.array(appealed_in, type=field.type))
    else:
        alj = alj.append_column(field, pa.array(appealed_in, type=field.type))
    pq.write_table(alj, args.alj, compression="zstd", compression_level=9)

    linked = sum(1 for a in appealed_in if a)
    named = len(reviewed)
    resolved = sum(1 for k in reviewed if k in set(n for n in nos if n))
    print(f"{linked} of {alj.num_rows} ALJ decisions are named by an Appellate "
          f"decision ({linked / alj.num_rows:.1%})")
    print(f"  Appellate decisions naming one: "
          f"{sum(len(v) for v in reviewed.values())}, pointing at {named} distinct "
          f"numbers, {resolved} of which are held here ({resolved / named:.0%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
