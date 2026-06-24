# Reporting Contract

Last updated: 2026-06-24

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
- cluster duplicate, overlapping, or derivative evidence into event-level
  claims before writing chronology
- identify decisions, commitments, blockers, risks, open questions, and shipped
  work
- compare conversations, GitHub activity, deployments, and task state when
  those sources exist
- include project-resource discovery outcomes, separating confirmed
  newly-linked resources from uncertain candidate resources
- separate source facts from interpretation
- assign confidence and missing-evidence caveats
- include a compact self-evaluation of evidence faithfulness, chronology,
  cross-source reasoning, uncertainty handling, source coverage honesty, known
  weaknesses, and human-review needs
- avoid creating authoritative entries from uncertain tags alone

The synthesizer should produce structured synthesis, not a polished management
report.

Current deterministic preparation command:

```bash
python3 scripts/project_intel.py synthesize-project-state <Project-tag>
```

The command validates tagged logs, extracts records, filters confirmed and
uncertain evidence to the project report window, writes private prepared
synthesis JSON/Markdown artifacts, and writes a run manifest. It blocks on
stale/missing/prepared/failed tagging work, but lets `needs_review` items
through as review signals so Codex can surface uncertainty without treating it
as fact. It scaffolds `self_evaluation` for Codex to fill during synthesis. It
does not advance the report cursor.

Completed synthesis artifacts should be checked with:

```bash
python3 scripts/project_intel.py validate-synthesis data/projects/<Project-tag>/synthesis/<run-id>_synthesis.json
```

The validator checks completion, self-evaluation scoring, evidence references,
and whether uncertain evidence leaked into authoritative sections. It does not
replace human/Codex judgment about whether the synthesis is insightful.

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
- include uncertain project-resource candidates in a review section with
  confidence, matched signals, source reference, and recommended next action
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
