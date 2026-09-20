"""Build the single combined Parquet the web explorer loads whole into DuckDB-WASM.

Modeled on usajobs_historical's site: no backend, the browser fetches one
Parquet file and queries it in memory (see web/shared/wasm-api.js there for
why "fetch once, query locally" beats range-reading a file this size).

    python build_web_data.py --dir out/ -o web/data/decisions.parquet
"""
from __future__ import annotations

import argparse
import collections
import re
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

import categories
import jsonl

# respondent (build_dataset.py's own field) is which of six government
# offices is a party -- CMS, Inspector General, etc. -- never the actual
# doctor, facility, or company, because that's simply not what
# metadata.RESPONDENTS's regex list extracts. That name was never captured
# anywhere in the corpus-building pipeline, but it didn't need to be: the
# Board's own index already carries it in the caption ("The Inspector
# General v. Roy W. Schoettle, D.O.", "CTP v. Rusda Oil Company Inc."), and
# build_dataset.py reads that record already (for source_url) without ever
# looking at .caption. This parses it back out for the site, from
# decisions_index.jsonl, which already exists locally -- no corpus rebuild,
# no re-fetching a single decision.
_CAPTION_PREFIX = re.compile(r"^\s*\d{4}\.\d{2}\.\d{2}\s*[.,;]?\s*")
_DECISION_NO_TOKEN = re.compile(
    r"^(?:ALJ\s+)?Ruling\s+No\.?\s*[\d\-]+\s*[.,;]?\s*"
    r"|^[A-Za-z0-9\-]+\s*[.,;]?\s*", re.IGNORECASE)
_VS = re.compile(r"\s+vs?\.?\s+", re.IGNORECASE)
# The same government-party list metadata.RESPONDENTS classifies a decision
# by, plus HHS/FDA/CTP forms that show up in captions but never in
# RESPONDENTS (that list was built for ALJ/Appellate headers, which never
# say "FDA" in so many words the way a caption does).
_GOVT_PARTY = re.compile(
    r"(?i:\bthe\s+inspector\s+general\b)|\bI\.\s?G\.\b"
    r"|centers\s+for\s+medicare\s*&?\s*(?:and\s*)?medicaid\s+services|\bCMS\b"
    r"|health\s+care\s+financing\s+administration|\bHCFA\b"
    r"|administration\s+for\s+children\s+and\s+families|\bACF\b"
    r"|office\s+of\s+human\s+development\s+services|\bOHDS\b"
    r"|office\s+of\s+research\s+integrity|\bORI\b"
    r"|department\s+of\s+health\s+and\s+human\s+services"
    r"|\bCTP\b|center\s+for\s+tobacco\s+products|\bFDA\b|food\s+and\s+drug\s+administration",
    re.IGNORECASE)
_TRAILING_ROLE = re.compile(
    r",?\s*(?:Petitioner|Respondent|Appellant|Appellee)\.?\s*$", re.IGNORECASE)
_IN_RE = re.compile(r"^(?:in\s+the\s+matter\s+of|in\s+re)\s+", re.IGNORECASE)


def party_name_from_caption(caption: str | None) -> str | None:
    """The non-government party's name from an index caption, best-effort."""
    if not caption:
        return None
    text = _CAPTION_PREFIX.sub("", caption).strip()
    text = _DECISION_NO_TOKEN.sub("", text, count=1).strip()
    text = _IN_RE.sub("", text)
    parts = _VS.split(text, maxsplit=1)
    if len(parts) == 2:
        a, b = (p.strip() for p in parts)
        a_govt, b_govt = bool(_GOVT_PARTY.search(a)), bool(_GOVT_PARTY.search(b))
        text = b if (a_govt and not b_govt) else a
    text = _TRAILING_ROLE.sub("", text).strip().strip(",.;: ")
    return text or None


