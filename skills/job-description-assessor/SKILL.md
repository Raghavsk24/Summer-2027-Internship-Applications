---
name: job-description-assessor
description: Assess an internship posting against Raghav's master resume, covering eligibility, weighted skill fit, and an Apply / Review / Skip verdict. Use whenever the user shares an internship posting (URL, pasted text, or file) and asks whether they should apply, whether they are a match, or to assess or score it.
---

# Job Description Assessor

Decides whether Raghav is eligible for an internship posting, scores fit against the master resume, and gives a verdict of **Apply**, **Review**, or **Skip**. You do the judgment work (eligibility, skill extraction, matching). `scripts/score.py` only verifies evidence and does the arithmetic.

**Inputs** (paths relative to the repo root):
- Candidate facts: `.claude/skills/job-description-assessor/candidate.md`
- Master resume: `master/Raghav_Senthil_Kumar_Master_Resume.tex`. Use the `.tex` file, not the PDF next to it.
- Scorer: `.claude/skills/job-description-assessor/scripts/score.py`

## Output rules

- Render the report as markdown in the chat response. Never create or save report files.
- Pass data to score.py through stdin: `echo '<json>' | python scripts/score.py --resume <path>`. Never write intermediate JSON files.
  - Run it with the Bash tool from the repo root:
    `echo '<json>' | python .claude/skills/job-description-assessor/scripts/score.py --resume master/Raghav_Senthil_Kumar_Master_Resume.tex`
  - If the JSON contains a single quote (`'`), write it as `'\''` inside the echo, or pipe it through a quoted heredoc (`python ... <<'EOF'` … `EOF`), which is still stdin.
  - Escape backslashes inside JSON strings (`\\`).

## Workflow

1. Read the posting, candidate.md, and the master resume. For a URL, fetch the page. For a file, read it. Note the posting date if one is shown.
2. Run the eligibility check (rules below). If any rule returns ineligible, render the report with fit 0%, verdict Skip, and the quoted clause, then stop.
3. Extract technical skills from the required and preferred sections. For each, record: section, whether it is emphasized ("strong", "must", "proficient", "expert"), whether it appears in the role title or first responsibility, and mention count including synonyms.
   - Sections headed "Basic", "Minimum", or "Must have" are **required**. Sections headed "Preferred", "Bonus", "Nice to have", or "Plus" are **preferred**. If the posting has no split, treat every listed qualification as required.
   - Extract technical skills only (languages, frameworks, tools, platforms, technical concepts). Skip soft skills, degree requirements, and eligibility items.
   - Count mentions across the whole posting, including synonyms (for example "ML" and "machine learning" count as one skill).
4. Match each skill to the master resume, assign a match type, and quote the resume text verbatim as evidence.
5. Send everything to score.py via stdin.
6. Render the report from the script's output. Use the script's fit_percent, verdict, weights, and final match types exactly as returned. Never override them.

## Eligibility rules

Each rule returns eligible, ineligible, or unknown. "Ineligible" requires a verbatim quote from the posting. Any "unknown" forces the verdict to Review. If nothing is stated, the result is eligible.

1. **Term:** must be Summer 2027. A summer role with no year that was posted fall 2026 or later counts as 2027. "Summer or Fall 2027" passes. Only an explicit different term fails.
2. **Citizenship:** only "US citizen required" (or equivalent) fails. "US person" and "authorized to work in the US without sponsorship" pass for a permanent resident.
3. **Clearance:** "must hold or be able to obtain a security clearance" fails. Vague mentions of cleared work are unknown.
4. **Class standing:** wording keyed to graduation year or grade cohort ("rising juniors", "Class of 2029") defers to rule 5. Wording keyed to time enrolled ("completed two years of study") is checked against one year completed. Bare "juniors and seniors" with no other context is unknown.
5. **Graduation window:** the posting's range must include May 2029. This is the primary test for standing.
6. **Program restrictions:** only an explicit eligibility restriction to a group I'm not in fails (demographic, specific schools, first-gen, veterans, membership requirements). Ignore EEO "we encourage X to apply" language.
7. **GPA minimum:** unknown, since I have no college GPA yet.

Overall eligibility sent to the script: `ineligible` if any rule is ineligible, else `unknown` if any rule is unknown, else `eligible`.

## Match types

| Type | Example | Credit |
|---|---|---|
| exact | Python / Python | 1.0 |
| alias | Postgres / PostgreSQL | 1.0 |
| allowed_alternative (posting explicitly permits substitutes) | "Java or similar OOP language" / C++ | 1.0 |
| adjacent (related skill, posting does not permit substitutes) | "Java" / C++ | 0.5 |
| none | | 0 |

Evidence must be copied verbatim from the resume. Never paraphrase it.

- Quote one contiguous span of resume text, preferably the most specific one (a bullet over a skills-list entry). Quote the text as it reads on the page, leaving out LaTeX markup (`\emph{...}` → `...`, `\&` → `&`, `\%` → `%`, `$|$` → `|`). The script strips markup on both sides, and plain text avoids backslash escaping in the shell. Do not change, reorder, or abbreviate any words, numbers, or punctuation.
- For `none`, set evidence to `null`.
- The script substring-matches each quote against the resume. If a quote is not found, the script downgrades that skill to `none`.

## Script contract

stdin:
```json
{
  "eligibility": "eligible | ineligible | unknown",
  "skills": [
    {
      "name": "string",
      "section": "required | preferred",
      "emphasized": true,
      "in_title_or_first_resp": false,
      "mentions": 1,
      "match_type": "exact | alias | allowed_alternative | adjacent | none",
      "evidence": "verbatim resume text or null"
    }
  ]
}
```

stdout: `fit_percent`, `R`, `P`, `verdict`, `verdict_reason_code`, and `skills[]` with `name`, `section`, `weight`, `match_type` (final), `credit`, `evidence_verified`, `downgraded`.

Weights: `base (3 required / 1 preferred) × boost (1.5 if emphasized or in title/first responsibility) × freq (1 + 0.1 per extra mention, capped at 1.3)`. Fit = `0.75·R + 0.25·P` (or `R` alone if there are no preferred skills). Thresholds: ≥65% Apply, 45–64% Review, <45% Skip. Eligibility unknown or no required skills means Review.

If the script exits with an error (bad JSON, missing resume, binary resume), fix the input and rerun. Never hand-compute a score.

## Report template

**1. Posting info**

| Field | Value |
|---|---|
| Employer | … |
| Role | … |
| Location | … |
| Pay | … |
| Date posted | … |
| Company size | … (external) |

Any field not in the posting reads "Not listed". Company size comes from a web lookup and is marked "(external)".

**2. Score and verdict:** fit %, verdict, and a one-sentence reason. For ineligible postings show 0%, Skip, and the quoted clause, and render nothing further.

- For eligibility `unknown`, the reason names the rule(s) that came back unknown (for example "GPA minimum stated; no college GPA yet").
- Format: **Fit: 72% · Verdict: Apply**, then the reason sentence.

**3. Requirements breakdown:** two tables (Required, Preferred) with columns Skill | Weight | Match | Resume evidence. List unmatched skills last in each table. Flag any skill the script downgraded for failed evidence.

- Sort matched skills by weight, highest first, and put `none` rows last.
- Match column shows the final match type from the script. For downgraded skills, write `none ⚠ downgraded (evidence not found)`.
- The evidence column shows the verbatim quote in quotes, or "—" for none.
- If a section has no skills, write "No preferred skills listed." (or "required") instead of a table.
