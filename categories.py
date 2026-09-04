"""Every category defined once: pattern, description, legal citation.

Previously the pattern lived in categorize_counts.py, the description and
citation in build_manifests.py, and the slice's name was whatever got typed on
the command line. The three drifted -- the counter called it
"excl_b7_fraud_kickback", the manifest looked up "b7" and found nothing, and
"samhsa_otp_cert" had a pattern but no description at all, so it would have
shipped with a blank legal basis. One dict prevents that class of bug.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    name: str
    description: str
    citation: str
    pattern: re.Pattern

    @property
    def regex(self) -> re.Pattern:
        return self.pattern


def _c(name, description, citation, pattern):
    return Category(name, description, citation, re.compile(pattern, re.IGNORECASE))


CATEGORIES = {c.name: c for c in [
    # --- program areas -------------------------------------------------------
    _c("ori_research_misconduct",
       "Research misconduct findings (PHS/ORI) reviewed on appeal",
       "42 CFR Part 93",
       r"office of research integrity|research misconduct"
       r"|42\s*C\.?\s*F\.?\s*R\.?\s*part\s*93"),
    _c("clia_lab_sanctions",
       "CLIA laboratory certificate sanctions (revocation, suspension, CMP)",
       "42 CFR Part 493",
       r"\bCLIA\b|clinical laboratory improvement"
       r"|42\s*C\.?\s*F\.?\s*R\.?\s*part\s*493"),
    _c("emtala_cmp",
       "EMTALA screening/stabilization civil money penalties",
       "42 U.S.C. 1395dd (EMTALA)",
       r"\bEMTALA\b|emergency medical treatment and (?:active )?labor act|1395dd"),
    _c("opo_decert",
       "Organ procurement organization decertification/recertification",
       "42 CFR Part 486",
       r"organ procurement organization|42\s*C\.?\s*F\.?\s*R\.?\s*part\s*486"),
    _c("samhsa_otp_cert",
       "Opioid treatment program certification (SAMHSA)",
       "42 CFR Part 8",
       r"opioid treatment program|42\s*C\.?\s*F\.?\s*R\.?\s*part\s*8\b"),
    _c("ihs_isdeaa",
       "Indian Self-Determination and Education Assistance Act contract/funding disputes",
       "25 U.S.C. 5301 et seq. (ISDEAA)",
       r"indian self-determination|ISDEAA"
       r"|self-determination (?:and education )?assistance act|\b638 contract"),
    _c("head_start",
       "Head Start grant disputes (termination, denial of refunding, and related actions)",
       "Head Start Act; 45 CFR Part 1303",
       r"head start"),
    _c("title_ivd_child_support",
       "Title IV-D child support enforcement penalty/audit disallowances",
       "Title IV-D, Social Security Act",
       r"title iv-d|child support enforcement"),

    # --- OIG exclusion sub-bases, section 1128(b) ----------------------------
    _c("excl_b3_controlled_substance",
       "OIG exclusion for controlled substance conviction",
       "42 U.S.C. 1320a-7(b)(3) / 1128(b)(3)",
       r"(?:1320a[\s\-‐-―]*7|1128)\s*\(\s*b\s*\)\s*\(\s*3\s*\)"),
    _c("excl_b4_license_revocation",
       "OIG exclusion for license revocation or surrender",
       "42 U.S.C. 1320a-7(b)(4) / 1128(b)(4)",
       r"(?:1320a[\s\-‐-―]*7|1128)\s*\(\s*b\s*\)\s*\(\s*4\s*\)"),
    _c("excl_b6_quality_care",
       "OIG exclusion for failure to provide quality care",
       "42 U.S.C. 1320a-7(b)(6) / 1128(b)(6)",
       r"(?:1320a[\s\-‐-―]*7|1128)\s*\(\s*b\s*\)\s*\(\s*6\s*\)"),
    _c("excl_b7_fraud_kickback",
       "OIG permissive exclusion for fraud, kickback, or related offenses",
       "42 U.S.C. 1320a-7(b)(7) / 1128(b)(7)",
       r"(?:1320a[\s\-‐-―]*7|1128)\s*\(\s*b\s*\)\s*\(\s*7\s*\)"),
    _c("excl_b14_loan_default",
       "OIG exclusion for default on health education loan/scholarship obligation",
       "42 U.S.C. 1320a-7(b)(14) / 1128(b)(14)",
       r"(?:1320a[\s\-‐-―]*7|1128)\s*\(\s*b\s*\)\s*\(\s*14\s*\)"),

    # --- enrollment revocation grounds, 42 CFR 424.535(a) --------------------
    _c("enroll_a3_felony",
       "Provider enrollment revocation for felony conviction",
       "42 CFR 424.535(a)(3)",
       r"424\.535\s*\(\s*a\s*\)\s*\(\s*3\s*\)"),
    _c("enroll_a5_nonoperational",
       "Provider enrollment revocation, non-operational provider/supplier",
       "42 CFR 424.535(a)(5)",
       r"424\.535\s*\(\s*a\s*\)\s*\(\s*5\s*\)"),
    _c("enroll_a8_billing_abuse",
       "Provider enrollment revocation for abuse of billing privileges",
       "42 CFR 424.535(a)(8)",
       r"424\.535\s*\(\s*a\s*\)\s*\(\s*8\s*\)"),
]}
