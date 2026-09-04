#!/usr/bin/env python3
"""
Convert a folder tree of DAB decision PDFs into JSONL, and emit a filtered
(b)(7) exclusion mini-dataset in the same pass.

Basic usage:
    python pdf_to_jsonl.py ./dab_pdfs -o dab.jsonl --b7-out dab_b7.jsonl

With OCR fallback for scanned/image-only PDFs (slower; needs the tesseract
binary + `pip install pymupdf pytesseract pillow`):
    python pdf_to_jsonl.py ./dab_pdfs --ocr

One JSON object per line, one line per PDF.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

# --- (b)(7) detection ---------------------------------------------------------
# Matches the exclusion authority in its common citation forms, tolerant of the
# stray whitespace/line breaks that PDF text extraction injects, e.g.
#   1128(b)(7) | section 1128 (b)(7) | 1320a-7(b)(7) | 42 U.S.C. 1320a-7(b)(7)
B7_RE = re.compile(
    r"(?:1320a[\s\-\u2010-\u2015]?7|1128)\s*\(\s*b\s*\)\s*\(\s*7\s*\)",
    re.IGNORECASE,
)
# Secondary signal: the exclusion-period reasonableness factors.
FACTORS_RE = re.compile(r"1001\.901", re.IGNORECASE)


def extract_text(pdf_path: Path) -> tuple[str, int]:
    """Return (text, num_pages) via the text layer. Raises on unreadable files."""
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


def normalize(text: str) -> str:
    """Collapse whitespace so citations split across lines still match."""
    return re.sub(r"\s+", " ", text)


def main() -> int:
    ap = argparse.ArgumentParser(description="DAB PDFs -> JSONL (+ b7 slice)")
    ap.add_argument("input_dir", type=Path, help="folder to search (recursive)")
    ap.add_argument("-o", "--out", type=Path, default=Path("dab.jsonl"),
                    help="full dataset output (default: dab.jsonl)")
    ap.add_argument("--b7-out", type=Path, default=Path("dab_b7.jsonl"),
                    help="(b)(7) slice output (default: dab_b7.jsonl)")
    ap.add_argument("--glob", default="**/*.pdf",
                    help="glob pattern under input_dir (default: **/*.pdf)")
    ap.add_argument("--ocr", action="store_true",
                    help="OCR any PDF whose text layer is under --min-chars")
    ap.add_argument("--min-chars", type=int, default=200,
                    help="text-layer threshold that triggers OCR (default: 200)")
    ap.add_argument("--ocr-dpi", type=int, default=300,
                    help="rasterization DPI for OCR (default: 300)")
    args = ap.parse_args()

    pdfs = sorted(args.input_dir.glob(args.glob))
    if not pdfs:
        print(f"No PDFs found under {args.input_dir} matching {args.glob}",
              file=sys.stderr)
        return 1

    total = b7 = failed = ocr_used = 0
    with args.out.open("w", encoding="utf-8") as fout, \
         args.b7_out.open("w", encoding="utf-8") as fb7:
        for pdf in pdfs:
            try:
                text, n_pages = extract_text(pdf)
            except Exception as e:  # keep going; log the casualty
                failed += 1
                print(f"[skip] {pdf}: {e}", file=sys.stderr)
                continue

            did_ocr = False
            if args.ocr and len(text.strip()) < args.min_chars:
                try:
                    ocr = ocr_text(pdf, dpi=args.ocr_dpi)
                    if len(ocr.strip()) > len(text.strip()):
                        text, did_ocr = ocr, True
                        ocr_used += 1
                except Exception as e:
                    print(f"[ocr-fail] {pdf}: {e}", file=sys.stderr)

            norm = normalize(text)
            n_b7 = len(B7_RE.findall(norm))
            rec = {
                "id": pdf.relative_to(args.input_dir).with_suffix("").as_posix(),
                "source_path": str(pdf),
                "text": text,
                "num_pages": n_pages,
                "num_chars": len(text),
                "is_b7": n_b7 > 0,
                "b7_matches": n_b7,
                "cites_1001_901": bool(FACTORS_RE.search(norm)),
                "ocr_used": did_ocr,
            }
            line = json.dumps(rec, ensure_ascii=False)
            fout.write(line + "\n")
            total += 1
            if rec["is_b7"]:
                fb7.write(line + "\n")
                b7 += 1

    print(f"Wrote {total} records to {args.out}", file=sys.stderr)
    print(f"  of which {b7} matched (b)(7) -> {args.b7_out}", file=sys.stderr)
    if ocr_used:
        print(f"  {ocr_used} PDF(s) recovered via OCR", file=sys.stderr)
    if failed:
        print(f"  {failed} PDF(s) failed extraction (logged above)",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
