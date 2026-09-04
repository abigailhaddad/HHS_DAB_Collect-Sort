#!/usr/bin/env python3
"""Build a manifest for each corpus (DAB, ALJ) describing every category
slice derived from it: file name, legal basis, citation, and record count.
Counts are read live from the files on disk, not hardcoded.
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent

DESCRIPTIONS = {
    "b7": ("OIG permissive exclusion for fraud, kickback, or related offenses",
           "42 U.S.C. 1320a-7(b)(7) / 1128(b)(7)"),
    "clia_lab_sanctions": ("CLIA laboratory certificate sanctions (revocation, suspension, CMP)",
                            "42 CFR Part 493"),
    "excl_b3_controlled_substance": ("OIG exclusion for controlled substance conviction",
                                      "42 U.S.C. 1128(b)(3)"),
    "excl_b4_license_revocation": ("OIG exclusion for license revocation or surrender",
                                    "42 U.S.C. 1128(b)(4)"),
    "excl_b6_quality_care": ("OIG exclusion for failure to provide quality care",
                              "42 U.S.C. 1128(b)(6)"),
    "excl_b14_loan_default": ("OIG exclusion for default on health education loan/scholarship obligation",
                               "42 U.S.C. 1128(b)(14)"),
    "enroll_a3_felony": ("Provider enrollment revocation for felony conviction",
                          "42 CFR 424.535(a)(3)"),
    "enroll_a5_nonoperational": ("Provider enrollment revocation, non-operational provider/supplier",
                                  "42 CFR 424.535(a)(5)"),
    "enroll_a8_billing_abuse": ("Provider enrollment revocation for abuse of billing privileges",
                                 "42 CFR 424.535(a)(8)"),
    "title_ivd_child_support": ("Title IV-D child support enforcement penalty/audit disallowances",
                                 "Title IV-D, Social Security Act"),
    "head_start": ("Head Start grant disputes (termination, denial of refunding, and related actions)",
                    "Head Start Act; 45 CFR Part 1303"),
    "ihs_isdeaa": ("Indian Self-Determination and Education Assistance Act contract/funding disputes",
                    "25 U.S.C. 5301 et seq. (ISDEAA)"),
    "ori_research_misconduct": ("Research misconduct findings (PHS/ORI) reviewed on appeal",
                                 "42 CFR Part 93"),
    "emtala_cmp": ("EMTALA screening/stabilization civil money penalties",
                    "42 U.S.C. 1395dd (EMTALA)"),
    "opo_decert": ("Organ procurement organization decertification/recertification",
                    "42 CFR Part 486"),
}


def count_lines(path: Path) -> int:
    with path.open(encoding="utf-8") as f:
        return sum(1 for _ in f)


def build_manifest(corpus: str, source_file: str):
    source_path = ROOT / source_file
    source_total = count_lines(source_path) if source_path.exists() else None

    slices = []
    for path in sorted(ROOT.glob(f"{corpus}_*.jsonl")):
        category = path.stem[len(corpus) + 1:]
        desc, citation = DESCRIPTIONS.get(category, ("", ""))
        slices.append({
            "file": path.name,
            "category": category,
            "description": desc,
            "citation": citation,
            "record_count": count_lines(path),
        })

    manifest = {
        "corpus": corpus,
        "source_file": source_file,
        "source_total_records": source_total,
        "slice_count": len(slices),
        "slices": slices,
    }
    out_path = ROOT / f"manifest_{corpus}.json"
    out_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{out_path.name}: {len(slices)} slices")


if __name__ == "__main__":
    build_manifest("dab", "dab.jsonl")
    build_manifest("alj", "alj.jsonl")
