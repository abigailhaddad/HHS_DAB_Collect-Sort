"""Text extraction. HHS publishes decisions as both HTML and PDF."""
import extract

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


SPLIT_NUMBER_HTML = """<html><body>
<table><tr><td>Docket No.C-99-733</td></tr>
<tr><td>Decision No. <strong>CR7</strong><b>38</b></td></tr></table>
<p>Petitioner <b>VITAS</b> Healthcare <i>Corporation</i> appealed.</p>
</body></html>"""


def test_inline_tags_do_not_split_a_number():
    # The 1999-2006 template renders "Decision No. CR738" as
    # "<strong>CR7</strong><b>38</b>". Replacing every tag with a space made
    # that "CR7 38", and eleven decisions parsed as CR7.
    import tempfile, pathlib
    f = pathlib.Path(tempfile.mkstemp(suffix=".html")[1])
    f.write_text(SPLIT_NUMBER_HTML, encoding="utf-8")
    text, _ = extract.extract_text(f)
    assert "CR738" in text
    assert "CR7 38" not in text


def test_block_tags_still_separate_their_contents():
    # ...but table cells must not run together into one word.
    import tempfile, pathlib
    f = pathlib.Path(tempfile.mkstemp(suffix=".html")[1])
    f.write_text(SPLIT_NUMBER_HTML, encoding="utf-8")
    text, _ = extract.extract_text(f)
    assert "C-99-733Decision" not in text
    # Inline emphasis inside a sentence must not lose its spaces either.
    assert "Petitioner VITAS Healthcare Corporation appealed." in " ".join(text.split())
