#!/usr/bin/env python3
"""Score an internship posting against the master resume.

Reads skill-match JSON from stdin, verifies each evidence quote against the
resume, computes weighted fit, and prints the result as JSON to stdout.

Usage:
    echo '<json>' | python scripts/score.py --resume <path>
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

CREDIT = {
    "exact": 1.0,
    "alias": 1.0,
    "allowed_alternative": 1.0,
    "adjacent": 0.5,
    "none": 0.0,
}
ELIGIBILITY = {"eligible", "ineligible", "unknown"}
SECTIONS = {"required", "preferred"}
BINARY_EXTS = {".pdf", ".docx", ".doc"}

APPLY_AT = 65
REVIEW_AT = 45


def fail(msg):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


# ---------- normalization ----------

LATEX_ESCAPES = {r"\%": "\x00PCT", r"\$": "\x00DOL", r"\&": "\x00AMP",
                 r"\#": "\x00HSH", r"\_": "\x00USC", r"\{": "\x00LBR",
                 r"\}": "\x00RBR"}
RESTORE = {"\x00PCT": "%", "\x00DOL": "$", "\x00AMP": "&", "\x00HSH": "#",
           "\x00USC": "_", "\x00LBR": "{", "\x00RBR": "}"}
UNICODE_PUNCT = {"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
                 "\u2013": "-", "\u2014": "-", "\u00a0": " "}


def strip_latex(text, tex_source):
    text = re.sub(r"\\\\(\[[^\]]*\])?", " ", text)          # line breaks
    for esc, ph in LATEX_ESCAPES.items():
        text = text.replace(esc, ph)
    if tex_source:
        text = re.sub(r"%.*", "", text)                      # comments (only in .tex files)
    text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", "", text)   # commands + opt args
    text = text.replace("{", "").replace("}", "")
    text = text.replace("~", " ").replace("``", '"').replace("''", '"')
    for ph, ch in RESTORE.items():
        text = text.replace(ph, ch)
    return text


def strip_markdown(text):
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^\s*#+\s+", "", line)                # headings
        line = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", line)   # list markers
        lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)   # links/images
    text = text.replace("*", "").replace("`", "")
    text = re.sub(r"(?<!\w)_+|_+(?!\w)", "", text)           # _emphasis_
    return text


def normalize(text, tex_source=False):
    text = unicodedata.normalize("NFKC", text)
    for u, a in UNICODE_PUNCT.items():
        text = text.replace(u, a)
    text = strip_markdown(strip_latex(text, tex_source))
    # "$" is both a LaTeX math delimiter and a currency sign; drop it on both
    # sides so "$|$" and "\$3.5K" compare equal to plain "|" and "$3.5K".
    text = text.replace("$", "")
    text = re.sub(r"-{2,}", "-", text)
    return re.sub(r"\s+", " ", text).strip().lower()


# ---------- input ----------

def load_resume(path_str):
    path = Path(path_str)
    if path.suffix.lower() in BINARY_EXTS:
        fail(f"resume '{path}' is a {path.suffix} file. Provide a text-based "
             "version (.tex, .md, or .txt); binary formats are not supported.")
    if not path.is_file():
        fail(f"resume not found: {path}")
    text = path.read_text(encoding="utf-8", errors="replace")
    return normalize(text, tex_source=path.suffix.lower() == ".tex")


def load_input():
    raw = sys.stdin.buffer.read().decode("utf-8-sig")
    if not raw.strip():
        fail("no JSON received on stdin")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        fail(f"invalid JSON on stdin: {e}")
    if data.get("eligibility") not in ELIGIBILITY:
        fail(f"'eligibility' must be one of {sorted(ELIGIBILITY)}")
    skills = data.get("skills", [])
    if not isinstance(skills, list):
        fail("'skills' must be a list")
    for i, s in enumerate(skills):
        if not isinstance(s, dict) or not s.get("name"):
            fail(f"skills[{i}] must be an object with a 'name'")
        if s.get("section") not in SECTIONS:
            fail(f"skills[{i}] ({s['name']}): 'section' must be one of {sorted(SECTIONS)}")
        if s.get("match_type") not in CREDIT:
            fail(f"skills[{i}] ({s['name']}): 'match_type' must be one of {sorted(CREDIT)}")
    return data["eligibility"], skills


# ---------- scoring ----------

def weight(skill):
    base = 3.0 if skill["section"] == "required" else 1.0
    boost = 1.5 if skill.get("emphasized") or skill.get("in_title_or_first_resp") else 1.0
    try:
        mentions = int(skill.get("mentions") or 1)
    except (TypeError, ValueError):
        mentions = 1
    freq = min(1 + 0.1 * (max(mentions, 1) - 1), 1.3)
    return base * boost * freq


def score_skill(skill, resume):
    evidence = skill.get("evidence")
    norm_ev = normalize(evidence) if isinstance(evidence, str) else ""
    verified = bool(norm_ev) and norm_ev in resume
    match_type = skill["match_type"]
    downgraded = match_type != "none" and not verified
    if downgraded:
        match_type = "none"
    return {
        "name": skill["name"],
        "section": skill["section"],
        "weight": round(weight(skill), 3),
        "match_type": match_type,
        "credit": CREDIT[match_type],
        "evidence_verified": verified,
        "downgraded": downgraded,
    }


def section_score(results, section):
    rows = [r for r in results if r["section"] == section]
    if not rows:
        return None
    total = sum(r["weight"] for r in rows)
    return sum(r["weight"] * r["credit"] for r in rows) / total


def verdict_for(eligibility, has_required, fit_percent):
    if eligibility == "ineligible":
        return "Skip", "ineligible"
    if not has_required:
        return "Review", "no_required_skills"
    if eligibility == "unknown":
        return "Review", "eligibility_unknown"
    if fit_percent >= APPLY_AT:
        return "Apply", "fit_at_or_above_65"
    if fit_percent >= REVIEW_AT:
        return "Review", "fit_45_to_64"
    return "Skip", "fit_below_45"


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--resume", required=True, help="path to text-based master resume")
    args = parser.parse_args()

    resume = load_resume(args.resume)
    eligibility, skills = load_input()
    results = [score_skill(s, resume) for s in skills]

    R = section_score(results, "required")
    P = section_score(results, "preferred")
    if eligibility == "ineligible":
        fit = 0.0
    elif R is None:
        fit = P or 0.0
    elif P is None:
        fit = R
    else:
        fit = 0.75 * R + 0.25 * P
    fit_percent = int(fit * 100 + 0.5)  # round half up, not banker's rounding
    verdict, reason = verdict_for(eligibility, R is not None, fit_percent)

    out = {
        "fit_percent": fit_percent,
        "R": None if R is None else round(R, 4),
        "P": None if P is None else round(P, 4),
        "verdict": verdict,
        "verdict_reason_code": reason,
        "skills": results,
    }
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
