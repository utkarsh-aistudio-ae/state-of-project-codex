---
name: run-state-of-project
description: Run the Project Intel filesystem-first state-of-project workflow. Use when Codex needs to execute or review data fetches, project-specific report runs, tagging worklists, validation, extraction, report generation, cursors, manifests, and source coverage gaps.
---

# Run State Of Project

Use this skill for the current filesystem-first state-of-project workflow. The
external scheduler chooses when to run data fetches and when to generate
project-specific reports.

Codex owns intelligent steps such as tagging and report judgment. Deterministic
scripts own paths, hashes, cursors, validation, extraction, manifests, and
private report files.

Before changing the workflow shape, read the orchestration recipe:

```text
orchestrations/state-of-project-nightly.md
```

## Workflow

1. Run source ingestion for the cursor-selected windows:

   ```bash
   python3 scripts/project_intel.py run-data-fetch
   ```

   Shared datasources use source-linked fetch cursors. Project-specific source
   entities use project-linked fetch cursors. Before project-linked source
   fetches, run resource discovery/reconciliation where supported so new likely
   repos, deployments, environments, or folders are not missed.
2. For project-linked source families, treat high-confidence discovered
   resources as local project profile/resource updates only when the
   source-family policy allows auto-linking and the evidence is recorded.
   Uncertain discovered resources become review items and report material, not
   canonical project evidence.
3. If the derived worklist has non-current items, run the `project-tagger` skill
   on the blocking untouched logs listed by `queue` or the manifest. Tagging is
   source-artifact/source-entity work with cursor ownership: source-linked for
   shared resources and existing projects, seven-day shared-resource lookback
   for newly added projects, and project-linked for project-specific resources.
   Process only items with `work_required: true` and skip `current` items.
4. Confirm the project tag exists in `data/registry/project-tags.yaml`.
5. Run:

   ```bash
   python3 scripts/project_intel.py synthesize-project-state <Project-tag>
   ```

6. If the synthesis command exits with `tagging_required`, run
   `project-tagger` on the blocking stale/missing/prepared/failed logs, then
   rerun synthesis. If only `needs_review` remains, synthesis may proceed but
   uncertain records must stay review-only.
7. Run `project-state-synthesizer` on the generated private synthesis artifacts
   under `data/projects/<Project-tag>/synthesis/...`.
8. Until `state-report-writer` exists, the current placeholder report can be
   generated with:

   ```bash
   python3 scripts/project_intel.py run-state-report <Project-tag>
   ```

9. If the report command exits with `tagging_required`, run `project-tagger` on
   the blocking untouched logs, then rerun `run-state-report`.
10. If validation fails, inspect the validation report and repair tagged logs
   without editing untouched logs.
11. If the run succeeds, review the generated private report under
   `data/reports/<Project-tag>/...` and the manifest under `logs/runs/...`.

## Current Behavior

The current deterministic CLI separates data fetching from project-specific
reporting. `run-data-fetch` reads default data-fetch sources from
`data/registry/source-families.yaml`, computes cursor-selected fetch windows,
runs implemented source readers, and records source coverage gaps for
unavailable or not-yet-implemented readers. `run-state-report <Project-tag>`
validates/extracts already-tagged evidence and writes the project-specific
private report.

Current implemented batch readers:

- GitHub: uses active project repo profiles from
  `data/registry/project-tags.yaml` as project-scoped source entities and reader
  limits from `data/registry/source-families.yaml`; fetch cursors are
  project-linked, and repo activity logs use stable source-entity paths instead
  of fetch-time filenames.
- Gmail: uses project aliases, strong signals, and reader settings from the
  registries as discovery signals, dedupes matching thread IDs, and fetches
  full sanitized threads once per shared source window.

Current skipped source gaps:

- Fireflies batch discovery, because only single-transcript fetch exists.
- Drive.
- Deployment-provider-specific readers.
- Wide-net project resource discovery for GitHub repos and deployment provider
  projects is planned; current GitHub fetches only repos already listed in the
  active project profile.

The `queue` command is a derived filesystem worklist, not a durable queue. The
synthesis command writes private prepared synthesis artifacts and does not
advance the report cursor. The report cursor advances only after the report
stage succeeds.

Tagging uses cursor-selected candidate sets plus source content hashes and
registry state as its per-artifact proof of currency. It should not run once per
project report, and it should not duplicate work for source artifacts or
project-scoped source entities that are already current. A source artifact is
retagged only when it is inside the relevant cursor window and its source hash
changes, relevant registry state changes, the tagged copy is missing/prepared,
or the tagger explicitly marked the file failed or in need of review.

## Safety

- Do not send emails, create GitHub issues, open PRs, update deployments, or
  write to external services during this workflow.
- Treat generated reports and source logs as private runtime artifacts.
- Do not commit `state/`, `logs/`, `data/raw/`, `data/derived/`, or
  `data/reports/`.
- Do not resolve long-term orchestration architecture inside this skill. If the
  workflow needs a database, persistent queue, scheduler, review UI, service, or
  MCP boundary, surface that as an architecture question.
