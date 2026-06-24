# Runtime State

Last updated: 2026-06-24

This file documents the filesystem-only runtime state model for the current
Project Intel prototype.

The external scheduler triggers data-fetch runs and, separately, named project
report runs. Project Intel does not own the schedule yet. The
scheduled-run metadata contract is documented in
`data/registry/scheduled-run-contract.md`.

```bash
python3 scripts/project_intel.py run-data-fetch
python3 scripts/project_intel.py run-state-report <Project-tag>
```

## Cursors

Fetch cursors, tagging cursors, and per-project report cursors live under
private runtime state:

```text
state/cursors/resource-discovery/projects/<Project-tag>/<Source>.json
state/cursors/data-fetch/sources/<Source>.json
state/cursors/data-fetch/projects/<Project-tag>/<Source>.json
state/cursors/tagging/sources/<Source>.json
state/cursors/tagging/projects/<Project-tag>/<Source>.json
state/cursors/<Project-tag>/report.json
```

The current prototype still has some legacy source cursor paths and uses tagged
file metadata as the immediate tagging cursor. The target contract is explicit
cursor ownership by source family and project context.

- Fetch cursors advance after a source fetch succeeds and untouched logs are
  safely written.
- Fetch cursors may advance even when later tagging blocks report generation;
  the source data has been captured, while tagging remains a separate lifecycle
  stage.
- Broad shared datasources such as Gmail, Fireflies, and future chat readers
  use source-linked fetch cursors. One conversation can contain evidence for
  many projects, so shared source capture must not run once per project report.
- Some source entities are naturally project-scoped, such as GitHub repos,
  Railway projects, Vercel projects, Notion spaces/page trees, deployment
  environments, or client-specific Drive folders. Those use project-linked
  fetch cursors so a newly added project gets its own initial fetch window
  instead of inheriting an old global source cursor.
- Before project-linked fetch cursors run, project-resource discovery cursors
  can scan provider inventory for new repos, deployments, environments, folders,
  or similar source entities that may belong to the project.
- Project-linked fetch cursors should still maintain stable source entity keys
  and `seen_keys` so readers can reuse an already-seen untouched source-log path
  instead of creating duplicate files and duplicate tagging work.
- For shared resources and projects already present in the registry, tagging
  cursors are source-linked. Current tagged metadata prevents repeated LLM work
  across project report runs.
- When a new canonical project is added, the shared-resource tagging cursor for
  that project starts at `run_started_at - 7 days` by default. Older historical
  retagging is an explicit backfill by date range, source, or project.
- For project-specific resources, tagging cursors are project-linked.
- The report cursor advances only after the tagging worklist is clear,
  validation passes, extraction succeeds, and report generation succeeds.
- Fetches should use a lookback overlap, such as 48 hours, to catch late
  updates and edited threads.

Example source-linked fetch cursor:

```json
{
  "scope": "data-fetch",
  "source": "Gmail",
  "last_successful_fetch_at": "2026-06-23T00:00:00Z",
  "lookback_overlap_hours": 48,
  "seen_keys": {
    "<gmail-thread-id>": {
      "source_id": "<gmail-thread-id>",
      "path": "data/raw/untouched/Gmail/2026-06/2026-06-23/thread_<gmail-thread-id>_0900.md",
      "content_hash": "sha256:...",
      "occurred_at": "2026-06-23T09:00:00Z",
      "seen_at": "2026-06-23T20:00:00Z"
    }
  }
}
```

Example project-linked fetch cursor:

```json
{
  "scope": "data-fetch",
  "source": "GitHub",
  "project": "Argos-ddt",
  "last_successful_fetch_at": "2026-06-23T00:00:00Z",
  "lookback_overlap_hours": 48,
  "seen_keys": {
    "aistudioae/argos-ddt-prod": {
      "source_id": "aistudioae/argos-ddt-prod",
      "path": "data/raw/untouched/GitHub/2026-06/2026-06-23/repo_aistudioae__argos-ddt-prod_activity.md",
      "content_hash": "sha256:...",
      "occurred_at": "2026-06-23T00:00:00Z",
      "seen_at": "2026-06-23T20:00:00Z"
    }
  }
}
```

Example project-resource discovery cursor:

```json
{
  "scope": "resource-discovery",
  "source": "GitHub",
  "project": "Argos-ddt",
  "last_successful_discovery_at": "2026-06-23T00:00:00Z",
  "inventory_cursor": "provider-specific-page-or-timestamp",
  "seen_candidate_keys": {
    "aistudioae/argos-ddt-prod": {
      "source_entity_id": "aistudioae/argos-ddt-prod",
      "decision": "linked",
      "confidence": "high",
      "seen_at": "2026-06-23T20:00:00Z"
    }
  }
}
```

Example project-linked tagging cursor for a newly added project:

