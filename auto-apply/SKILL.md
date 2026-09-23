---
name: auto-apply
description: End-to-end internship pipeline for Raghav. Given a URL (a careers page, a job-search results page, or a single posting), it collects the internship postings, checks eligibility and scores each one against the master resume (Apply / Review / Skip), tailors a one-page LaTeX resume (PDF + .tex) for every posting worth applying to, logs them in applications.csv, and commits and pushes the results to the repo. Use whenever the user shares a job URL or posting and asks to run auto-apply, find which jobs are worth applying to, assess or score a posting, or tailor / ATS-optimize the resume for it. It never submits applications.
---

# Auto-Apply

Pipeline: **URL → collect postings → assess each → tailor resumes for the ones worth applying to → update the repo → report.**

You do the judgment work (eligibility, skill matching, content selection, rewriting, auditing). The scripts do only mechanical work: `scripts/score.py` verifies evidence and computes fit; `scripts/measure.py` compiles LaTeX and measures the PDF. This skill never submits an application.

**Inputs** (paths relative to the repo root):
- Candidate facts: `skills/auto-apply/candidate.md`
- Master resume: `master/Raghav_Senthil_Kumar_Master_Resume.tex`. Use the `.tex` file, not the PDF next to it.
- Base template: `base/Raghav_Senthil_Kumar_Resume.tex`
- Shared preamble: `preamble.tex`. Both resumes pull it in with `\input{../preamble}`.
- Tracker: `applications.csv`
- Scorer: `skills/auto-apply/scripts/score.py`
- Measurer: `skills/auto-apply/scripts/measure.py`

The template uses no `fontspec`, so the engine is `pdflatex`. measure.py detects this on its own.

---

## Phase 1: Collect postings

1. Fetch the URL. If the fetched text has no job titles (common on JavaScript-rendered career sites such as Workday), open it in the browser and read the page text instead.
2. Decide whether the URL is a **single posting** or a **listing**.
   - **Single posting:** that posting is the only candidate.
   - **Listing:** go through every page of results (pagination, "Load more", infinite scroll) and collect each posting's title, URL, location, and job ID. Then open each posting to read its full description.
3. Screen out, without a full assessment, and record the reason for the final report:
   - **Not an internship:** full-time, new-grad, or experienced roles.
   - **Clearly non-technical:** for example HR, marketing, sales, legal, or finance internships with no technical skills.
   - **Already tracked:** `applications.csv` already has a row with the same company and job ID, or the same company and role when there is no job ID.
4. If more than 20 postings remain, show the list and ask the user whether to assess all of them or a subset before continuing.

## Phase 2: Assess each posting

For every remaining posting, run the steps below. Keep each posting's results (posting info, eligibility, score.py output) for Phases 3 to 6.

1. Read the posting, candidate.md, and the master resume. Note the posting date if one is shown.
2. Run the eligibility check (rules below). If any rule returns ineligible, the posting gets fit 0% and verdict Skip, with the quoted clause. Do not score it.
3. Extract technical skills from the required and preferred sections. For each, record: section, whether it is emphasized ("strong", "must", "proficient", "expert"), whether it appears in the role title or first responsibility, and mention count including synonyms.
   - Sections headed "Basic", "Minimum", or "Must have" are **required**. Sections headed "Preferred", "Bonus", "Nice to have", or "Plus" are **preferred**. If the posting has no split, treat every listed qualification as required.
   - Extract technical skills only (languages, frameworks, tools, platforms, technical concepts). Skip soft skills, degree requirements, and eligibility items.
   - Count mentions across the whole posting, including synonyms (for example "ML" and "machine learning" count as one skill).
4. Match each skill to the master resume, assign a match type, and quote the resume text verbatim as evidence.
5. Send everything to score.py via stdin (contract below). Use its fit_percent, verdict, weights, and final match types exactly as returned. Never override them and never hand-compute a score.

### Eligibility rules

Each rule returns eligible, ineligible, or unknown. "Ineligible" requires a verbatim quote from the posting. Any "unknown" forces the verdict to Review. If nothing is stated, the result is eligible.

