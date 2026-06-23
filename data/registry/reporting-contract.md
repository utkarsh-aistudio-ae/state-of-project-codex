# Reporting Contract

Last updated: 2026-06-23

This file defines the boundary between project-state synthesis and report
writing.

## Boundary

`project-state-synthesizer` and `state-report-writer` are separate concepts.

The synthesizer owns reasoning. The report writer owns presentation.

```text
tagged evidence records
-> project-state-synthesizer
-> canonical synthesis markdown/JSON
-> state-report-writer
-> canonical report markdown/JSON
-> PDF renderer later
```

## Project State Synthesizer

Responsibilities:

- consume confirmed extracted evidence records
- include uncertain records only as review signals
- infer chronology across sources
- identify decisions, commitments, blockers, risks, open questions, and shipped
  work
- compare conversations, GitHub activity, deployments, and task state when
  those sources exist
- separate source facts from interpretation
- assign confidence and missing-evidence caveats
- avoid creating authoritative entries from uncertain tags alone

The synthesizer should produce structured synthesis, not a polished management
report.

Suggested output path:

```text
data/projects/<Project-tag>/synthesis/<run-id>_synthesis.json
data/projects/<Project-tag>/synthesis/<run-id>_synthesis.md
```

## State Report Writer

Responsibilities:

- consume synthesis output and source coverage metadata
- produce a human-readable management report
- preserve source windows and confidence
- list source gaps without hiding them
- keep uncertain items in review sections
- avoid adding new factual claims that are not in synthesis or source evidence
- prepare canonical markdown/JSON for later PDF rendering

The report writer should not be responsible for deep chronology inference,
cross-source contradiction detection, or comparing conversation promises to
implemented changes.

Suggested output path:

```text
data/reports/<Project-tag>/<YYYY-MM-DD>/<run-id>_state-of-project.md
data/reports/<Project-tag>/<YYYY-MM-DD>/<run-id>_state-of-project.json
```

PDFs are derivatives and should be rendered later from canonical report
artifacts.

## Current Skeleton

The current `run-state-report` command writes a placeholder private markdown
report directly from extracted records. This is acceptable only as a skeleton.
Before generating management-grade reports, introduce the synthesis boundary
above so the report writer does not become the intelligence layer.