```json
{
  "scope": "tagging",
  "project": "New-project",
  "source_scope": "shared_resources",
  "cursor_reason": "new_canonical_project",
  "tagging_start": "2026-06-17T00:00:00Z",
  "tagging_end": "2026-06-24T00:00:00Z"
}
```

Example report cursor:

```json
{
  "project": "Argos-ddt",
  "last_successful_report_at": "2026-06-23T00:00:00Z",
  "last_run_id": "20260623T000000Z"
}
```

## Windows

For source fetches:

```text
fetch_start = last_successful_fetch_at - lookback_overlap
fetch_end = run_started_at
```

If a source has no cursor yet, use the previous seven days as the initial
window. If a project-linked source cursor has no cursor for that project, use
the previous seven days even when another project has already fetched the same
source family.

For project-resource discovery:

```text
discovery_start = last_successful_discovery_at - lookback_overlap
discovery_end = run_started_at
```

Discovery may also use provider inventory pagination cursors when timestamp
windows are not enough. The result is not source evidence by itself; it is a
project-resource reconciliation signal.

For reports:

```text
report_start = max(last_successful_report_at, run_started_at - 7 days)
report_end = run_started_at
```

## Worklists

There is no separate durable queue in the current filesystem-first prototype.
The `queue` command exposes a derived tagging worklist. The worklist is derived
from:

- `data/raw/untouched/...`
- `data/raw/tagged/...`
- source content hashes
- semantic registry state
- tagged file metadata
- validation state

This keeps queue state reproducible after restart. A persistent queue, cache,
index, database, vector store, or service is a future architecture decision.

The tagging worklist is source-artifact scoped. Some artifacts are broad shared
conversations; others are project-scoped source entities. In both cases, tagging
must process only items where `work_required: true`; `current` items are
skipped. Cursor policy chooses which artifacts/entities are candidates:

- source-linked tagging cursor for shared resources and existing registry
  projects
- seven-day project-linked shared-resource cursor for a newly added project
- project-linked tagging cursor for project-specific source entities

The tagged file metadata remains the per-file proof of currency:

- `source_content_hash`
- `registry_state_version`
- `registry_active_project_tags`
- `registry_active_project_tags_hash`
- `registry_relevant_project_hashes`
- `registry_relevant_special_hashes`
- `tag_status`
- `annotation_count`
- `uncertain_annotation_count`

This means a source artifact or project-scoped source entity is retagged only
when it falls inside the cursor-selected candidate set and the source content
changed, relevant registry state changed, a tagged copy is missing/prepared, or
the tagger marked the file failed or in need of review. Project reports must not
create duplicate tagging passes for artifacts that are already current.

The whole-file `project-tags.yaml` hash is retained only as a legacy/audit
field. Queue decisions use semantic registry state:

- `new_project_added`: shared-source candidates are selected only inside the
  default seven-day tagging window unless an explicit backfill is requested;
  project-linked sources use project-linked candidates.
- `project_profile_changed`: only files relevant to that project are stale,
  including files tagged or uncertain for that project, source logs selected by
  that project's cursor, or manually selected files.
- `special_tag_changed`: only files using the changed special tag are stale.
- unrelated registry metadata changes do not make all tagged files stale.

Existing tagged files with only legacy `registry_hash` remain backward
compatible. They are not forced stale solely because the whole registry hash
changes; rerunning the tag command upgrades them to semantic registry metadata.

Prepared tagged files use `tag_status: "prepared"` and remain in the derived
worklist as `needs_tagging` until Codex adds canonical annotations and reruns the
deterministic tag metadata command.

## Project Resource Candidates

Nightly discovery for project-linked sources may find resources not yet listed
in the project profile.

High-confidence candidates may be added to the local project-linked resource
list when source-family policy allows auto-linking. The run manifest must record
the resource id, source reference, matched signals, confidence, reason, and the
profile/registry update performed.

Uncertain candidates must be written to private review state and surfaced in
the project report:

```text
data/derived/review/project-resource-candidates.jsonl
```

Uncertain candidates are not canonical evidence, should not create timeline
entries or tickets, and should not cause project-linked fetch/tag cursors to run
as if the resource were confirmed.

## Reports

Generated reports are private runtime artifacts:

```text
data/reports/<Project-tag>/<YYYY-MM-DD>/<run-id>_state-of-project.md
```

Reports must cite extracted evidence records and list source coverage gaps.
They are ignored by git.

## Run Manifests

Each data-fetch or report run writes a private manifest:

```text
logs/runs/<run-id>/manifest.json
```

The manifest records scope, project when applicable, windows, source fetch
status, resource discovery status, tagging worklist status, validation,
extraction, report path, cursor updates, source status counts, trigger source,
start/end timestamps, duration, mutation flag, external delivery flag, warnings,
and errors.