def load_party_names(index_path: Path) -> dict[str, str]:
    """"division#decision_no" -> party name. A number the Board lists twice
    cannot identify a caption, so -- same rule build_dataset.py's own
    index_lookup() follows -- a key seen with two different captions is
    dropped rather than guessed at."""
    if not index_path.exists():
        return {}
    lookup: dict[str, str] = {}
    ambiguous: set[str] = set()
    for r in jsonl.read(index_path):
        if not r.get("decision_no"):
            continue
        key = f"{r['division']}#{r['decision_no']}".lower()
        name = party_name_from_caption(r.get("caption"))
        if not name:
            continue
        if key in lookup and lookup[key] != name:
            ambiguous.add(key)
        else:
            lookup[key] = name
    for key in ambiguous:
        lookup.pop(key, None)
    return lookup

# fields.judges() finds a real name in the source text, but the text itself is
# sometimes wrong: a signature line's kerning gets read as a stray mid-word
# space ("Bill Tho mas"), a scan misreads one letter ("Riotto" -> "Piotto"),
# or the name-matching regex runs on past the sentence that follows it
# ("Joseph K. Riotto. On"). None of that is fixable by re-reading the text
# more carefully -- the extracted string itself is what's wrong -- so this is
# a hand-built alias table from the ~195 distinct strings actually observed
# in the corpus, each checked against how often it appears and what it's
# probably a corruption of. It's assembled to be conservative: a name only
# merges into another when they share a surname (allowing a one-letter typo
# or a clear truncation), never on a first-name coincidence alone. Applied
# here, for the web explorer's filters and display, not to the archival text.
_JUDGE_DROP = {
    "Administrative Law Judge",   # the title itself, not a name -- a
    "Presiding Board Member",     # signature block with no name matched
}
_JUDGE_ALIASES = {
    "Bill Tho": "Bill Thomas",
    "Leslie Sussan": "Leslie A. Sussan",
    "Steve T. Kessel": "Steven T. Kessel",
    "Steven T.": "Steven T. Kessel",
    "Steven Kessel": "Steven T. Kessel",
    "Steven T. Xessel": "Steven T. Kessel",
    "Steven T. Keseel": "Steven T. Kessel",
    "Steven T. Kessel. Judge": "Steven T. Kessel",
    "Constance B. Tobi": "Constance B. Tobias",
    "Constance A. Tobias": "Constance B. Tobias",
    "Constance Tobias": "Constance B. Tobias",
    "Constance T. O' Bryant": "Constance T. O'Bryant",
    "ConStance T. O'Bryant": "Constance T. O'Bryant",
    "Keith Sickendick": "Keith W. Sickendick",
    "Keith W. Sickendiek": "Keith W. Sickendick",
    "KEITH W. SICKENDICK": "Keith W. Sickendick",
    "Judith A.": "Judith A. Ballard",
    "Judith A. Ballard Presiding": "Judith A. Ballard",
    "Judith Ballard": "Judith A. Ballard",
    "Scott Ande": "Scott Anderson",
    "Sheila A. Hegy": "Sheila Ann Hegy",
    "Sheila Ann Heg": "Sheila Ann Hegy",
    "Shelia Ann Hegy": "Sheila Ann Hegy",
    "Sheila Hegy": "Sheila Ann Hegy",
    "Sheila An Hegy": "Sheila Ann Hegy",
    "Shelia A. Hegy": "Sheila Ann Hegy",
    "Leslie C.": "Leslie C. Rogall",
    "Donald F. Garrett Presiding": "Donald F. Garrett",
    "Susan S. Yi": "Susan S. Yim",
    "Susan A. Yim": "Susan S. Yim",
    "Christopher S. Ra": "Christopher S. Randolph",
    "Christopher S. Randolp": "Christopher S. Randolph",
    "Stephen H. Godek": "Stephen M. Godek",
    "Stephen G. Godek": "Stephen M. Godek",
    "Stephen Godek": "Stephen M. Godek",
    "Steven M. Godek": "Stephen M. Godek",
    "Stephen M. Oodek": "Stephen M. Godek",
    "M. Godek": "Stephen M. Godek",
    "Stephen' M. Go": "Stephen M. Godek",
    "Joseph Gr": "Joseph Grow",
    "Leslie A. We": "Leslie A. Weyn",
    "Catherine Ravinksi": "Catherine Ravinski",
    "Richard J.": "Richard J. Smith",
    "Cecilia Sparks Ford Presiding": "Cecilia Sparks Ford",
    "Cecilia S. Ford": "Cecilia Sparks Ford",
    "Cecila Sparks Ford": "Cecilia Sparks Ford",
    "Ford Presiding": "Cecilia Sparks Ford",
    "Joseph Y. Riotto": "Joseph K. Riotto",
    "Joseph K. Riotto. On": "Joseph K. Riotto",
    "Joseph K.": "Joseph K. Riotto",
    "Joseph K. Riotto. Having": "Joseph K. Riotto",
    "Joseph K. Riotto. He": "Joseph K. Riotto",
    "Joseph K. Riotto. At": "Joseph K. Riotto",
    "Joseph K. Piotto": "Joseph K. Riotto",
    "Joseph Riotto": "Joseph K. Riotto",
    "Charles E.'Stratton": "Charles E. Stratton",
    "Charles F. Stratton": "Charles E. Stratton",
    "Charles Stratton": "Charles E. Stratton",
    "M. Terry Johnson Presiding": "M. Terry Johnson",
    "M. Terry": "M. Terry Johnson",
    "Alexander G. Teitz Presiding": "Alexander G. Teitz",
    "Alfonso J. Monta": "Alfonso J. Montano",
    "Alfonso J. Montan": "Alfonso J. Montano",
    "Alfonso Monta": "Alfonso J. Montano",
    "Alfonso Montano": "Alfonso J. Montano",
    "Mimi Hwang Leahy's August": "Mimi Hwang Leahy",
    "Mum Hwang Leahy": "Mimi Hwang Leahy",
    "Mimi Hwang Leahy. The": "Mimi Hwang Leahy",
    "Mimi Hwang Leahy. By": "Mimi Hwang Leahy",
    "Mimi Hwang Leahy. CMS": "Mimi Hwang Leahy",
    "M. H. Leahy. The": "Mimi Hwang Leahy",
    "Edward D.": "Edward D. Steinman",
    "Edward D. Steinman. At": "Edward D. Steinman",
    "Edward Steinman": "Edward D. Steinman",
    "Benjamin Zeitlin": "Benjamin J. Zeitlin",
    "Thomas E. Malone": "Thomas Malone",
    "Marc R. Hillson. At": "Marc R. Hillson",
    "Marc Hillson": "Marc R. Hillson",
    "Mark R. Hillson": "Marc R. Hillson",
    "Francis DeGeorge": "Francis D. DeGeorge",
    "Frank DeGeorge": "Francis D. DeGeorge",
    "Francis D. Degeorge": "Francis D. DeGeorge",
    "Bernard Kelly": "Bernard E. Kelly",
    "David Dukes": "David V. Dukes",
    "David V. Dueks": "David V. Dukes",
    "Jill Clifton": "Jill S. Clifton",
    "Jill S. Clifton. On": "Jill S. Clifton",
    "Jill S. Clifton. Prior": "Jill S. Clifton",
    "Jill Clifton. Subsequently": "Jill S. Clifton",
    "Frank Dell'Acqua": "Frank L. Dell'Acqua",
    "Jose A. Anglada. The": "Jose A. Anglada",
    "Bernice Bernstein": "Bernice L. Bernstein",
    "Manuel Hiller": "Manuel B. Hiller",
    "Edwin Yourman": "Edwin H. Yourman",
    "Erwin Yourman": "Edwin H. Yourman",
    "Edward T. York": "Edward York",
    "Wilmot R. Hasting": "Wilmot R. Hastings",
    "Marion Silva's": "Marion Silva",
    "Marion Silva. Pursuant": "Marion Silva",
    "William T. Van Orman": "William Van Orman",
    "Stuart H. Clark": "Stuart H. Clarke",
    "Anabel Bowen": "Anabel Smith Bowen",
    "Date Charles D. Baker": "Charles D. Baker",
}


