# BankLens agent instructions

BankLens is an independent Python application with a local browser UI. It filters
and redacts downloaded PDF bank statements without banking credentials, cloud
processing or runtime AI. Keep that product boundary intact.

## Issues, branches and pull requests

- At the start of a new implementation task, inspect the worktree, repository,
  branch and current `origin/main`. Fetch before branching when access is
  available; report unavailable access rather than claiming freshness. Preserve
  unrelated local work and the base of an existing, relevant PR.
- Track bugs, features and substantial maintenance in this repository's issues.
  Search open and closed issues before opening one. Reuse the matching issue for
  follow-up observations and fixes; a small correction to an existing PR does
  not need a new issue.
- Keep the active request, issue, branch and PR aligned. Understanding questions
  authorize an answer; implementation requests authorize work on the requested
  change. Resolve a genuinely conflicting target before changing it.
- Use short-lived `codex/<issue>-<topic>` branches and PRs targeting `main`.
  Deliver requested implementation through a commit, pushed working branch and
  reviewable PR. Do not commit or push directly to `main` unless the owner
  explicitly requests that exception. Do not introduce a long-lived integration
  branch or change repository protections as a side effect.
- Link the issue from the PR. Explain the resulting behavior, relevant checks
  and remaining limitations. Use draft status while work is unfinished.
- Merge only when the owner explicitly asks for that merge and applicable checks
  and review requirements are satisfied. A request to implement, commit, push or
  open a PR does not itself authorize merging or publishing a release.

## Verification and handoff

- Run checks that exercise the changed behavior before committing. Documentation
  changes need formatting and link checks; they do not require the application
  test suite. Prefer focused checks, then broaden for affected boundaries.
- For bugs, preserve a minimal synthetic reproduction and demonstrate the
  failing assertion before fixing when feasible. State when reproduction is
  incomplete; do not adjust expectations just to accept faulty behavior.
- Keep unit, browser, rendered-PDF and real-format evidence distinct. A local
  pass does not establish CI success or compatibility with every bank layout.
- Inspect configured workflows before reporting CI. If none exist, say so.
  Match results and artifacts to the intended commit, and distinguish pending,
  passed, failed, skipped and unavailable checks. After an authorized merge,
  follow any triggered checks on the resulting `main` commit to completion.
- Use `banklens_pdf/version.py` for app, API and recognition identity. Change the
  relevant version when its behavior or compatibility changes; documentation
  alone does not require a version bump.

## Private data and local processing

- Use only wholly synthetic PDFs and fixtures in tests, screenshots, issues and
  PRs. Never publish real statements, extracted values, personal filenames,
  private workspaces or exported proofs.
- The local toolkit may process the owner's statements for their own browser
  session. Do not fetch private page images, text or booking responses into the
  agent's context. Use aggregate local diagnostics when investigating real data;
  reproduce the relevant structure with artificial data.
- Keep originals read-only, input/state directories separate and server access
  on loopback with the existing session, Host and Origin protections. Do not
  introduce remote assets, telemetry or external processing incidentally.
- Follow the current `CONTRIBUTING.md`, `COPYRIGHT.md` and `LICENSE` for
  contributions and licensing.

## Project skills and references

Load the skill relevant to the task; unrelated skills need not be read:

- Issue, branch, PR or review work: [banklens-workflow](.agents/skills/banklens-workflow/SKILL.md).
- Parser, session or redaction changes and regressions: [banklens-verification](.agents/skills/banklens-verification/SKILL.md).
- CI, release readiness or result handoff: [banklens-ci-handoff](.agents/skills/banklens-ci-handoff/SKILL.md).

The human workflow is in [docs/development-workflow.md](docs/development-workflow.md).
Architecture and diagnostics are in [docs/technical-details.md](docs/technical-details.md).
Keep README, contribution guidance and UI text in German; agent skills may use
English. These rules and skills are maintained within BankLens itself.
