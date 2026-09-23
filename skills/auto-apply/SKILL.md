---
name: auto-apply
description: Tailor Raghav's LaTeX resume to one internship posting and produce a one-page PDF plus its .tex source. Use whenever the user asks to tailor, optimize, or ATS-optimize their resume for a specific posting, or to run auto-apply on a posting. Builds on the job-description-assessor report. Produces a tailored resume only; it never submits applications.
---

# Auto-Apply

Tailors the resume to one posting, using the job-description-assessor report for that posting. You do the judgment work (selection, rewriting, auditing). `scripts/measure.py` only compiles the .tex and measures the PDF. This skill never submits an application.

**Inputs** (paths relative to the repo root):
- Base template: `base/Raghav_Senthil_Kumar_Resume.tex`
- Master resume: `master/Raghav_Senthil_Kumar_Master_Resume.tex`. Use the `.tex` file, not the PDF next to it.
- Shared preamble: `preamble.tex`. Both resumes pull it in with `\input{../preamble}`.
- Measurer: `skills/auto-apply/scripts/measure.py` (`scripts/measure.py` inside this skill's folder)

The template uses no `fontspec`, so the engine is `pdflatex`. measure.py detects this on its own.

## Precondition

- If this chat has no job-description-assessor report for this posting, run job-description-assessor first.
- Proceed only if the verdict is **Apply**. If it is **Review**, ask the user before proceeding. If it is **Skip**, stop and say why (quote the report's reason).
- From the report, take:
  - **Company name:** the Employer row of the Posting info table.
  - **Role title:** the Role row.
  - **Work location:** the Location row.
  - **Scored skill list:** every row of the Required and Preferred tables, with its Weight and Match type.
- Terms used below:
  - **High-weight skill:** weight ≥ 3 (every required skill; no preferred skill reaches 3).
  - **Matched:** match type exact, alias, allowed_alternative, or adjacent.
  - **Unmatched:** match type none, including rows marked `none ⚠ downgraded`.

## Sources

- The **base template** owns layout and the header: document class, `\input` of the preamble, header block, section and entry macros, spacing.
- The **master resume** owns all content. Nothing appears on the tailored resume that is not traceable to a specific master-resume entry. Education, entry headings (titles, links, dates), bullets, and skills all come from the master.
- Master bullets carry `% core | tags: ...` comments. Use them as selection hints, and leave them out of the output.
- The master's Certifications section is never used.

## Workflow

### 1. Select content

- Score each experience and project by the summed weight of the posting skills its master-resume bullets evidence. Count a skill once per entry, and count adjacent matches at half weight.
- **Experience** stays in reverse-chronological order. Drop an entry only if space forces it.
- **Projects** are ordered by relevance score, highest first, and cut from the bottom.
- Start the draft with every experience and project, and cut only after measure.py reports more than one page. If the page ends with visible room, bring back the next dropped project before adding words elsewhere.
- Within each entry, pick the 2 to 4 bullets that evidence the highest-weight skills. Prefer `core` bullets when scores tie.

### 2. Build the draft

- Start from a copy of the base template and pull in the selected content.
- Use exactly four sections, with these headers: `Education`, `Experience`, `Projects`, `Skills`. (The base template's `Technical Skills` becomes `Skills`.)
- Add `Phoenix, AZ $|$ ` to the start of the header's contact line only if the posting's work location is in Arizona. The company's headquarters and remote roles do not count. Otherwise the header shows no location.
- Education comes from the master unchanged, except that its Activities line must fit on one line. Drop the least relevant activities to make it fit, and never list one twice.
- Keep the base template's Skills layout: at most 4 category lines, each fitting on one line. measure.py only measures bullets, so check the Skills lines in the PDF's text (a wrapped line shows up as an extra line) and drop the lowest-weight skill from any line that wraps.

### 3. Rewrite bullets

- Use the tech-resume-optimizer skill for bullet craft. The rules in this file override it wherever they conflict (for example, never add a summary section).
- High-weight matched skills get the posting's exact phrasing, placed early in the bullet.
- Skills the assessor marked as unmatched are never inserted, anywhere on the page.
- The Skills section lists only master-resume skills, reordered by weight: posting-matched skills first, highest weight first, then other master skills relevant to the role.
- Single column, no tables, standard headers. Do not add sections, columns, icons, or graphics.
- Escape LaTeX special characters in all inserted text: `% & # _ $ { } ~ ^ \` (for example `C\#`, `R\&D`, `40\%`, `\$3.5K`).

### 4. Compile and measure

Run from the repo root:

```bash
python skills/auto-apply/scripts/measure.py <path.tex>
```

- It compiles twice in a temporary directory, copies the PDF next to the .tex, and prints JSON: `page_count`, `right_edge`, and `bullets[]` with `index`, `page`, `preview` (first 8 words), `line_count`, `last_line_fill_pct`, `pass`.
- Bullets are numbered in page order, so the two Education lines (Coursework, Activities) are bullets 1 and 2. Use `preview` to map each bullet back to its `\resumeItem` in the .tex.
- On a compile error it prints the LaTeX log lines and exits non-zero. Fix the .tex and rerun.
- If the TeX engine is missing, install it first: `apt-get install -y texlive-latex-extra`, plus `texlive-xetex` if the template uses fontspec. measure.py installs pdfplumber itself if needed.

### 5. Run the audit loop (below)

### 6. Write the output (below)

## Embellishment boundary

Allowed:
- stronger verbs;
- reordering what a bullet emphasizes;
- stating context the source clearly implies;
- swapping in the posting's term when the assessor marked the match as alias or allowed_alternative.

Not allowed:
- new or inflated numbers;
- scope upgrades (for example "contributed to" becoming "led");
- outcomes the master resume does not state;
- renaming adjacent matches (if Java was matched adjacent to C++, the resume still says C++).

Embellishment inside this boundary is encouraged.

## Line-fill rule

- The last line of every Experience and Projects bullet must be 90 to 100% full, as reported by measure.py.
- If the last line is under 50%, cut words so the bullet ends on the previous line.
- If it is 50% or more, add words to fill it (context, the posting's phrasing for a matched skill, a tool the master bullet names).
- The Education Coursework and Activities lines are fixed lists, so they are exempt from line fill. Fill cannot be reached there without inventing content.

## Audit loop

Run these pass/fail checks:

1. Exactly one page (`page_count == 1`).
2. Only the four sections: Education, Experience, Projects, Skills.
3. Every entry has 2 to 4 bullets.
4. Every Experience and Projects bullet's last line measures 90 to 100% (`pass: true`).
5. Every bullet traces to a specific master-resume entry, with no claims outside the embellishment boundary. Check every number, tool, and outcome against the master bullet it came from.
6. Every high-weight matched skill appears at least once on the page.
7. No verb is repeated within an entry, and tense is consistent: past tense for past roles, present tense for current ones. A role is current if its end date is "Present" or later than today.

Fix the failures, recompile, and re-check. Stop when all checks pass or after 3 iterations. If it stops at the cap, list the checks that still fail.

When rules conflict, this is the precedence:
1. Truthfulness
2. One page
3. Section and bullet counts
4. Line fill
5. Keyword density

## Output

```
Company_Name_Target_Role_Month_Year/
  Raghav_Senthil_Kumar_Target_Role_Resume.pdf
  Raghav_Senthil_Kumar_Target_Role_Resume.tex
```

- Target_Role is the role title from the report. Spaces become underscores, special characters are stripped, and repeated underscores collapse to one.
- Month_Year is the generation date with the month written in full (for example `Acme_Robotics_Software_Engineering_Intern_September_2026`, holding `Raghav_Senthil_Kumar_Software_Engineering_Intern_Resume.pdf`).
- Only these two files go in the directory. No aux or log files. measure.py already compiles elsewhere and copies only the PDF back.
- **In this repo:** create the directory under `tailored/`. The .tex sits two levels below the repo root, so its preamble line becomes `\input{../../preamble}`.
- **On claude.ai:** create the directory under `/mnt/user-data/outputs` and present both files. There is no shared preamble there, so paste the contents of `preamble.tex` in place of the `\input` line, which keeps the .tex self-contained.
- Draft in that same directory, overwriting the two files on each iteration, so the final PDF is the one measure.py last produced from the final .tex.

After presenting, give a short summary in chat:
- the audit results, one line per check (pass/fail), plus the iteration count;
- which experiences and projects were dropped for space;
- any high-weight skill left out because the master resume has no evidence for it.