import re as _re

# "Presiding" (and "Presiding Board Member") is a title the extractor
# sometimes leaves attached to the last name on a multi-judge signature
# block, not part of anyone's name -- catches strays like "Settle Presiding"
# that have no fuller variant anywhere else in the corpus to alias to.
_PRESIDING_SUFFIX = _re.compile(r"\s+Presiding(?:\s+Board\s+Member)?$")


def normalize_judges(names: list[str] | None) -> list[str]:
    if not names:
        return []
    out, seen = [], set()
    for name in names:
        if name in _JUDGE_ALIASES:
            name = _JUDGE_ALIASES[name]
        else:
            name = _PRESIDING_SUFFIX.sub("", name)
        if name in _JUDGE_DROP:
            continue
        if name not in seen:
            seen.add(name)
            out.append(name)
    return sorted(out)


SITE_SCHEMA = pa.schema([
    ("id", pa.string()),
    ("corpus", pa.string()),
    ("decision_no", pa.string()),
    ("decision_date", pa.date32()),
    ("year", pa.int16()),
    ("tribunal", pa.string()),
    ("respondent", pa.string()),
    ("party_name", pa.string()),
    ("judges", pa.list_(pa.string())),
    ("dispositions", pa.list_(pa.string())),
    ("provider_ids", pa.list_(pa.string())),
    ("reviews_decision_no", pa.string()),
    ("appealed_in", pa.list_(pa.string())),
    ("categories", pa.list_(pa.string())),
    ("source_url", pa.string()),
    ("num_pages", pa.int32()),
    ("text", pa.string()),
])


