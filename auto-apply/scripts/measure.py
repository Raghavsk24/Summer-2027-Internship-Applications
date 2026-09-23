#!/usr/bin/env python3
"""Compile a LaTeX resume and measure its bullets.

Compiles in a temporary directory (aux/log files never touch the .tex's
folder), then reports page count and, for every bullet, how full its last
line is. Prints JSON to stdout and copies the PDF next to the .tex.

Usage:
    python scripts/measure.py <path.tex> [--engine pdflatex|xelatex] [--bullet-chars "•"]
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

LINE_TOLERANCE = 3.0   # pt; words whose vertical midpoints differ by less share a line
WORD_GAP = 1.5         # pt; TeX squeezes interword glue, so pdfplumber's default (3) fuses words
FILL_MIN, FILL_MAX = 90.0, 100.0
LOG_CONTEXT = 4        # log lines printed after each "!" error line
TEX_PT_TO_BP = 72 / 72.27  # TeX points -> PDF points

# Typed into the log at \begin{document}, after the preamble has set the
# margins, so measure.py knows where the text area ends on the page.
LAYOUT_PROBE = (
    r"\AtBeginDocument{"
    r"\typeout{MEASURE-TEXT-BOTTOM=\the\dimexpr 1in+\voffset+\topmargin"
    r"+\headheight+\headsep+\textheight\relax}"
    r"\typeout{MEASURE-LINE=\the\baselineskip}}"
)


def fail(msg, code=2):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def ensure_pdfplumber():
    try:
        import pdfplumber  # noqa: F401
    except ImportError:
        base = [sys.executable, "-m", "pip", "install", "--quiet", "pdfplumber"]
        # Older pip rejects --break-system-packages; retry without it.
        if subprocess.call(base + ["--break-system-packages"]) != 0 and subprocess.call(base) != 0:
            fail("could not install pdfplumber")
    import pdfplumber
    return pdfplumber


# ---------- compile ----------

def read_with_inputs(tex_path, seen=None):
    """Return the .tex source plus any \\input/\\include files it pulls in."""
    seen = seen if seen is not None else set()
    tex_path = tex_path.resolve()
    if tex_path in seen or not tex_path.is_file():
        return ""
    seen.add(tex_path)
    text = tex_path.read_text(encoding="utf-8", errors="replace")
    body = re.sub(r"(?<!\\)%.*", "", text)
    for name in re.findall(r"\\(?:input|include)\{([^}]+)\}", body):
        child = (tex_path.parent / name)
        if child.suffix != ".tex":
            child = child.with_name(child.name + ".tex")
        text += "\n" + read_with_inputs(child, seen)
    return text


def detect_engine(tex_path):
    source = re.sub(r"(?<!\\)%.*", "", read_with_inputs(tex_path))
    return "xelatex" if re.search(r"\\usepackage(\[[^\]]*\])?\{[^}]*\bfontspec\b", source) else "pdflatex"


def log_errors(log_path):
    if not log_path.is_file():
        return "(no log file produced)"
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    out = []
    for i, line in enumerate(lines):
        if line.startswith("!"):
            out.extend(lines[i:i + LOG_CONTEXT + 1])
            out.append("")
    return "\n".join(out) if out else "\n".join(lines[-30:])


def compile_pdf(tex_path, engine, workdir):
    if shutil.which(engine) is None:
        fail(f"{engine} not found on PATH. Install TeX first "
             "(apt-get install -y texlive-latex-extra, plus texlive-xetex for fontspec templates).")
    cmd = [engine, "-interaction=nonstopmode", "-halt-on-error",
           f"-output-directory={workdir}", f"-jobname={tex_path.stem}",
           LAYOUT_PROBE + r"\input{" + tex_path.name + "}"]
    # Run from the .tex's own folder so relative \input paths (../preamble) resolve.
    for _ in range(2):
        result = subprocess.run(cmd, cwd=tex_path.parent, capture_output=True,
                                text=True, errors="replace")
        if result.returncode != 0:
            print(log_errors(Path(workdir) / (tex_path.stem + ".log")), file=sys.stderr)
            fail(f"{engine} failed to compile {tex_path.name}", code=1)
    pdf = Path(workdir) / (tex_path.stem + ".pdf")
    if not pdf.is_file():
        fail(f"{engine} produced no PDF", code=1)
    return pdf, read_layout(Path(workdir) / (tex_path.stem + ".log"))


def read_layout(log_path):
    """Text-area bottom and line height (PDF points) from the probe's log lines."""
    log = log_path.read_text(encoding="utf-8", errors="replace")
    found = {}
    for key in ("TEXT-BOTTOM", "LINE"):
        m = re.search(rf"MEASURE-{key}=([\d.]+)pt", log)
        found[key] = float(m.group(1)) * TEX_PT_TO_BP if m else None
    return found["TEXT-BOTTOM"], found["LINE"]


# ---------- measure ----------

