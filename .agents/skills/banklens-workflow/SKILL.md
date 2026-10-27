---
name: banklens-workflow
description: "Deliver BankLens changes through a matching issue, short-lived branch and reviewable pull request; use for implementation planning, issue triage and PR preparation."
---

# BankLens issue-to-PR workflow

Read the repository's [AGENTS.md](../../../AGENTS.md) and consult
[development-workflow.md](../../../docs/development-workflow.md) for the human
workflow. These are BankLens-local instructions.

## Establish the task

- Verify repository, worktree, branch, issue and any referenced PR before editing
  or writing to GitHub. Use the issue's actual scope and PR base, not a nearby
  open item or a remembered branch from another task.
- At a new task or resumed session, fetch and inspect `origin/main` when access
  is available. Preserve uncommitted work; do not reset or rebase it implicitly.
  Reuse the relevant open PR branch for follow-ups instead of creating duplicates.
- Answer assessment questions as questions. An implementation request authorizes
  the requested change and preparing its reviewable PR; routine steps in that
  authorized workflow do not need repeated confirmation.

## Track the work

Search open and closed issues before recording a bug, feature or substantial
maintenance task. Add relevant observations to the matching issue. Keep expected
behavior, observed behavior and suspected causes distinct. Record app version or
source commit when known; unknown provenance stays unknown.

Use only synthetic examples and aggregate diagnostics. Do not transfer personal
statements, booking text, file paths or workspaces to GitHub. Sharing a BankLens
issue does not authorize posting feedback to any other repository.

## Prepare the change

Use a short `codex/<issue>-<topic>` branch from the current appropriate base.
Keep one coherent change per PR and link its issue. Follow the
[verification skill](../banklens-verification/SKILL.md)
when changing parsing, sessions or exports. Select checks according to the diff;
documentation alone does not require running the application suite.

Commit the verified change and push the working branch. Open a PR against `main`
with the final behavior, issue, executed checks and limitations. Keep unfinished
work in draft. Update the existing PR after follow-ups rather than preserving an
obsolete description. Do not change repository protections or add release
automation merely to complete an ordinary PR.

## Review and hand off

Check the final diff against the issue. Confirm that no generated PDFs, private
state or unrelated files entered the commit. Match any CI evidence to the PR's
current head, accounting for a synthetic merge SHA if the workflow uses one.
Hand off the PR URL, issue, branch, commit and actual checks.

Wait for an explicit owner instruction before merging. If that instruction is
already present, use it after applicable checks and review requirements are met;
do not ask for the same authorization again. A general implementation, commit,
push or PR request does not authorize a merge or release publication.
