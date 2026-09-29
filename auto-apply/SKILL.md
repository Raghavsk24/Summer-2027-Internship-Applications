---
name: auto-apply
description: This is an internship application automation. Input a URL (a careers page, a job-search results page, or a single posting) and the agent will scrape the site for internship postings. It will check whether the candidate is eligible and compute a score on how the candidates master resume matches with internship posting. It then tailors a one-page LaTeX resume (PDF and .tex) for every posting worth applying to. Finally, it adds each posting to the Internship Application Tracker Google Spreadsheet that the candidate has connected the agent to and gives a summary.

---

# Auto-Apply

Pipeline: **Search the URL → Scrape internship posting→ assess candidate match for each posting → tailor resumes for the ones worth applying to → add them to the Google Sheet tracker → summarize in chat.**

You do the judgment work (eligibility, skill matching, content selection, rewriting, auditing). The scripts do only mechanical work: `scripts/score.py` verifies evidence and computes fit; `scripts/measure.py` compiles LaTeX and measures the PDF. This skill never submits an application, nor does it commit a change.

**Inputs** (paths relative to the repo root):
- Candidate facts: `auto-apply/candidate.md`
- Master resume: `master/Raghav_Senthil_Kumar_Master_Resume.tex`. Use the `.tex` file, not the PDF next to it.
- Base template: `base/Raghav_Senthil_Kumar_Resume.tex`
- Shared preamble: `preamble.tex`. Both resumes pull it in with `\input{../preamble}`.
- Tracker: the **Internship Application Tracker** Google Sheet on Raghav's Google Drive, file ID `1OPAJhLDzKnxyn1oOEVu6YY1ZwhrUdbzq2O4vxvycIkQ` (https://docs.google.com/spreadsheets/d/1OPAJhLDzKnxyn1oOEVu6YY1ZwhrUdbzq2O4vxvycIkQ/edit). If that ID stops resolving, search Drive for the title. `applications.csv` in the repo is no longer updated.
- Scorer: `auto-apply/scripts/score.py`
- Measurer: `auto-apply/scripts/measure.py`

The template uses no `fontspec`, so the engine is `pdflatex`. measure.py detects this on its own.

---

## Phase 1: Collect postings

1. Fetch the URL. If the fetched text has no job titles, open it in the browser and read the page text instead.
2. Decide whether the URL is a **single posting** or a **listing**.
   - **Single posting:** that posting is the only posting to evaluate.
   - **Listing:** go through every page of results and collect each posting's title, URL and job ID. Then open each posting to read its full description.
3. Remove irrelevant postings from the list being assessed
   - **Not an internship:** full-time, new-grad, or experienced roles.
   - **Clearly non-technical:** for example HR, marketing, sales, legal, or finance internships with no technical skills.

## Phase 2: Evaluate each Intenship

For every remaining posting, run the steps below. Keep each posting's results (posting info, eligibility, score.py output) for Phases 3 to 6.

1. Read the posting, candidate.md, and the master resume. Note the posting date if one is shown.
2. Run the eligibility check (rules below). If any rule returns ineligible, automatically give it a verdict of Skip, with the quoted clause. Do not score it.
3. Extract technical skills from the required and preferred sections. For each, record: section, whether it is emphasized ("strong", "must", "proficient", "expert"), whether it appears in the role title or first responsibility, and mention count including synonyms.
   - Sections headed "Basic", "Minimum", or "Must have" are **required**. Sections headed "Preferred", "Bonus", "Nice to have", or "Plus" are **preferred**. If the posting has no split, treat every listed qualification as required.
   - Extract technical skills only (languages, frameworks, tools, platforms, technical concepts). Skip soft skills, degree requirements, and eligibility items.
   - Count mentions across the whole posting, including synonyms (for example "ML" and "machine learning" count as one skill. PyTorch and TensorFlow or also similar frameworks so they count as synonyms. SQL and PostgreSQL count as synonyms. React and Next.js count as synonyms. These are examples; they are not an exhaustive list).
4. Match each skill to the master resume, assign a match type, and quote the resume text verbatim as evidence.
5. Send everything to score.py via stdin (contract below). Use its fit_percent, verdict, weights, and final match types exactly as returned. Never override them and never hand-compute a score.

### Eligibility rules