def category_labels(path: Path) -> dict[str, str]:
    """category key -> description, e.g. "clia_lab_sanctions" -> "CLIA
    laboratory certificate sanctions (revocation, suspension, CMP)"."""
    cats = categories.load(path) if path else categories.load()
    return {name: c.description for name, c in cats.items()}


def load_categories(slices_path: Path, labels: dict[str, str]) -> dict[str, list[str]]:
    """id -> sorted list of category descriptions it belongs to."""
    if not slices_path.exists():
        return {}
    t = pq.read_table(slices_path, columns=["id", "category"])
    out: dict[str, list[str]] = collections.defaultdict(list)
    for id_, cat in zip(t.column("id").to_pylist(), t.column("category").to_pylist()):
        out[id_].append(labels.get(cat, cat))
    return {k: sorted(v) for k, v in out.items()}


def build(out_dir: Path, index_path: Path = Path("decisions_index.jsonl")) -> pa.Table:
    labels = category_labels(Path("categories.yaml"))
    cat_by_id = load_categories(out_dir / "slices.parquet", labels)
    party_by_key = load_party_names(index_path)

    rows = []
    for corpus in ("alj", "dab"):
        path = out_dir / f"{corpus}.parquet"
        if not path.exists():
            continue
        cols = ["id", "corpus", "decision_no", "decision_date", "year",
                "tribunal", "respondent", "judges", "dispositions",
                "provider_ids", "reviews_decision_no", "source_url",
                "num_pages", "text"]
        t = pq.read_table(path)
        if "appealed_in" not in t.column_names:
            t = t.append_column("appealed_in",
                                pa.array([None] * t.num_rows,
                                        type=pa.list_(pa.string())))
        cols.append("appealed_in")
        t = t.select(cols)
        for row in t.to_pylist():
            row["categories"] = cat_by_id.get(row["id"], [])
            row["judges"] = normalize_judges(row["judges"])
            key = f"{corpus}#{row['decision_no']}".lower() if row["decision_no"] else None
            row["party_name"] = party_by_key.get(key) if key else None
            rows.append(row)

    cols = {f.name: [r[f.name] for r in rows] for f in SITE_SCHEMA}
    return pa.Table.from_pydict(cols, schema=SITE_SCHEMA)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=Path("out"))
    ap.add_argument("-o", "--out", type=Path, default=Path("web/data/decisions.parquet"))
    args = ap.parse_args()

    table = build(args.dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, args.out, compression="zstd", compression_level=9)
    mb = args.out.stat().st_size / 1e6
    print(f"{args.out}: {table.num_rows} rows, {mb:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
