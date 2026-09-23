# Summer 2027 Internship Applications

## What this repository is for

Version control for my resumes during the Summer 2027 internship cycle. It holds a master resume, a general-purpose base resume, and a tailored resume for each posting I apply to. It also contains `auto-apply`, a Claude skill that finds postings worth applying to and drafts those tailored resumes for me.

## Layout

```
master/          Master resume (.tex/.pdf): every bullet I've written. The source of truth; never sent out.
base/            General one-page resume built from master; also the layout template for tailored resumes.
preamble.tex     LaTeX preamble shared by every resume (\input by each .tex).
tailored/        One folder per posting: <Company>_<Role>_<Month>_<Year>/ with the tailored .tex and .pdf.
archive/         Folders for closed or rejected applications (moved here, never deleted).
auto-apply/      The Claude skill:
  SKILL.md         Pipeline instructions
  candidate.md     Private candidate facts used for eligibility checks (git-ignored)
  scripts/
    score.py       Verifies resume evidence and computes the fit score and verdict
    measure.py     Compiles LaTeX and measures page count, line fill, and page fill
```

## How the skill works

Give Claude a URL (a careers page, a search-results page, or a single posting) and ask it to run auto-apply. It never submits an application.

1. **Collect:** gathers every internship posting from the URL, and screens out non-internships, non-technical roles, and postings already in the tracker.
2. **Assess:** checks eligibility (term, citizenship, clearance, graduation window, and so on), pulls the technical skills from each posting, matches them to evidence in the master resume, and runs `score.py` to get a fit percentage and a verdict of **Apply**, **Review**, or **Skip**.
3. **Decide:** tailors a resume for every Apply posting, and asks me which Review postings to tailor.
4. **Tailor:** builds a one-page resume from the base template, using only content from the master resume. `measure.py` compiles it, and an audit loop checks that it is exactly one page, full to the bottom, has 90–100% last-line fill on every bullet, covers the posting's high-weight skills, and makes no claims beyond the master resume.
5. **Save:** writes the `.tex` and `.pdf` to `tailored/`, commits and pushes them, and adds a row for each to the Internship Application Tracker Google Sheet.
6. **Summarize:** reports each posting's fit, the skill-by-skill breakdown, the audit results, and anything skipped.

## License

MIT
