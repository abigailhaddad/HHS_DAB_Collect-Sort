#!/usr/bin/env python3
"""Convert a folder tree of DAB/ALJ decision PDFs into one JSONL per corpus.

    python pdf_to_jsonl.py ./dab_pdfs -o dab.jsonl
    python pdf_to_jsonl.py ./dab_pdfs -o dab.jsonl --ocr   # needs tesseract

One JSON object per line, one line per PDF. Categorisation is not done here --
that is slice_jsonl.py's job, driven by categories.py. Emitting a (b)(7) slice
from inside the extractor meant one category was privileged over the fifteen
others and its label was computed by different code than theirs.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

# A decision page is dense prose. Well under this and the text layer is a
# scanning artefact -- page furniture, a few stray words -- even though it
# clears any absolute character count a long document would pass.
MIN_CHARS_PER_PAGE = 400
# Runs of letters with no vowel are what a failed text layer looks like once
# it is decoded: "t:rsotee's", "Financisl", "~lich". Real legal prose sits near
# 1%; the worst scans in this corpus reach 7%.
MAX_NO_VOWEL_RATE = 0.04


def extract_text(pdf_path: Path) -> tuple[str, int]:
    reader = PdfReader(str(pdf_path))
    pages = [(p.extract_text() or "") for p in reader.pages]
    return "\n".join(pages), len(reader.pages)


def ocr_text(pdf_path: Path, dpi: int = 300) -> str:
    """Rasterize each page and OCR it. Imports are local so the tool runs
    without the OCR stack unless --ocr is actually used."""
    import io

    import pymupdf              # rasterizer (no system poppler needed)
    import pytesseract          # wraps the tesseract binary
    from PIL import Image

    out = []
    with pymupdf.open(str(pdf_path)) as doc:
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            out.append(pytesseract.image_to_string(img))
    return "\n".join(out)


def no_vowel_rate(text: str) -> float:
    words = re.findall(r"[A-Za-z]{3,}", text)
    if not words:
        return 1.0
    return sum(1 for w in words if not re.search(r"[aeiouyAEIOUY]", w)) / len(words)


def text_quality(text: str, n_pages: int) -> tuple[bool, str]:
    """Is this text layer usable? Returns (ok, reason-if-not).

    An absolute character floor only catches PDFs with *no* text layer. It does
    not catch the 1980s scans in this corpus, whose layers are present, long,
    and garbled -- those cleared a 200-character threshold and were never
    re-OCR'd, so they shipped as-is.
    """
    stripped = text.strip()
    if not stripped:
        return False, "empty text layer"
    if n_pages and len(stripped) / n_pages < MIN_CHARS_PER_PAGE:
        return False, f"{len(stripped) // max(n_pages, 1)} chars/page"
    rate = no_vowel_rate(stripped)
    if rate > MAX_NO_VOWEL_RATE:
        return False, f"{rate:.1%} of words have no vowel"
    return True, ""


def main() -> int:
    ap = argparse.ArgumentParser(description="decision PDFs -> corpus JSONL")
    ap.add_argument("input_dir", type=Path, help="folder to search (recursive)")
    ap.add_argument("-o", "--out", type=Path, default=Path("dab.jsonl"))
    ap.add_argument("--glob", default="**/*.pdf")
    ap.add_argument("--ocr", action="store_true",
                    help="re-OCR any PDF whose text layer fails the quality test")
    ap.add_argument("--ocr-dpi", type=int, default=300)
    args = ap.parse_args()

    pdfs = sorted(args.input_dir.glob(args.glob))
    if not pdfs:
        print(f"No PDFs under {args.input_dir} matching {args.glob}", file=sys.stderr)
        return 1

    total = failed = ocr_used = poor = 0
    with args.out.open("w", encoding="utf-8") as fout:
        for pdf in pdfs:
            try:
                text, n_pages = extract_text(pdf)
            except Exception as e:                  # keep going; log the casualty
                failed += 1
                print(f"[skip] {pdf}: {e}", file=sys.stderr)
                continue

            ok, reason = text_quality(text, n_pages)
            did_ocr = False
            if not ok:
                poor += 1
                if args.ocr:
                    try:
                        ocr = ocr_text(pdf, dpi=args.ocr_dpi)
                        # Only take the OCR if it is actually better.
                        if text_quality(ocr, n_pages)[0] or len(ocr.strip()) > len(text.strip()):
                            text, did_ocr = ocr, True
                            ocr_used += 1
                    except Exception as e:
                        print(f"[ocr-fail] {pdf}: {e}", file=sys.stderr)
                else:
                    print(f"[poor text] {pdf}: {reason}", file=sys.stderr)

            # The id is the path under input_dir; the absolute path is not
            # recorded, because it is the operator's local directory layout and
            # means nothing to anyone downloading the dataset.
            fout.write(json.dumps({
                "id": pdf.relative_to(args.input_dir).with_suffix("").as_posix(),
                "text": text,
                "num_pages": n_pages,
                "num_chars": len(text),
                "ocr_used": did_ocr,
                "text_layer_ok": ok or did_ocr,
            }, ensure_ascii=False) + "\n")
            total += 1

    print(f"Wrote {total} records to {args.out}", file=sys.stderr)
    print(f"  {poor} had a poor text layer" + (f", {ocr_used} recovered by OCR"
          if args.ocr else " (re-run with --ocr to recover them)"), file=sys.stderr)
    if failed:
        print(f"  {failed} failed extraction (logged above)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
