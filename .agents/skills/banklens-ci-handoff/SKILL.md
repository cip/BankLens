---
name: banklens-ci-handoff
description: "Run or assess BankLens CI and release-readiness checks, then hand off exact commit and artifact evidence; use for build status, PR checks and authorized merges or releases."
---

# BankLens CI and handoff

Use [AGENTS.md](../../../AGENTS.md) and the current repository workflows as the
source of requirements. Read [development-workflow.md](../../../docs/development-workflow.md)
for the merge boundary. This skill does not presume a CI pipeline or installer
exists and does not grant permission to merge or publish.

## Resolve the source and checks

Identify the intended issue, PR, base/head, branch and commit. Inspect
`.github/workflows/` if present before dispatching or interpreting runs. If no
workflow exists, report local results and CI as not configured. Do not invent a
pipeline, dashboard or required status check.

Select the relevant local checks before a commit using the
[verification skill](../banklens-verification/SKILL.md).
For documentation or skill-only edits, inspect links, Markdown/YAML structure,
skill metadata and authorization boundaries, plus `git diff --check`. If the
skill-creator structural validator is available, use it; otherwise describe
which static checks were actually performed. Static checks are not agent
behavioral evaluations. Skip unrelated app tests for these changes.

## Monitor actual runs

- Reuse a run already triggered for the requested commit instead of dispatching
  duplicates. Re-check the PR head before handoff and mark superseded evidence.
- Distinguish the PR head from any synthetic merge commit tested by CI. Inspect
  relevant jobs through completion; a queued run, uploaded artifact or successful
  commit is not proof that all checks passed.
- Diagnose failed-job logs before retrying. Separate application failures from
  missing dependencies, infrastructure and cancellation. Avoid repeated full
  runs when a focused retry is justified.
- Retain the failed command and cause for blocked local checks. Do not call a
  partial substitute a full-suite pass. Do not introduce external services,
  credentials or paid evaluations as an incidental validation step.

## Verify any deliverable

Read app, API and recognition identity from `banklens_pdf/version.py` when
relevant. Version changes follow the changed behavior; documentation edits do
not require app-version increments. Keep local or packaged source identity tied
to the actual commit rather than copying a version from another branch.

If the task produces an artifact, verify its existence and provenance before
claiming it is available. Distinguish source downloads, exported proof PDFs and
installable application packages. A generated PDF proves neither a successful
application build nor installability. Synthetic test artifacts contain no real
bank data; private proof exports are not release assets.

## Finish the authorized operation

Without explicit merge approval, hand off the reviewable PR. After an approved
merge, verify the resulting `main` commit and monitor any workflows it actually
triggers. Publishing a release or installing an artifact is a separate action
unless already included in the owner's request.

Report the PR URL, branch/commit, relevant version, executed checks and remaining
limitations. Include real CI run and artifact links when available. State
pending, passed, failed, skipped, unavailable or not configured accurately.
