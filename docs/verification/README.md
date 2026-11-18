# Verification: bug tracker

Owner: DevOps 2. Purpose: one place to log, assign, update and verify bugs for
the Setu Guide POC, as required by the "Complete Next-Phase Task List".

## Files

| File | What it is |
|---|---|
| `docs/verification/bug-tracker.csv` | The tracker itself (open in Excel, Google Sheets or LibreOffice). Header-only until a real bug is confirmed. |
| `docs/verification/privacy-log-audit.md` | Repeatable check that no private data or secrets reach the logs. File any leak in the tracker. |
| `docs/verification/monitoring.md` | What to observe, alert thresholds and owners (requirements only; no stack is implemented). |
| `docs/verification/devops2-handover.md` | Day 1 handover for a new DevOps 2 intern: repo layout, setup, branch/PR workflow, tests and CI, bug tracker, staging health, and version recording. |
| `docs/verification/README.md` | This guide: how to add, assign, update and verify bugs. |

The tracker is **intentionally empty**. As of the last test run no defect has
been confirmed (`docs/load_and_failure_test_notes.md`, section 4). Do not add a
row you cannot back with evidence.

## How to open and share

- Spreadsheet apps: open `bug-tracker.csv` directly, or import it
  (`Data > From Text/CSV` in Excel). It is plain UTF-8 CSV, one row per bug.
- Google Sheets: `File > Import > Upload` and pick the CSV.
- GitHub: the CSV renders as a table; the README renders below it.
- Share by linking the path in the team channel and in the PR for this branch.
  Anyone with repo access can open the raw file.

## Columns (do not rename or reorder)

1. `Bug ID` - `BUG-001`, `BUG-002`, ... never reuse an id.
2. `Title / Description` - one line: what is wrong and where.
3. `Severity` - `Critical` | `High` | `Medium` | `Low` (see below).
4. `Component` - `API` | `CI/CD` | `deployment` | `AI/ML` | `safety` | `testing` | `documentation` | `other`.
5. `Steps to Reproduce` - numbered, minimal, using synthetic data only.
6. `Expected Result` - what should happen.
7. `Actual Result` - what happened instead (paste the status code / message).
8. `Assigned Owner` - repository handle or role from `docs/team/` (see owners below).
9. `Status` - `New` | `In Progress` | `Fixed` | `Verified` | `Reopened`.
10. `Evidence / File Reference` - log line, test name, file:line, screenshot name, or PR link. No secrets.
11. `Date Reported` - `YYYY-MM-DD`.
12. `Notes` - anything else (blockers, related bug, workaround).

## Adding a bug

1. Open the CSV and add exactly one row on the next free line.
2. Pick the next free `Bug ID`.
3. Fill every column. Leave `Assigned Owner` empty only if you truly do not
   know the owner; put a question in `Notes` and raise it with the team lead.
4. `Status` starts at `New`.
5. Save. If you use Excel, keep the file as **CSV UTF-8** so Hindi/unicode text
   survives.

Field rules for a CSV: wrap a field in double quotes if it contains a comma,
a double quote or a line break; escape an inner double quote by doubling it
(`""`). Keep one bug per row so sorting and filtering work.

## Severity

| Severity | Meaning | Example trigger |
|---|---|---|
| Critical | Service down, data/privacy leak, or wrong safety behaviour. | `/health` down; private data in logs; a distress message answered as normal. |
| High | Core flow broken, no workaround. | `/v1/guide/chat` returns 5xx; CI red on `dev`. |
| Medium | Flow degraded or a workaround exists. | Wrong `X-Cache` value; unclear error detail. |
| Low | Cosmetic, docs, or nice-to-have. | Typo in `docs/api.md`; unclear README step. |

## Assigning

Owners follow `CONTRIBUTING.md` and `docs/team/*.md`:

| Component | Owner |
|---|---|
| API, Docker | DevOps 1 |
| CI/CD, deployment, docs, `.github/`, `deploy/` | DevOps 2 |
| AI/ML (retrieval, prompts, responder) | AI/ML 2 / AI/ML 3 |
| safety | Team lead |
| schemas | Team lead |
| data / evaluation | AI/ML 1 |

Assign by writing the handle/role in `Assigned Owner` and setting
`Status = New` for that owner.

## Updating and verifying (status workflow)

```
New -> In Progress -> Fixed -> Verified
                         ^         |
                         |         v
                      Reopened <---+
```

1. **New** - logged, not started.
2. **In Progress** - owner is working on it. Add the branch/PR link in
   `Evidence / File Reference`.
3. **Fixed** - change merged or staged. The owner states how it was fixed in
   `Notes`.
4. **Verified** - someone other than the fixer reproduced the fix on the target
   (dev machine / staging) and confirmed the `Expected Result`. Put the proof
   (test name, log line, screenshot) in `Evidence / File Reference`.
5. **Reopened** - verification failed; owner goes back to `In Progress` with a
   `Notes` entry explaining what still fails.

Never mark `Fixed` or `Verified` without evidence. Only the verifier moves a bug
to `Verified`.

## Privacy and secrets (mandatory)

- Use synthetic ids/messages only (see `docs/api.md`, section 22).
- Never paste API keys, tokens, passwords, real user data or full request
  bodies. If a log leak is the bug, reference the sentinel marker or line
  number instead of pasting the secret.
- Evidence for privacy bugs points at the audit procedure in
  `docs/verification/privacy-log-audit.md`, plus `docs/api.md` (section 18) and
  `tests/failure/test_log_privacy.py`.

## Scope

This task adds documentation only. It does not change application code, CI
workflows, dependencies or configuration.
