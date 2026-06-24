# State Of Project Nightly

Last updated: 2026-06-24

This is the current orchestration recipe for cursor-governed data capture plus
one named project report. It is not a navigator. It exists because there is
currently one primary workflow family and its skills/tools are local to this
workflow.

## Purpose

Discover likely project-linked resources, capture source data once per relevant
cursor window/entity, tag only cursor-selected source artifacts that need work,
then produce a private state-of-project report for one canonical project tag
using the filesystem-first Project Intel contracts.

## Trigger

An external scheduler or a human runs data ingestion:

```bash
python3 scripts/project_intel.py run-data-fetch
```

Project-specific reporting runs after the relevant source logs are fetched and
tagged:

```bash
python3 scripts/project_intel.py synthesize-project-state <Project-tag>
python3 scripts/project_intel.py write-state-report <Project-tag>
```

The scheduler owns timing. Project Intel owns the run contract, fetch cursors,
tagging cursors, report cursors, manifests, source coverage, validation,
extraction, and private artifacts.

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
- `project-state-synthesizer`: Codex judgment for source-backed project state
- `state-report-writer`: report presentation and PDF derivative rendering
- `capture-project-intel-teachings`: durable workflow learning

Future concepts:

- `project-resource-discoverer`: wide-net discovery for repos, deployments, and
  other project-linked source entities

## Ordered Steps

1. Load source-family cursor policy and active project profiles.
2. For project-linked source families, run resource discovery/reconciliation
   across provider inventories such as GitHub repos, Vercel projects, Railway
   projects, deployment environments, and later Drive/Notion project areas.
   High-confidence resources may be added to the local project-linked resource
   list with evidence when policy allows it; uncertain resources become review
   items and must be mentioned in the report.
3. Compute fetch windows from filesystem cursors: source-linked for broad
   shared datasources, project-linked for project-specific source entities, and
   entity-dependent for mixed sources.
4. Run implemented source readers. GitHub and Gmail are currently implemented.
   Gmail is broad shared-source ingestion; GitHub is project-profile-driven
   source-entity ingestion. Source-entity readers must reuse stable source
   paths for the same entity/activity bucket instead of creating new files from
   fetch time alone. Fireflies batch discovery, Drive, and
   deployment-provider-specific readers remain source coverage gaps until their
   readers exist.
5. Build the derived source-artifact tagging worklist from the cursor-selected
   candidate set, untouched/tagged files, source hashes, registry state, and
   tagger metadata.
6. If worklist items need tagging, run `project-tagger` only on items where
   `work_required: true`; skip `current` items. Tagging may operate on broad
   shared artifacts or project-scoped source entities. For existing registry
   projects, shared-resource tagging is source-linked. For a newly added
   canonical project, shared-resource tagging uses the default seven-day
   lookback. For project-specific resources, tagging is project-linked.
7. Confirm the report project tag exists and is active.
8. Validate tagged logs.
9. Extract tagged evidence records.
10. Filter evidence to the project and report window.
11. Run `python3 scripts/project_intel.py synthesize-project-state
    <Project-tag>` to prepare the private synthesis evidence pack and draft.
12. Run `project-state-synthesizer` to fill the synthesis reasoning from
    confirmed evidence and route uncertain evidence to review sections.
13. Run `state-report-writer`, usually via `python3 scripts/project_intel.py
    write-state-report <Project-tag>`, to write canonical report JSON/Markdown
    and render HTML/PDF derivatives.
14. Write manifest.
15. Advance resource-discovery cursors after successful discovery; advance fetch
    cursors after successful source fetches; advance tagging
    cursors after successful tagging for their selected candidate set; advance
    report cursor only when the report stage succeeds.

## Branches

- If a source reader is not implemented, mark it `skipped`; do not pretend it
  was checked.
- If source coverage gaps exist, record them in the data-fetch manifest.
- If resource discovery finds uncertain project-linked candidates, keep them out
  of canonical evidence, write review items, and include them in the report.
- If tagging is required, stop report generation before validation/extraction
  until the cursor-selected tagging worklist is current.
- If validation fails, stop before extraction/reporting.
- If uncertain evidence exists, include it in review sections; do not use it as
  authoritative source for timeline entries or tickets.

## Output Shape

Current private outputs:

```text
logs/runs/<run-id>/manifest.json
data/reports/<Project-tag>/<YYYY-MM-DD>/<run-id>_state-of-project.md
data/derived/tagged-notes.jsonl
data/derived/review/project-resource-candidates.jsonl
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
- Do not use fetch-time-only filenames as source identity for project-linked
  source entities such as GitHub repos.
- Do not let a global source cursor cause a newly added project to miss its
  default initial window for project-specific resources.
- Do not silently auto-link project resources unless the source-family policy
  allows high-confidence auto-linking and the manifest records why.
- Do not create tickets, send emails, post messages, update deployments, or push
  code from this workflow.
- Do not commit private runtime artifacts.
- Do not treat skipped sources as checked sources.