1. **Term:** must be Summer 2027. A summer role with no year that was posted fall 2026 or later counts as 2027. "Summer or Fall 2027" passes. Only an explicit different term fails.
2. **Citizenship:** only "US citizen required" (or equivalent) fails. "US person" and "authorized to work in the US without sponsorship" pass for a permanent resident.
3. **Clearance:** "must hold or be able to obtain a security clearance" fails. Vague mentions of cleared work are unknown.
4. **Class standing:** wording keyed to graduation year or grade cohort ("rising juniors", "Class of 2029") defers to rule 5. Wording keyed to time enrolled ("completed two years of study") is checked against one year completed. Bare "juniors and seniors" with no other context is unknown.
5. **Graduation window:** the posting's range must include May 2029. This is the primary test for standing.
6. **Program restrictions:** only an explicit eligibility restriction to a group Raghav is not in fails (demographic, specific schools, first-gen, veterans, membership requirements). Ignore EEO "we encourage X to apply" language.
7. **GPA minimum:** unknown, since there is no college GPA yet.

Overall eligibility sent to the script: `ineligible` if any rule is ineligible, else `unknown` if any rule is unknown, else `eligible`.

### Match types

| Type | Example | Credit |
|---|---|---|
| exact | Python / Python | 1.0 |
| alias | Postgres / PostgreSQL | 1.0 |
| allowed_alternative (posting explicitly permits substitutes) | "Java or similar OOP language" / C++ | 1.0 |
| adjacent (related skill, posting does not permit substitutes) | "Java" / C++ | 0.5 |
| none | | 0 |

Evidence must be copied verbatim from the master resume. Never paraphrase it.

- Quote one contiguous span of resume text, preferably the most specific one (a bullet over a skills-list entry). Quote the text as it reads on the page, leaving out LaTeX markup (`\emph{...}` → `...`, `\&` → `&`, `\%` → `%`, `$|$` → `|`). Do not change, reorder, or abbreviate any words, numbers, or punctuation.
- For `none`, set evidence to `null`.
- The script substring-matches each quote against the resume. If a quote is not found, it downgrades that skill to `none`.

### score.py contract

Pass the JSON through stdin; never write intermediate JSON files. From the repo root:

```bash
python skills/auto-apply/scripts/score.py --resume master/Raghav_Senthil_Kumar_Master_Resume.tex <<'EOF'
{ ...json... }
EOF
```

The quoted heredoc avoids shell-escaping problems with `'` in the JSON. Escape backslashes inside JSON strings (`\\`).

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

If the script exits with an error (bad JSON, missing resume), fix the input and rerun.

## Phase 3: Decide

- **Apply:** tailor a resume (Phase 4).
- **Review:** after every posting has been assessed, ask the user once, in a single question listing each Review posting with its fit and reason, which ones to tailor. Tailor only the ones they pick.
- **Skip:** no resume. Record the reason (the quoted clause for ineligible postings).

If no posting ends up selected, skip Phases 4 and 5 and go straight to the report.

## Phase 4: Tailor a resume (each selected posting)

From the posting's assessment, take the company name, role title, work location, and the scored skill list (weights and final match types). Terms:
- **High-weight skill:** weight ≥ 3 (every required skill; no preferred skill reaches 3).
- **Matched:** match type exact, alias, allowed_alternative, or adjacent.
- **Unmatched:** final match type none, including downgraded skills.

### Sources

- The **base template** owns layout and the header: document class, `\input` of the preamble, header block, section and entry macros, spacing.
- The **master resume** owns all content. Nothing appears on the tailored resume that is not traceable to a specific master-resume entry. Education, entry headings (titles, links, dates), bullets, and skills all come from the master.
- Master bullets carry `% core | tags: ...` comments. Use them as selection hints, and leave them out of the output.
- The master's Certifications section is never used.

### 4.1 Select content

- Score each experience and project by the summed weight of the posting skills its master-resume bullets evidence. Count a skill once per entry, and count adjacent matches at half weight.
- **Experience** stays in reverse-chronological order. Drop an entry only if space forces it.
- **Projects** are ordered by relevance score, highest first, and cut from the bottom.
- Start the draft with every experience and project, and cut only after measure.py reports more than one page. The page must also end full (see Page-fill rule), so never cut more than the overflow requires.
- Within each entry, pick the 2 to 4 bullets that evidence the highest-weight skills. Prefer `core` bullets when scores tie.

### 4.2 Build the draft

