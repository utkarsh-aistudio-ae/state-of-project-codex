---
name: state-report-writer
description: Turn completed Project Intel synthesis artifacts into canonical audit reports and curated management PDF briefs. Use when Codex needs to produce, review, or rerender a state report from Project Intel synthesis JSON, write canonical report JSON/Markdown under data/reports, render an HTML/PDF management brief, or check report presentation without redoing synthesis reasoning.
---

# State Report Writer

Use this skill after `project-state-synthesizer` has produced a completed and
validated synthesis artifact.

The synthesizer owns reasoning. The report writer owns presentation,
readability, source visibility, caveats, review sections, and derivative PDF
rendering. The JSON/Markdown report is the agent/audit artifact. The HTML/PDF
report is a management brief and must not be a mechanical Markdown printout.

When creating, changing, or reviewing the PDF/HTML brief shape, read
`references/management-pdf-brief.md`.

## Workflow

1. Confirm the synthesis artifact is completed:

   ```bash
   python3 scripts/project_intel.py validate-synthesis data/projects/<Project-tag>/synthesis/<run-id>_synthesis.json
   ```

2. Write the report from the synthesis:

   ```bash
   python3 scripts/project_intel.py write-state-report <Project-tag> --synthesis data/projects/<Project-tag>/synthesis/<run-id>_synthesis.json
   ```

   If no `--synthesis` path is provided, the command uses the latest
   `synthesized` artifact for the project.

3. Review the generated private artifacts:

   ```text
   data/reports/<Project-tag>/<YYYY-MM-DD>/<run-id>_state-of-project.json
   data/reports/<Project-tag>/<YYYY-MM-DD>/<run-id>_state-of-project.md
   data/reports/<Project-tag>/<YYYY-MM-DD>/<run-id>_state-of-project.html
   data/reports/<Project-tag>/<YYYY-MM-DD>/<run-id>_state-of-project.pdf
   data/reports/<Project-tag>/<YYYY-MM-DD>/<run-id>_state-of-project.preview.png
   ```

4. Treat JSON and Markdown as canonical audit artifacts. Treat HTML and PDF as
   curated management derivatives. Markdown should still include user-openable
   links to concrete source artifacts where useful; unlike the PDF, it may also
   include evidence IDs, source paths, and the evidence index.
5. If the report is a dry run or review-only render, pass:

   ```bash
   python3 scripts/project_intel.py write-state-report <Project-tag> --no-advance-cursor
   ```

## Report Rules

- Do not add factual claims that are not present in synthesis or source
  evidence.
- Keep uncertain records in review sections.
- Preserve synthesis confidence, source coverage gaps, caveats, and human-review
  needs.
- Suggested follow-ups are proposals only. Do not create tickets, send emails,
  update deployments, or write to external systems.
- Keep the PDF readable for AiStudio management: lead with the executive state,
  material changes since the cursor, shipped/deployed work, client signals,
  risks, blockers, open questions, and next actions.
- Do not hide skipped, planned, unavailable, or stale sources.
- Do not include raw source transcript/email blocks in the management report.
  Keep evidence IDs, source paths, exhaustive evidence indexes, and audit tables
  in JSON/Markdown rather than the PDF.
- Add links to concrete source artifacts when they are directly relevant and
  available: conversations, email threads, PRs, issues/tickets, commits,
  deployments, docs, repos, or other resource URLs. Prefer the most specific
  link that supports the statement. Do not substitute local source-file paths
  or opaque evidence IDs for real user-openable links.
- Prefer a concise 1-2 page management brief as a soft target. Do not enforce a
  hard page limit when the project state genuinely needs more space.

## Expected Sections

The canonical Markdown should include detailed audit sections:

- TL;DR
- Shipped / deployed
- Client or stakeholder signals
- Meetings, decisions, and commitments
- Risks, blockers, and open questions
- Suggested follow-ups
- Uncertain / review
- Source coverage and caveats
- Evidence index
- Report integrity
- Relevant user-openable links in item sections and evidence-index rows

The management PDF should instead read like a brief:

- project state narrative
- main themes or deltas since the cursor
- work completed / deployed
- client or stakeholder signals
- risks, blockers, and open questions
- recommended next actions
- plain-language source coverage notes
- concrete source/resource links where useful

The PDF should aggregate details into a coherent story. It should not list every
small event, every evidence ID, or the full evidence index.

Keep detailed PDF presentation rules in `references/management-pdf-brief.md`.

## Validation

After writing the report:

```bash
python3 -m pip install --target .python-deps -r requirements.txt
PYTHONPATH=.python-deps python3 -m py_compile scripts/project_intel.py
PYTHONPATH=.python-deps python3 scripts/project_intel.py validate-synthesis data/projects/<Project-tag>/synthesis/<run-id>_synthesis.json
test -s data/reports/<Project-tag>/<YYYY-MM-DD>/<run-id>_state-of-project.pdf
test -s data/reports/<Project-tag>/<YYYY-MM-DD>/<run-id>_state-of-project.preview.png
```

Open or inspect the preview PNG before calling the PDF complete. The preview
must show the actual report content, not a browser error page, blank page,
access-denied page, or renderer diagnostic output.
The preview must be rendered from the actual PDF page, not from the source HTML
or a browser PDF-viewer screenshot.
Check that the PDF reads as a management brief rather than an agent audit log.

If the PDF renderer fails, keep the canonical JSON/Markdown and surface the
rendering failure. Do not treat a missing PDF as a completed report when the
user asked for a PDF.
