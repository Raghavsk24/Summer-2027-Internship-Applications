# Summer 2027 Internship Applications

Resume version control and application tracking for the Summer 2027 internship cycle.

## Layout

```
master/     Master resume: every bullet ever written (source of truth, never sent)
base/       General one-page resume built from master (quick applications)
shared/     preamble.tex, shared by every resume
tailored/   One folder per application: <Company>_<Role>-Intern_<YYYY-MM>/
              Raghav_Senthil_Kumar_<Role>_Resume.tex / .pdf
              job-posting.md        (copy of templates/job-posting.md)
              cover-letter.tex/.pdf (optional)
templates/  job-posting.md template
tools/      Resume skills + check_line_fill.py
archive/    Closed/rejected application folders (move here, never delete)
applications.csv   Tracker: which version went where, and its status
```

## Workflow for a new application

1. Update `master/` first if there's anything new (project, skill, metric). Commit it.
2. `mkdir tailored/<Company>_<Role>-Intern_<YYYY-MM>`, then copy in `base/*.tex` and `templates/job-posting.md`.
3. Fill in `job-posting.md` with the full posting text.
4. Tailor the resume by pulling bullets from master. `\input{../../shared/preamble}` is the preamble path.
5. Compile to PDF, then run `tools/check_line_fill.py`.
6. Add a row to `applications.csv`.
7. Commit as `tailored/<folder>`. After submitting, commit again as `applied/<folder>` and tag it:
   `git tag applied/<folder>`. The tag pins the exact PDF that was sent.

## Tracker statuses

`Tailored` → `Applied` → `OA` → `Interview` → `Offer` / `Rejected` / `Withdrawn`

## Rules

- Never edit master for a single application; tailor in the application's folder.
- Don't overwrite a PDF after it has been sent. Put changes in a new folder, or use the tag to recover it.
- Move dead applications to `archive/` instead of deleting them.