def group_lines(words):
    """Group words into lines by vertical position, top to bottom."""
    # Midpoints, not tops: the bullet glyph and "$" sit at different tops than
    # the text beside them but share its vertical center.
    mid = lambda w: (w["top"] + w["bottom"]) / 2
    lines = []
    for w in sorted(words, key=lambda w: (mid(w), w["x0"])):
        if lines and abs(mid(w) - lines[-1]["mid"]) <= LINE_TOLERANCE:
            lines[-1]["words"].append(w)
        else:
            lines.append({"mid": mid(w), "words": [w]})
    for line in lines:
        line["words"].sort(key=lambda w: w["x0"])
        line["x0"] = line["words"][0]["x0"]
        line["x1"] = max(w["x1"] for w in line["words"])
    return lines


def split_glyph(line, glyphs):
    """If the line holds a bullet glyph, return (text_left, words after glyph)."""
    for i, w in enumerate(line["words"]):
        if not w["text"] or w["text"][0] not in glyphs:
            continue
        rest = w["text"].lstrip(glyphs)
        if rest:  # glyph fused to the first word: use that word's first real char
            chars = [c for c in w.get("chars", []) if c["text"] not in glyphs and c["text"].strip()]
            left = chars[0]["x0"] if chars else w["x0"]
            return left, [dict(w, text=rest, x0=left)] + line["words"][i + 1:]
        after = line["words"][i + 1:]
        if after:
            return after[0]["x0"], after
    return None


def last_text_bottom(page):
    """Bottom of the lowest word on the page (the resume's last line)."""
    words = page.extract_words(x_tolerance=WORD_GAP)
    return max((w["bottom"] for w in words), default=None)


def find_bullets(pdf, glyphs):
    bullets = []
    for page_no, page in enumerate(pdf.pages, start=1):
        words = page.extract_words(x_tolerance=WORD_GAP, return_chars=True)
        current = None
        for line in group_lines(words):
            hit = split_glyph(line, glyphs)
            if hit:
                text_left, first_words = hit
                current = {"page": page_no, "text_left": text_left,
                           "lines": [{"x1": line["x1"], "words": first_words}]}
                bullets.append(current)
            elif current and line["x0"] >= current["text_left"] - 1.0:
                current["lines"].append({"x1": line["x1"], "words": line["words"]})
            else:
                current = None  # heading or section line ends the bullet
        # a bullet never continues across a page break
    return bullets


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tex", help="path to the .tex file")
    parser.add_argument("--engine", choices=["pdflatex", "xelatex"],
                        help="TeX engine (default: xelatex if fontspec is used, else pdflatex)")
    parser.add_argument("--bullet-chars", default="•",
                        help='characters that mark a bullet (default: "•")')
    args = parser.parse_args()

    tex_path = Path(args.tex).resolve()
    if not tex_path.is_file() or tex_path.suffix != ".tex":
        fail(f"not a .tex file: {args.tex}")
    engine = args.engine or detect_engine(tex_path)
    pdfplumber = ensure_pdfplumber()

    with tempfile.TemporaryDirectory() as workdir:
        pdf_path, (text_bottom, line_height) = compile_pdf(tex_path, engine, workdir)
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            bullets = find_bullets(pdf, args.bullet_chars)
            content_bottom = last_text_bottom(pdf.pages[-1])
        shutil.copyfile(pdf_path, tex_path.with_suffix(".pdf"))

    right_edge = max((l["x1"] for b in bullets for l in b["lines"]), default=None)
    report = []
    for i, b in enumerate(bullets, start=1):
        width = right_edge - b["text_left"]
        fill = (b["lines"][-1]["x1"] - b["text_left"]) / width * 100 if width > 0 else 0.0
        words = [w["text"] for l in b["lines"] for w in l["words"]]
        report.append({
            "index": i,
            "page": b["page"],
            "preview": " ".join(words[:8]),
            "line_count": len(b["lines"]),
            "last_line_fill_pct": round(fill, 1),
            "pass": FILL_MIN <= round(fill, 1) <= FILL_MAX,
        })

    # Gap between the last line and the bottom of the text area on the last page.
    # Under one line height the page is full: no further line can fit.
    gap = None
    if text_bottom is not None and content_bottom is not None:
        gap = text_bottom - content_bottom
    page_fill = {
        "text_area_bottom": None if text_bottom is None else round(text_bottom, 2),
        "content_bottom": None if content_bottom is None else round(content_bottom, 2),
        "bottom_gap_pt": None if gap is None else round(gap, 1),
        "line_height_pt": None if line_height is None else round(line_height, 1),
        "free_lines": None if gap is None or not line_height else round(gap / line_height, 1),
        "page_full": None if gap is None or not line_height else gap < line_height,
    }

    sys.stdout.reconfigure(encoding="utf-8")
    json.dump({
        "engine": engine,
        "page_count": page_count,
        "right_edge": None if right_edge is None else round(right_edge, 2),
        "page_fill": page_fill,
        "bullets": report,
    }, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
