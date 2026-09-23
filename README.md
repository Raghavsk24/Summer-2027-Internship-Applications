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


