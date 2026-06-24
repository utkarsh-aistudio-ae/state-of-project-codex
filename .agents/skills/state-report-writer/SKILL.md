---
name: state-report-writer
description: Turn completed Project Intel synthesis artifacts into management-ready state-of-project reports and PDF derivatives. Use when Codex needs to produce, review, or rerender a state report from Project Intel synthesis JSON, write canonical report JSON/Markdown under data/reports, render a PDF, or check report presentation without redoing synthesis reasoning.
---

# State Report Writer

Use this skill after `project-state-synthesizer` has produced a completed and
validated synthesis artifact.

The synthesizer owns reasoning. The report writer owns presentation,
readability, source visibility, caveats, review sections, and derivative PDF
rendering.

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
   ```

4. Treat JSON and Markdown as canonical. Treat HTML and PDF as derivatives.
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
- Keep the report readable for AiStudio management: lead with the executive
  state, shipped/deployed work, client signals, risks, review items, and source
  coverage.
- Do not hide skipped, planned, unavailable, or stale sources.
- Do not include raw source transcript/email blocks in the management report.
  Cite evidence IDs and source file references instead.

## Expected Sections

The canonical Markdown should include:

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

## Validation

After writing the report:

```bash
python3 -m py_compile scripts/project_intel.py
python3 scripts/project_intel.py validate-synthesis data/projects/<Project-tag>/synthesis/<run-id>_synthesis.json
test -s data/reports/<Project-tag>/<YYYY-MM-DD>/<run-id>_state-of-project.pdf
```

If the PDF renderer fails, keep the canonical JSON/Markdown and surface the
rendering failure. Do not treat a missing PDF as a completed report when the
user asked for a PDF.