- Start from a copy of the base template and pull in the selected content.
- Use exactly four sections, with these headers: `Education`, `Experience`, `Projects`, `Skills`. (The base template's `Technical Skills` becomes `Skills`.)
- Add `Phoenix, AZ $|$ ` to the start of the header's contact line only if the posting's work location is in Arizona. The company's headquarters and remote roles do not count. Otherwise the header shows no location.
- Education comes from the master unchanged, except that its Activities line must fit on one line. Drop the least relevant activities to make it fit, and never list one twice.
- Keep the base template's Skills layout: 4 category lines (up to 6 when the Page-fill rule needs them), each fitting on one line. measure.py only measures bullets, so check the Skills lines in the PDF's text (a wrapped line shows up as an extra line) and drop the lowest-weight skill from any line that wraps.

### 4.3 Rewrite bullets

- Use the tech-resume-optimizer skill for bullet craft. The rules in this file override it wherever they conflict (for example, never add a summary section).
- High-weight matched skills get the posting's exact phrasing, placed early in the bullet.
- Skills marked unmatched are never inserted, anywhere on the page.
- The Skills section lists only master-resume skills, reordered by weight: posting-matched skills first, highest weight first, then other master skills relevant to the role.
- Single column, no tables, standard headers. Do not add sections, columns, icons, or graphics.
- Escape LaTeX special characters in all inserted text: `% & # _ $ { } ~ ^ \` (for example `C\#`, `R\&D`, `40\%`, `\$3.5K`).

### 4.4 Compile and measure

```bash
python skills/auto-apply/scripts/measure.py <path.tex>
```

- It compiles twice in a temporary directory, copies the PDF next to the .tex, and prints JSON: `page_count`, `right_edge`, `page_fill`, and `bullets[]` with `index`, `page`, `preview` (first 8 words), `line_count`, `last_line_fill_pct`, `pass`.
- `page_fill` reports the gap between the last line and the bottom of the text area: `bottom_gap_pt`, `line_height_pt`, `free_lines` (gap ÷ line height), and `page_full` (true when the gap is less than one line, so no further line fits).
- Bullets are numbered in page order, so the two Education lines (Coursework, Activities) are bullets 1 and 2. Use `preview` to map each bullet back to its `\resumeItem` in the .tex.
- On a compile error it prints the LaTeX log lines and exits non-zero. Fix the .tex and rerun.
- If the TeX engine is missing, install it first: `apt-get install -y texlive-latex-extra`, plus `texlive-xetex` if the template uses fontspec. measure.py installs pdfplumber itself if needed.

### 4.5 Run the audit loop (below), then write the output (Phase 5)

### Embellishment boundary

Allowed:
- stronger verbs;
- reordering what a bullet emphasizes;
- stating context the source clearly implies;
- swapping in the posting's term when the match is alias or allowed_alternative.

Not allowed:
- new or inflated numbers;
- scope upgrades (for example "contributed to" becoming "led");
- outcomes the master resume does not state;
- renaming adjacent matches (if Java was matched adjacent to C++, the resume still says C++).

Embellishment inside this boundary is encouraged.

### Line-fill rule

- The last line of every Experience and Projects bullet must be 90 to 100% full, as reported by measure.py.
- If the last line is under 50%, cut words so the bullet ends on the previous line.
- If it is 50% or more, add words to fill it (context, the posting's phrasing for a matched skill, a tool the master bullet names).
- The Education Coursework and Activities lines are fixed lists, so they are exempt from line fill. Fill cannot be reached there without inventing content.

### Page-fill rule

The resume always runs the full length of the page: the last line sits less than one line height above the bottom margin (`page_fill.page_full: true`). Never fill space by changing margins, font size, or vertical spacing, because the base template owns layout. Fill it with content.

When `free_lines` is 1 or more, add lines in this order until the page is full, re-measuring after each change:
1. **Restore a dropped project,** the next one by relevance, with 2 bullets. This costs about 4 lines (heading, spacing, bullets), so use it when `free_lines` is 4 or more.
2. **Add an unused master bullet** to an entry that has fewer than 4, taking the bullet that evidences the highest-weight posting skill first. Each one-line bullet costs about 1.1 lines. Bring its wording to 90–100% line fill as usual.
3. **Grow a one-line bullet into two full lines** using detail its master bullet states or clearly implies (for example, restoring words trimmed earlier). This costs exactly 1 line and is the right move when `free_lines` is between 1 and 1.1.
4. **Add a Skills category line** built from a master Skills category not yet shown (for example Data & Analytics), up to 6 lines in total.

Every added line follows the same rules as the rest of the page: traceable to the master, inside the embellishment boundary, 90–100% line fill, and at most 4 bullets per entry. If the page overflows after an addition, undo it and try the next, smaller option.

### Audit loop

Run these pass/fail checks:

1. Exactly one page (`page_count == 1`).
2. Only the four sections: Education, Experience, Projects, Skills.
3. Every entry has 2 to 4 bullets.
4. Every Experience and Projects bullet's last line measures 90 to 100% (`pass: true`).
5. Every bullet traces to a specific master-resume entry, with no claims outside the embellishment boundary. Check every number, tool, and outcome against the master bullet it came from.
6. Every high-weight matched skill appears at least once on the page.
7. No verb is repeated within an entry, and tense is consistent: past tense for past roles, present tense for current ones. A role is current if its end date is "Present" or later than today.
8. The page is full: the last line is less than one line height from the bottom margin (`page_fill.page_full: true`).

Fix the failures, recompile, and re-check. Stop when all checks pass or after 3 iterations. If it stops at the cap, record the checks that still fail for the report.

When rules conflict, this is the precedence:
1. Truthfulness
2. One page
3. Section and bullet counts
4. Full page
5. Line fill
6. Keyword density

## Phase 5: Write the output and update the repo

### Files

```
tailored/Company_Name_Target_Role_Month_Year/
  Raghav_Senthil_Kumar_Target_Role_Resume.pdf
  Raghav_Senthil_Kumar_Target_Role_Resume.tex
```

- Target_Role is the role title. Spaces become underscores, special characters are stripped, and repeated underscores collapse to one.
- Month_Year is the generation date with the month written in full (for example `tailored/Acme_Robotics_Software_Engineering_Intern_September_2026/`, holding `Raghav_Senthil_Kumar_Software_Engineering_Intern_Resume.pdf`).
- If that directory already exists for a different posting (for example two openings with the same title), append the job ID to the directory name.
- Only these two files go in the directory. No aux or log files. measure.py compiles elsewhere and copies only the PDF back.
- The .tex sits two levels below the repo root, so its preamble line is `\input{../../preamble}`.
- Draft in that same directory, overwriting the two files on each iteration, so the final PDF is the one measure.py last produced from the final .tex.

### Tracker

Append one row per tailored resume to `applications.csv`, keeping its header and column order:

| Column | Value |
|---|---|
| company | Company name |
| role | Role title as posted |
| job_id | Job ID, or empty |
| folder | `tailored/<directory>` |
| resume_file | the PDF's file name |
| cover_letter, date_applied, method | empty |
| status | `Tailored` |
| next_step | `Submit application` |
| notes | `Fit NN%; <posting URL>` |

Quote any field that contains a comma. Do not edit existing rows.

### Commit and push

1. Stage only this run's files: `git add tailored/<each new directory> applications.csv`. Never stage other changes in the working tree, and leave them as they are.
2. Commit with a message naming the postings, for example `Tailor resumes: Acme Robotics (Software Engineering Intern), Globex (Data Science Intern)`, ending with any attribution lines the environment requires.
3. Push to the current branch's upstream (`git push`). If the push fails, do not force it; report the error and leave the commit local.

**On claude.ai (no repo):** create each directory under `/mnt/user-data/outputs` instead, paste the contents of `preamble.tex` in place of the `\input` line so each .tex is self-contained, present the files, and skip the tracker and git steps.

## Phase 6: Report in chat

1. **Summary table** of every posting found, including screened-out ones:

   | Company | Role | Location | Fit | Verdict | Outcome |
   |---|---|---|---|---|---|

   Outcome is the resume folder, "Not tailored (declined)", the Skip reason, or the screening reason ("Not an internship", "Non-technical", "Already tracked"). Sort by fit, highest first, with screened-out postings last.

2. **Per tailored posting**, the assessment and the tailoring results:
   - **Posting info:** a table of Employer, Role, Location, Pay, Date posted, Company size (external). Any field not in the posting reads "Not listed". Company size comes from a web lookup and is marked "(external)".
   - **Score and verdict:** **Fit: 72% · Verdict: Apply**, then a one-sentence reason. For eligibility `unknown`, the reason names the rule(s) that came back unknown.
   - **Requirements breakdown:** two tables (Required, Preferred) with columns Skill | Weight | Match | Resume evidence. Sort by weight, highest first, with `none` rows last. For downgraded skills, write `none ⚠ downgraded (evidence not found)`. Evidence is the verbatim quote in quotes, or "—". If a section has no skills, write "No preferred skills listed." (or "required").
   - **Audit:** one line per check (pass/fail), plus the iteration count.
   - **Space:** entries dropped for space, and lines added to fill the page.
   - **Gaps:** any high-weight skill left out because the master resume has no evidence for it.

3. **Skipped postings:** one line each with the reason. For ineligible ones, quote the clause.

4. **Repo:** the commit hash, the files it added, and whether the push succeeded.