Each rule returns eligible, ineligible, or unknown. "Ineligible" requires a verbatim quote from the posting. Any "unknown" forces the verdict to Review. If nothing is stated, the result is eligible.

1. **Term:** must be Summer 2027. A summer role with no year that was posted fall 2026 or later counts as 2027. "Summer or Fall 2027" passes. Only an explicit different term fails.
2. **Citizenship:** only "US citizen required" (or equivalent) fails. "US person" and "authorized to work in the US without sponsorship" pass for a permanent resident.
3. **Clearance:** "must hold or be able to obtain a security clearance" fails. Vague mentions of cleared work are unknown.
4. **Class standing:** wording keyed to graduation year or grade cohort ("rising juniors", "Class of 2029") defers to rule 5. Wording keyed to time enrolled ("completed two years of study") is checked against one year completed. If the job posting metions its looking for Juniors and Seniors only the verdict is SKip
5. **Graduation window:** the posting's range must include May 2029. This is the primary test for standing. If the posting does not have a graduation window, it is fine and it skips this requirement
6. **Program restrictions:** only an explicit eligibility restriction to a group Raghav is not in fails (demographic, specific schools, first-gen, veterans, membership requirements). Ignore EEO "we encourage X to apply" language.
7. **GPA minimum:** No college GPA yet (Assume 4.0)

Overall eligibility sent to the script: `ineligible` if any rule is ineligible, else `unknown` if any rule is unknown, else `eligible`.

### Match types

| Type | Example | Credit |
|---|---|---|
| exact | Python / Python | 1.0 |
| alias | Postgres / PostgreSQL | 1.0 |
| allowed_alternative (posting explicitly permits substitutes) | "Java or similar OOP language" / C++ | 1.0 |
| adjacent (related skill, posting does not permit substitutes) | "Java" / C++ or "TensorFlow"/"PyTorch" | 0.8 |
| none | | 0 |

Evidence must be copied verbatim from the master resume. Never paraphrase it.

- Quote one contiguous span of resume text, preferably the most specific one (a bullet over a skills-list entry). Quote the text as it reads on the page, leaving out LaTeX markup (`\emph{...}` → `...`, `\&` → `&`, `\%` → `%`, `$|$` → `|`). Do not change, reorder, or abbreviate any words, numbers, or punctuation.
- For `none`, set evidence to `null`.
- The script substring-matches each quote against the resume. If a quote is not found, it downgrades that skill to `none`.

### score.py contract

Pass the JSON through stdin; never write intermediate JSON files. From the repo root:

