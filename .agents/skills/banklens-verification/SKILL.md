---
name: banklens-verification
description: "Verify BankLens parsing, redaction, browser and session changes with synthetic inputs, independent privacy invariants and reproducible regressions."
---

# BankLens verification

Consult [AGENTS.md](../../../AGENTS.md) for private-data boundaries and
[CONTRIBUTING.md](../../../CONTRIBUTING.md) for setup. Read the relevant portion
of [technical-details.md](../../../docs/technical-details.md) when investigating
recognition, persistence or export behavior. Commands below run from repo root.

## Choose the boundary

| Changed behavior | Existing coverage to inspect |
| --- | --- |
| PDF inventory and input validation | `tests/test_inspect.py` |
| Field examples, profiles and geometry | `tests/test_fields.py`, `tests/test_multiline.py` |
| Review state, local API and folder sessions | `tests/test_preview.py`, `tests/test_server.py`, `tests/test_sources.py` |
| Search, grouping and redacted PDF output | `tests/test_proof.py` |
| Browser interactions | `tools/test_preview_ui.cjs`, `tools/test_multiline_ui.cjs`, `tools/test_proof_ui.cjs` |

Use the configured project interpreter, not a hardcoded machine-specific
runtime. A focused check can use
`python -m unittest discover -s tests -p 'test_proof.py' -v`; the full Python
suite uses `python -m unittest discover -s tests -v`.

For browser coverage, generate only the artificial inputs using
`tools/create_demo_pdf.py` and `tools/create_multiline_demo_pdf.py`. The UI scripts
expect Node.js Playwright and installed Chrome; the launcher supports
`BANKLENS_PYTHON` and the scripts support `BANKLENS_PLAYWRIGHT_PATH`.

## Reproduce independently

Exercise production parsing, session or export functions with wholly synthetic
PDFs and events. Preserve a small fixture and ordered reproduction for a bug;
show the failing behavior before correcting production code when feasible.
Use controlled event ordering or time when testing concurrent sessions and
background jobs. Do not implement a second copy of the production algorithm as
the expected result.

For the affected behavior, assert user-visible outcomes and independent
invariants rather than only matching labels or snapshots:

- Source bytes remain unchanged; generated output stays outside the input set.
- Only selected complete bookings and the currently intended header remain
  visible. Unselected bookings and the relevant balance area are masked.
- Exported copies do not retain source text layers, attachments or source
  metadata. Inspect PDF structure and rendered pixels as separate evidence;
  a black rectangle or absent text alone does not prove complete redaction.
- Unknown table boundaries or unresolved selected continuations block the
  affected export. A fixture must not silently supply the boundary being tested.
- Changed sources and stale selections cannot yield an export for obsolete
  input. Loading a second folder does not redirect an older tab or export job.
- Local API protections remain in place, including session routes, loopback,
  Host/Origin checks and the explicit request header where required.

Vary only cases relevant to the changed boundary: multi-line and cross-page
bookings, amount signs, header/footer boundaries, source changes, cancellation,
retries or session replacement. Retain previous observed fixture variants.

## Describe the evidence

Run focused checks first and broaden when the changed boundary needs it. Do not
relax privacy assertions or change a model expectation merely to make a failure
pass. If a private real-world report motivated the work, reproduce its structure
artificially; do not read its private contents into the agent context.

Report commands, results, fixture scope and missing evidence. Unit success,
browser execution, rendered-PDF inspection and verified real-bank compatibility
are different claims. Neither a synthetic pass nor an unexecuted visual check
establishes support for all statements from a bank.
