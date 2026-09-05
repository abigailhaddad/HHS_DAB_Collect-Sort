"""End to end: PDFs in, slices and a manifest out. Generates its own PDFs."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import categories

pymupdf = pytest.importorskip("pymupdf", reason="PDF generation needs pymupdf")

ROOT = Path(__file__).resolve().parents[1]

DECISION = (
    "Department of Health and Human Services\nDEPARTMENTAL APPEALS BOARD\n"
    "Civil Remedies Division\nIn the Case of:\nTest Provider, LLC,\nPetitioner,\n"
    "- v. -\nCenters for Medicare & Medicaid Services.\nDate: March 4, 2024\n"
    "Docket No. C-23-101\nDecision No. CR9999\n\nDECISION\n\n"
    "I sustain the determination of CMS to revoke Petitioner's Medicare billing\n"
    "privileges under 42 C.F.R. section 424.535(a)(3) based on a felony\n"
    "conviction. The revocation under section 424.535(a)(3) is lawful.\n")


def run(*args, cwd):
    r = subprocess.run([sys.executable, *args], cwd=cwd,
                       capture_output=True, text=True)
    assert r.returncode == 0, f"{args}\nstdout:{r.stdout}\nstderr:{r.stderr}"
    return r


@pytest.fixture
def corpus(tmp_path):
    pdfs = tmp_path / "pdfs"
    pdfs.mkdir()
    d = pymupdf.open()
    d.new_page().insert_text((60, 70), DECISION, fontsize=9)
    d.save(str(pdfs / "2024.03.04 CR9999 Test Provider LLC v. CMS.pdf"))
    d.close()
    d = pymupdf.open()                      # no text layer at all
    d.new_page().draw_rect(pymupdf.Rect(50, 50, 300, 300))
    d.save(str(pdfs / "2024.03.05 CR9998 Scanned Only.pdf"))
    d.close()
    return tmp_path


def test_full_pipeline(corpus):
    run(str(ROOT / "extract.py"), "pdfs", "-o", "alj.jsonl", cwd=corpus)
    records = [json.loads(l) for l in (corpus / "alj.jsonl").read_text().splitlines()]
    assert len(records) == 2
    good = next(r for r in records if "CR9999" in r["id"])
    assert good["text_layer_ok"] is True
    blank = next(r for r in records if "CR9998" in r["id"])
    assert blank["text_layer_ok"] is False
    # The operator's absolute path is not a property of the decision.
    assert "source_path" not in good

    run(str(ROOT / "build_dataset.py"), "alj.jsonl", "--corpus", "alj",
        "-o", "out", cwd=corpus)
    assert (corpus / "out" / "alj.parquet").exists()

    run(str(ROOT / "build_slices.py"), "out/alj.parquet",
        "-o", "out/slices.parquet", cwd=corpus)
    import pyarrow.parquet as pq
    sl = pq.read_table(corpus / "out" / "slices.parquet")
    cats = sl.column("category").to_pylist()
    assert "enroll_a3_felony" in cats
    # One membership row per (decision, category), not a copy of the decision.
    assert set(sl.column_names) == {"corpus", "id", "decision_no", "category",
                                    "match_count", "matches_in_citations",
                                    "first_match_char"}

    run(str(ROOT / "build_manifests.py"), "--dir", "out", cwd=corpus)
    manifest = json.loads((corpus / "out" / "manifest_alj.json").read_text())
    # Every category is listed, empty ones included: a category that matched
    # nothing is a fact, and omitting it looks like it was never tried.
    assert manifest["category_count"] == len(categories.CATEGORIES)
    assert len(manifest["slices"]) == len(categories.CATEGORIES)
    assert manifest["slice_count"] >= 1
    for s in manifest["slices"]:
        assert s["description"] and s["citation"], s["category"]


def test_metadata_survives_the_round_trip(corpus):
    run(str(ROOT / "extract.py"), "pdfs", "-o", "alj.jsonl", cwd=corpus)
    run(str(ROOT / "build_dataset.py"), "alj.jsonl", "--corpus", "alj",
        "-o", "out", cwd=corpus)
    import pyarrow.parquet as pq
    t = pq.read_table(corpus / "out" / "alj.parquet")
    by_id = dict(zip(t.column("id").to_pylist(), range(t.num_rows)))
    i = next(v for k, v in by_id.items() if "CR9999" in k)
    assert t.column("decision_no").to_pylist()[i] == "CR9999"
    assert t.column("tribunal").to_pylist()[i] == "Civil Remedies Division"
    assert t.column("respondent").to_pylist()[i] == "CMS"
    assert t.column("year").to_pylist()[i] == 2024


def test_missing_corpus_file_fails_loudly(tmp_path):
    # All-zero counts for a missing file read exactly like a category with no
    # hits, so categorize_counts.py used to report a clean empty table.
    r = subprocess.run([sys.executable, str(ROOT / "categorize_counts.py"),
                        "nope.jsonl"], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode != 0
    assert "no such file" in (r.stdout + r.stderr).lower()