```bash
python auto-apply/scripts/score.py --resume master/Raghav_Senthil_Kumar_Master_Resume.tex <<'EOF'
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
- **High-weight skill:** 5 skills that had the highest weights or match with the internship posting
- **Matched:** match type exact, alias, allowed_alternative, or adjacent.
- **Unmatched:** final match type none, including downgraded skills.

### Sources

- The **base template** owns layout and the header: document class, `\input` of the preamble, header block, section and entry macros, spacing.
- The **master resume** owns all content. Nothing appears on the tailored resume that is not traceable to a specific master-resume entry. Education, entry headings (titles, links, dates), bullets, and skills all come from the master. However, you are allowed to embelish numbers and rephrase content from the master resume
- Master bullets carry `% core | tags: ...` comments. Use them as selection hints, and leave them out of the output.
- The master's Certifications section is never used.

### 4.1 Select content

- Score each experience and project by the summed weight of the posting skills its master-resume bullets evidence. Count a skill once per entry, and count adjacent matches at half weight.
- **Experience** stays in reverse-chronological order. Drop an entry only if space forces it.
- **Projects** are ordered by relevance score, highest first, and cut from the bottom.
- Start the draft with every experience and project, and cut only after measure.py reports more than one page. The page must also end full (see Page-fill rule), so never cut more than the overflow requires.
- Within each entry, pick the bullets that evidence the highest-weight skills, within the entry-length limit below. Prefer `core` bullets when scores tie.
- **Entry length:** every Experience and Projects entry's bullets span **3 to 6 lines** in total. Count every wrapped line of every bullet (`entries[].line_count`); the entry's heading line does not count. Use at least 3 bullets per entry. If an entry runs past 6 lines, condense or cut its lowest-weight bullet (or merge two short ones) until it fits. When space is tight, drop the lowest-relevance project instead of taking any entry below 3 lines or 3 bullets. If an entry cannot reach 3 lines and 3 bullets truthfully, drop it.

### 4.2 Build the draft

- Start from a copy of the base template and pull in the selected content.
- Use exactly four sections, with these headers: `Education`, `Experience`, `Projects`, `Skills`. (The base template's `Technical Skills` becomes `Skills`.)
- Add `Phoenix, AZ $|$ ` to the start of the header's contact line only if the posting's work location is in Arizona. The company's headquarters and remote roles do not count. Otherwise the header shows no location.
- Education comes from the master unchanged, except that its Activities line must fit on one line. Drop the least relevant activities to make it fit, and never list one twice.
- **Skills section layout:** 4 or 5 category lines (never all 6), each fitting on one line.
  - Take the categories from the master's six Skills lists and keep the master's labels exactly: `Programming Languages`, `Frameworks/Platforms`, `DevTools`, `AI/ML`, `Data & Analytics`, `Concepts/Practices`. Do not rename, merge, or invent categories.
  - Pick the 4 or 5 lists most relevant to the posting. `Concepts/Practices` is always one of them. Keep every list that holds a posting-matched skill, and drop the least relevant one (for example `Data & Analytics` for a backend SWE role, or `DevTools` for an analytics role).
  - Pull in as many ATS-relevant skills from the master's skills inventory as fit on each line. Order: posting-matched skills first, highest weight first. Then add the other master skills in that list that an ATS for this role would look for. Then add the rest of that list until the line is full.
  - A skill appears on only one line, under its master category. On every line except Concepts/Practices, only skills from the master's Skills section may appear, and unmatched posting skills are never added.
  - **Concepts/Practices is built from the posting, not copied from the master's list.** Reshuffling the same master terms (Object-Oriented Programming, REST APIs, Unit Testing, Agile, ETL) onto every resume is exactly what to avoid. Build the line fresh for each posting:
    1. Read the whole posting (team blurb, responsibilities, required and preferred qualifications) and list the technical concepts, methods and practices it asks for, in its own words: for example "Root Cause Analysis", "System Integration", "Data Modeling", "KPI Reporting", "Distributed Systems", "Concurrent Programming", "Code Reviews", "Benchmarking", "Requirements Gathering", "Competitive Analysis". Include ones the role title and team imply (a triage team implies "Log Analysis"; a metrics team implies "Metric Design").
    2. Keep every concept that Raghav's experience, projects or coursework plausibly touches, even when the master never names it. A little embellishment is welcome on this line: Citation Chain's PostgreSQL tables support "Data Modeling", revising the VLM schema after each wrong prediction supports "Root Cause Analysis", Computer Science II supports "Data Structures". Leave a concept out only when nothing he has done relates to it.
    3. Order the line by the posting's emphasis, in Title Case, using the posting's wording. Add master Concepts/Practices items only to fill leftover room, and only ones the posting also calls for.
    4. At least 4 of the line's items come from this posting's own wording, and the line is never a reordering of another resume's Concepts/Practices line.
    5. Concepts only. Languages, frameworks, libraries, platforms and tools stay master-only on every line, so never list Snowflake, Rust or Tableau because a posting names them. Bullets still follow the rewrite rules and the embellishment boundary below.
  - measure.py only measures bullets, so check the Skills lines in the PDF's text (a wrapped line shows up as an extra line) and drop the lowest-priority skill from any line that wraps.

### 4.3 Rewrite bullets

- Use the tech-resume-optimizer skill for bullet craft. The rules in this file override it wherever they conflict (for example, never add a summary section).
- High-weight matched skills get the posting's exact phrasing, placed early in the bullet.
- Skills marked unmatched are never inserted, anywhere on the page. The one exception is an unmatched concept or practice (never a tool) on the Concepts/Practices line, under the Skills rules above.
- Outside Concepts/Practices, the Skills section lists only master-resume skills, reordered by weight: posting-matched skills first, highest weight first, then other master skills relevant to the role.
- Single column, no tables, standard headers. Do not add sections, columns, icons, or graphics.
- Escape LaTeX special characters in all inserted text: `% & # _ $ { } ~ ^ \` (for example `C\#`, `R\&D`, `40\%`, `\$3.5K`).

