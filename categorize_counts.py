#!/usr/bin/env python3
"""Count candidate-category hits across dab.jsonl / alj.jsonl to find
naturally-bounded slices (~50-100 records) before committing to any of them.
"""
import json
import re
import sys
from pathlib import Path

def norm(text):
    return re.sub(r"\s+", " ", text)

CATEGORIES = {
    # naturally small, self-contained
    "ori_research_misconduct": re.compile(
        r"office of research integrity|research misconduct|42\s*C\.?\s*F\.?\s*R\.?\s*part\s*93",
        re.IGNORECASE),
    "clia_lab_sanctions": re.compile(
        r"\bCLIA\b|clinical laboratory improvement|42\s*C\.?\s*F\.?\s*R\.?\s*part\s*493",
        re.IGNORECASE),
    "emtala_cmp": re.compile(
        r"\bEMTALA\b|emergency medical treatment and (active )?labor act|1395dd",
        re.IGNORECASE),
    "opo_decert": re.compile(
        r"organ procurement organization|42\s*C\.?\s*F\.?\s*R\.?\s*part\s*486",
        re.IGNORECASE),
    "samhsa_otp_cert": re.compile(
        r"opioid treatment program|42\s*C\.?\s*F\.?\s*R\.?\s*part\s*8\b",
        re.IGNORECASE),
    "ihs_isdeaa": re.compile(
        r"indian self-determination|ISDEAA|self-determination (and education )?assistance act|\b638 contract",
        re.IGNORECASE),
    "head_start": re.compile(r"head start", re.IGNORECASE),
    "title_ivd_child_support": re.compile(
        r"title iv-d|child support enforcement", re.IGNORECASE),

    # OIG exclusion sub-bases, 1128(b)
    "excl_b3_controlled_substance": re.compile(
        r"1128\s*\(\s*b\s*\)\s*\(\s*3\s*\)", re.IGNORECASE),
    "excl_b4_license_revocation": re.compile(
        r"1128\s*\(\s*b\s*\)\s*\(\s*4\s*\)", re.IGNORECASE),
    "excl_b6_quality_care": re.compile(
        r"1128\s*\(\s*b\s*\)\s*\(\s*6\s*\)", re.IGNORECASE),
    "excl_b7_fraud_kickback": re.compile(
        r"(?:1320a[\s\-‐-―]?7|1128)\s*\(\s*b\s*\)\s*\(\s*7\s*\)", re.IGNORECASE),
    "excl_b14_loan_default": re.compile(
        r"1128\s*\(\s*b\s*\)\s*\(\s*14\s*\)", re.IGNORECASE),

    # enrollment revocation grounds, 42 CFR 424.535(a)
    "enroll_a3_felony": re.compile(
        r"424\.535\s*\(\s*a\s*\)\s*\(\s*3\s*\)", re.IGNORECASE),
    "enroll_a5_nonoperational": re.compile(
        r"424\.535\s*\(\s*a\s*\)\s*\(\s*5\s*\)", re.IGNORECASE),
    "enroll_a8_billing_abuse": re.compile(
        r"424\.535\s*\(\s*a\s*\)\s*\(\s*8\s*\)", re.IGNORECASE),
}

def count_file(path):
    counts = {name: 0 for name in CATEGORIES}
    total = 0
    if not Path(path).exists():
        return counts, total
    with open(path, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            text = norm(rec["text"])
            total += 1
            for name, rx in CATEGORIES.items():
                if rx.search(text):
                    counts[name] += 1
    return counts, total

def main():
    files = sys.argv[1:] or ["dab.jsonl", "alj.jsonl"]
    results = {}
    for f in files:
        counts, total = count_file(f)
        results[f] = (counts, total)

    names = list(CATEGORIES)
    width = max(len(n) for n in names)
    header = f"{'category':<{width}}  " + "  ".join(f"{f:>10}" for f in files)
    print(header)
    print("-" * len(header))
    for name in names:
        row = f"{name:<{width}}  "
        row += "  ".join(f"{results[f][0][name]:>10}" for f in files)
        print(row)
    print("-" * len(header))
    print(f"{'TOTAL records':<{width}}  " + "  ".join(f"{results[f][1]:>10}" for f in files))

if __name__ == "__main__":
    main()
