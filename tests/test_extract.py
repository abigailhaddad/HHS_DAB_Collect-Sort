"""Text extraction. HHS publishes decisions as both HTML and PDF."""
import pdf_to_jsonl as extract

DECISION_HTML = """<!doctype html><html><head><title>CR636</title>
<style>.nav{color:red}</style>
<script>var analytics={"docket":"C-99-001","fake":"not part of the decision"};</script>
</head><body>
<div class="nav">Skip Navigation</div>
<h1>Decision No. CR 636</h1>
<p>Department of Health &amp; Human Services</p>
<p>I sustain the determination to terminate Petitioner&#39;s provider agreement
under 42 C.F.R. &sect; 424.535(a)(3).</p>
</body></html>"""


def test_html_text_is_extracted(tmp_path):
    f = tmp_path / "cr636.html"
    f.write_text(DECISION_HTML, encoding="utf-8")
    text, pages = extract.extract_text(f)
    assert "Decision No. CR 636" in text
    assert "424.535(a)(3)" in text
    assert pages == 0                      # HTML has no page count


def test_html_entities_are_decoded(tmp_path):
    f = tmp_path / "cr636.html"
    f.write_text(DECISION_HTML, encoding="utf-8")
    text, _ = extract.extract_text(f)
    assert "Health & Human Services" in text
    assert "Petitioner's" in text
    assert "&amp;" not in text


def test_script_and_style_bodies_are_dropped(tmp_path):
    # Stripping tags alone leaves the script's contents behind as if they were
    # text on the page -- here an analytics blob carrying a docket number.
    f = tmp_path / "cr636.html"
    f.write_text(DECISION_HTML, encoding="utf-8")
    text, _ = extract.extract_text(f)
    assert "not part of the decision" not in text
    assert "C-99-001" not in text
    assert "color:red" not in text


def test_html_with_no_page_count_is_not_failed_by_the_per_page_floor():
    # The chars-per-page floor cannot apply when there are no pages; an HTML
    # decision is judged on having text at all.
    assert extract.text_quality("word " * 300, 0)[0] is True
    assert extract.text_quality("   ", 0)[0] is False


def test_both_suffixes_are_collected(tmp_path):
    for name in ("a.pdf", "b.html", "c.HTM", "d.txt", "_failures.jsonl"):
        (tmp_path / name).write_text("x")
    wanted = extract.HTML_SUFFIXES | extract.PDF_SUFFIXES
    found = sorted(p.name for p in tmp_path.glob("**/*")
                   if p.is_file() and p.suffix.lower() in wanted)
    assert found == ["a.pdf", "b.html", "c.HTM"]