### 4.4 Compile and measure

```bash
python auto-apply/scripts/measure.py <path.tex>
```

- It compiles twice in a temporary directory, copies the PDF next to the .tex, and prints JSON: `page_count`, `right_edge`, `page_fill`, `entries[]`, and `bullets[]` with `index`, `entry`, `page`, `preview` (first 8 words), `line_count`, `last_line_fill_pct`, `pass`.
- `page_fill` reports the gap between the last line and the bottom of the text area: `bottom_gap_pt`, `line_height_pt`, `free_lines` (gap ÷ line height), and `page_full` (true when the gap is less than one line, so no further line fits).
- `entries[]` groups consecutive bullets under the heading line above them: `entry`, `heading` (for example `Chronos | Live Website | Source Code December 2025`), `bullets` (indexes), `bullet_count`, and `line_count` (total lines the entry's bullets span). Entry 1 is Education.
- Bullets are numbered in page order, so the two Education lines (Coursework, Activities) are bullets 1 and 2. Use `preview` to map each bullet back to its `\resumeItem` in the .tex.
- On a compile error it prints the LaTeX log lines and exits non-zero. Fix the .tex and rerun.
- If the TeX engine is missing, install it first: `apt-get install -y texlive-latex-extra`, plus `texlive-xetex` if the template uses fontspec. measure.py installs pdfplumber itself if needed.

### 4.5 Run the audit loop (below), then write the output (Phase 5)

### Embellishment boundary

Allowed:
- stronger verbs;
- reordering what a bullet emphasizes;
- stating context the source clearly implies;
- swapping in the posting's term when the match is alias or allowed_alternative;
- listing a concept or practice the posting names on the Concepts/Practices line when Raghav's work plausibly involved it, even if the master never names it (concepts only, never tools).

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
1. **Restore a dropped project,** the next one by relevance, with 3 one-line bullets. This costs about 5 lines (heading, spacing, bullets), so use it when `free_lines` is 5 or more.
2. **Add an unused master bullet** to an entry whose bullets span fewer than 6 lines, taking the bullet that evidences the highest-weight posting skill first. Each one-line bullet costs about 1.1 lines. Bring its wording to 90–100% line fill as usual.
3. **Grow a one-line bullet into two full lines** using detail its master bullet states or clearly implies (for example, restoring words trimmed earlier). This costs exactly 1 line and is the right move when `free_lines` is between 1 and 1.1.
4. **Add a Skills category line** built from a master Skills category not yet shown, up to 5 lines in total, following the Skills layout rules.

Every added line follows the same rules as the rest of the page: traceable to the master, inside the embellishment boundary, 90–100% line fill, and 3–6 lines (at least 3 bullets) per entry. If the page overflows after an addition, undo it and try the next, smaller option.

### Audit loop

Run these pass/fail checks:

1. Exactly one page (`page_count == 1`).
2. Only the four sections: Education, Experience, Projects, Skills.
3. Every Experience and Projects entry's bullets span 3 to 6 lines, with at least 3 bullets (`3 <= entries[].line_count <= 6` and `entries[].bullet_count >= 3`, skipping entry 1, Education, whose Coursework and Activities lines are exempt).
4. Every Experience and Projects bullet's last line measures 90 to 100% (`pass: true`).
5. Every bullet traces to a specific master-resume entry, with no claims outside the embellishment boundary. Check every number, tool, and outcome against the master bullet it came from.
6. Every high-weight matched skill appears at least once on the page.
7. No verb is repeated within an entry, and tense is consistent: past tense for past roles, present tense for current ones. A role is current if its end date is "Present" or later than today.
8. The page is full: the last line is less than one line height from the bottom margin (`page_fill.page_full: true`).
9. The Skills section has 4 or 5 lines, each with a master category label, each fitting on one line, and no skill appears on more than one line.
10. Concepts/Practices is on the page, at least 4 of its items come from this posting's own wording, none of them is a tool, language or framework, and it is not a reordering of another resume's Concepts/Practices line.

Fix the failures, recompile, and re-check. Stop when all checks pass or after 3 iterations. If it stops at the cap, record the checks that still fail for the report.

When rules conflict, this is the precedence:
1. Truthfulness
2. One page
3. Section counts and entry length (3–6 lines, at least 3 bullets)
4. Full page
5. Line fill
6. Keyword density

## Phase 5: Save the resumes and update the tracker

### Files

```
tailored/Company_Name_Target_Role/
  Raghav_Senthil_Kumar_Target_Role_Resume.pdf
  Raghav_Senthil_Kumar_Target_Role_Resume.tex
```

- **No dates in any name.** No directory or file under `tailored/` carries a date, month, year, season or term: not the generation date (`September_2026`) and not the internship term (`Summer_2027`, `2027`).
- Company_Name is the company as the tracker's Company column names it (for example `General_Dynamics_Information_Technology`, `Hudson_River_Trading`).
- Target_Role is the posted title cut down to the role itself: drop dates, years, seasons and terms, program names, locations, category prefixes in front of the real role, and filler qualifiers such as "Focused", and write "Internship" as "Intern". Spaces become underscores, special characters are stripped, and repeated underscores collapse to one. These examples are Raghav's own renames:

  | Posted title (company) | Directory | Files |
  |---|---|---|
  | Software Engineer Intern - Backend Focused - Summer 2027 (Rippling) | `Rippling_Software_Engineer_Intern_Backend/` | `Raghav_Senthil_Kumar_Software_Engineer_Intern_Backend_Resume.pdf` and `.tex` |
  | GDIT Summer Internship Program – Summer 2027 Generative AI Software Development Internship (General Dynamics Information Technology) | `General_Dynamics_Information_Technology_Generative_AI_Software_Development_Intern/` | `Raghav_Senthil_Kumar_Generative_AI_Software_Development_Intern_Resume.pdf` and `.tex` |
  | Software Developer, Network Software Intern (Summer 2027) (Astranis) | `Astranis_Network_Software_Intern/` | `Raghav_Senthil_Kumar_Network_Software_Intern_Resume.pdf` and `.tex` |
  | Data Scientist Intern - 2027 (Hudson River Trading) | `Hudson_River_Trading_Data_Scientist_Intern/` | `Raghav_Senthil_Kumar_Data_Scientist_Intern_Resume.pdf` and `.tex` |

- If that directory already exists for a different posting (for example two openings with the same title), append the job ID to the directory name, never a date.
- Only these two files go in the directory. No aux or log files. measure.py compiles elsewhere and copies only the PDF back.
- The .tex sits two levels below the repo root, so its preamble line is `\input{../../preamble}`.
- Draft in that same directory, overwriting the two files on each iteration, so the final PDF is the one measure.py last produced from the final .tex.


### Update the Internship Application Tracker

Add one row per tailored resume to the tracker sheet's application table, the table whose header row reads:

| Application Status | Company | Position | Date Applied | Details | Application Portal |
|---|---|---|---|---|---|
| `In Progress` | Company name | Role title exactly as posted | empty | `- Auto-apply fit NN% - Tailored resume: tailored/<directory>/` plus any key posting facts, such as work location, program length, or an eligibility note | Posting URL |

- Put new rows in the first empty rows directly below the last filled row of that table. Never edit existing rows, and never touch the Category / Count summary block above the table, since its counts update on their own.
- **How to write:** the Drive connector can read the sheet but cannot edit cells. Use, in order:
  1. a connected tool that can write Google Sheets cells, if one is available;
  2. otherwise, the browser where Raghav is signed in to Google (Claude in Chrome in the desktop app): open the sheet URL, click the Application Status cell of the first empty row, and type each row's six values with Tab between cells and Enter at the end of the row.
- **Verify:** re-read the sheet with `read_file_content` and confirm each new row appears exactly once, with every value in the right column. Fix any misplaced cell.
- If no write path works, put the rows in the chat as tab-separated lines ready to paste, and say plainly that the tracker was not updated.

## Phase 6: Summarize in chat

The summary goes in the chat response itself. Never save it to a file.


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
   - **Concepts/Practices:** which posting concepts went on the line and what backs each one.

3. **Skipped postings:** one line each with the reason. For ineligible ones, quote the clause.

4. **Repo:** the commit hash, the files it added, and whether the push succeeded.
5. **Tracker:** the rows added to the Internship Application Tracker (Company, Position), and whether the write was verified. If it was not updated, include the paste-ready rows.
