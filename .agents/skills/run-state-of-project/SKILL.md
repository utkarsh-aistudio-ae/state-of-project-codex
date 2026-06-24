---
name: run-state-of-project
description: Run the Project Intel filesystem-first state-of-project workflow. Use when Codex needs to execute or review shared data fetches, project-specific report runs, tagging worklists, validation, extraction, report generation, cursors, manifests, and source coverage gaps.
---

# Run State Of Project

Use this skill for the current filesystem-first state-of-project workflow. The
external scheduler chooses when to run shared data fetches and when to generate
project-specific reports.

Codex owns intelligent steps such as tagging and report judgment. Deterministic
scripts own paths, hashes, cursors, validation, extraction, manifests, and
private report files.

Before changing the workflow shape, read the orchestration recipe:

```text
orchestrations/state-of-project-nightly.md
```

## Workflow

1. Run shared source ingestion once for the source window:

   ```bash
   python3 scripts/project_intel.py run-data-fetch
   ```

2. If the derived worklist has non-current items, run the `project-tagger` skill
   on the blocking untouched logs listed by `queue` or the manifest. Tagging is
   source-artifact/source-entity work: process only items with
   `work_required: true` and skip `current` items.
3. Confirm the project tag exists in `data/registry/project-tags.yaml`.
4. Run:

   ```bash
   python3 scripts/project_intel.py run-state-report <Project-tag>
   ```

5. If the report command exits with `tagging_required`, run `project-tagger` on
   the blocking untouched logs, then rerun `run-state-report`.
6. If validation fails, inspect the validation report and repair tagged logs
   without editing untouched logs.
7. If the run succeeds, review the generated private report under
   `data/reports/<Project-tag>/...` and the manifest under `logs/runs/...`.

## Current Behavior

The current deterministic CLI separates shared data fetching from
project-specific reporting. `run-data-fetch` computes shared source fetch
windows, reads default data-fetch sources from
`data/registry/source-families.yaml`, runs implemented source readers, and
records source coverage gaps for unavailable or not-yet-implemented readers.
`run-state-report <Project-tag>` validates/extracts already-tagged evidence and
writes the project-specific private report.

Current implemented batch readers:

- GitHub: uses active project repo profiles from
  `data/registry/project-tags.yaml` as project-scoped source entities and reader
  limits from `data/registry/source-families.yaml`; repos are deduped across
  reports.
- Gmail: uses project aliases, strong signals, and reader settings from the
  registries as discovery signals, dedupes matching thread IDs, and fetches
  full sanitized threads once per shared source window.

Current skipped source gaps:

- Fireflies batch discovery, because only single-transcript fetch exists.
- Drive.
- Deployment-provider-specific readers.

The `queue` command is a derived filesystem worklist, not a durable queue. The
report cursor advances only after the derived worklist is clear, validation
passes, extraction succeeds, and the private report is written.

Tagging uses source content hashes and registry hashes as its per-artifact
cursor. It should not run once per project report, and it should not duplicate
work for source artifacts or project-scoped source entities that are already
current. A source artifact is retagged only when its source hash changes, the
project registry changes, the tagged copy is missing/prepared, or the tagger
explicitly marked the file failed or in need of review.

## Safety

- Do not send emails, create GitHub issues, open PRs, update deployments, or
  write to external services during this workflow.
- Treat generated reports and source logs as private runtime artifacts.
- Do not commit `state/`, `logs/`, `data/raw/`, `data/derived/`, or
  `data/reports/`.
- Do not resolve long-term orchestration architecture inside this skill. If the
  workflow needs a database, persistent queue, scheduler, review UI, service, or
  MCP boundary, surface that as an architecture question.
