# State Of Project Nightly

Last updated: 2026-06-23

This is the current orchestration recipe for shared data capture plus one named
project report. It is not a navigator. It exists because there is currently one
primary workflow family and its skills/tools are local to this workflow.

## Purpose

Capture shared source data once per source window, then produce a private
state-of-project report for one canonical project tag using the
filesystem-first Project Intel contracts.

## Trigger

An external scheduler or a human runs shared ingestion once:

```bash
python3 scripts/project_intel.py run-data-fetch
```

Project-specific reporting runs after shared source logs are fetched and tagged:

```bash
python3 scripts/project_intel.py run-state-report <Project-tag>
```

The scheduler owns timing. Project Intel owns the run contract, source cursors,
report cursors, manifests, source coverage, validation, extraction, and private
artifacts.

## Sources And Contracts

Primary contracts:

- `data/registry/project-tags.yaml`
- `data/registry/source-families.yaml`
- `data/registry/filesystem-layout.md`
- `data/registry/runtime-state.md`
- `data/registry/annotation-syntax.md`
- `data/registry/reporting-contract.md`
- `data/registry/scheduled-run-contract.md`

Current skills:

- `run-state-of-project`: conductor for the current workflow
- `project-tagger`: Codex judgment for project annotations
- `capture-project-intel-teachings`: durable workflow learning

Future concepts:

- `project-state-synthesizer`: reasoning and chronology
- `state-report-writer`: report presentation
- PDF renderer: derivative artifact generation

## Ordered Steps

1. Compute shared source fetch windows from filesystem cursors.
2. Build the data-fetch plan from `source-families.yaml`.
3. Run implemented source readers. GitHub and Gmail are currently implemented;
   Fireflies batch discovery, Drive, and deployment-provider-specific readers
   remain source coverage gaps until their readers exist.
4. Build the derived tagging worklist from untouched/tagged files, source
   hashes, registry hash, and tagger metadata.
5. If worklist items need tagging, run `project-tagger` before reporting.
6. Confirm the report project tag exists and is active.
7. Validate tagged logs.
8. Extract tagged evidence records.
9. Filter evidence to the project and report window.
10. Current skeleton: write private placeholder report.
11. Future: run `project-state-synthesizer`, then `state-report-writer`, then
    PDF rendering.
12. Write manifest.
13. Advance source cursors after successful source fetches; advance report
    cursor only when the report stage succeeds.

## Branches

- If a source reader is not implemented, mark it `skipped`; do not pretend it
  was checked.
- If source coverage gaps exist, record them in the data-fetch manifest.
- If tagging is required, stop report generation before validation/extraction.
- If validation fails, stop before extraction/reporting.
- If uncertain evidence exists, include it in review sections; do not use it as
  authoritative source for timeline entries or tickets.

## Output Shape

Current private outputs:

```text
logs/runs/<run-id>/manifest.json
data/reports/<Project-tag>/<YYYY-MM-DD>/<run-id>_state-of-project.md
data/derived/tagged-notes.jsonl
```

Future canonical outputs:

```text
data/projects/<Project-tag>/synthesis/<run-id>_synthesis.json
data/reports/<Project-tag>/<YYYY-MM-DD>/<run-id>_state-of-project.json
data/reports/<Project-tag>/<YYYY-MM-DD>/<run-id>_state-of-project.md
data/reports/<Project-tag>/<YYYY-MM-DD>/<run-id>_state-of-project.pdf
```

## Guardrails

- Do not introduce a navigator until there are multiple workflows with routing
  ambiguity.
- Do not create a durable queue in the current filesystem-first prototype.
- Do not fetch shared datasources once per project report.
- Do not create tickets, send emails, post messages, update deployments, or push
  code from this workflow.
- Do not commit private runtime artifacts.
- Do not treat skipped sources as checked sources.
