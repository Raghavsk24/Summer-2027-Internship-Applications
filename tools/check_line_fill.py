#!/usr/bin/env python3
"""Report how full the LAST line of every resume bullet is (house rule: 90-100%).

Usage, from the repo root:
    python tools/check_line_fill.py <resume.pdf> [heading-substring ...]

Compile to a scratch folder first so no build files land in the repo:
    cd <folder containing the .tex>
    pdflatex -interaction=nonstopmode -output-directory=<scratch> <file>.tex

Pass one or more heading substrings (e.g. clusion truck) to check only the bullets
under matching entries. Exit code is 1 if any bullet falls outside the range.

The right edge defaults to 576 pt (8.5 in page minus the 0.5 in margin set in
shared/preamble.tex). Change it with --right if the margins ever change.
Requires: pip install pdfplumber
"""
import argparse
import sys
from collections import Counter

import pdfplumber

BULLET = "•"


def read_lines(pdf):
    rows = []
    for page_no, page in enumerate(pdf.pages):
        for ln in page.extract_text_lines():
            rows.append({
                "page": page_no,
                "x0": ln["x0"],
                "x1": ln["x1"],
                "top": ln["top"],
                "text": ln["text"],
                "chars": ln["chars"],
            })
    return rows


def bullet_text_left(row):
    """x of the first visible character after the bullet glyph."""
    chars = row["chars"]
    for i, ch in enumerate(chars):
        if ch["text"] == BULLET:
            for nxt in chars[i + 1:]:
                if nxt["text"].strip():
                    return nxt["x0"]
    return None


def group_bullets(rows, gap=16.0):
    lefts = [bullet_text_left(r) for r in rows if r["text"].startswith(BULLET)]
    lefts = [round(x) for x in lefts if x is not None]
    if not lefts:
        return [], None
    text_left = Counter(lefts).most_common(1)[0][0]

    groups, heading, cur, prev = [], "", None, None
    for r in rows:
        if r["text"].startswith(BULLET):
            cur = {"heading": heading, "lines": [r]}
            groups.append(cur)
        elif (cur and prev and r["page"] == prev["page"]
              and abs(r["x0"] - text_left) <= 3 and 0 < r["top"] - prev["top"] <= gap):
            cur["lines"].append(r)
        else:
            cur = None
            if r["x0"] < text_left - 3:
                heading = r["text"]
        prev = r
    return groups, text_left


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("headings", nargs="*", help="only bullets under entries whose heading contains one of these")
    ap.add_argument("--min", type=float, default=90.0, dest="lo")
    ap.add_argument("--max", type=float, default=100.0, dest="hi")
    ap.add_argument("--right", type=float, default=576.0, help="right text edge in pt (default 576)")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    with pdfplumber.open(args.pdf) as pdf:
        groups, text_left = group_bullets(read_lines(pdf))
    if text_left is None:
        print("No bullets found.")
        return 1

    width = args.right - text_left
    print(f"text-left {text_left} pt, right edge {args.right:.0f} pt, width {width:.0f} pt, target {args.lo:.0f}-{args.hi:.0f}%\n")
    checked = bad = 0
    for g in groups:
        if args.headings and not any(h.lower() in g["heading"].lower() for h in args.headings):
            continue
        last = g["lines"][-1]
        fill = (last["x1"] - text_left) / width * 100
        checked += 1
        if fill < args.lo:
            flag = "SHORT"
        elif fill > args.hi + 0.5:
            flag = "OVER"
        else:
            flag = "ok"
        if flag != "ok":
            bad += 1
        n = len(g["lines"])
        tail = last["text"][-50:]
        print(f"{fill:6.1f}%  {flag:5s} {n} line{'s' if n > 1 else ' '}  [{g['heading'][:22]}] ...{tail}")
    print(f"\n{checked} bullets checked, {bad} outside {args.lo:.0f}-{args.hi:.0f}%")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
