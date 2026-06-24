# Runtime State

Last updated: 2026-06-23

This file documents the filesystem-only runtime state model for the current
Project Intel prototype.

The external scheduler triggers shared data fetches and, separately, named
project report runs. Project Intel does not own the schedule yet. The
scheduled-run metadata contract is documented in
`data/registry/scheduled-run-contract.md`.

```bash
python3 scripts/project_intel.py run-data-fetch
python3 scripts/project_intel.py run-state-report <Project-tag>
```

## Cursors

Source cursors and per-project report cursors live under private runtime state:

```text
state/cursors/data-fetch/<source>.json
state/cursors/<Project-tag>/report.json
```

Source cursors and report cursors are separate.

- Source cursors advance after a source fetch succeeds and untouched logs are
  safely written.
- Source cursors may advance even when the later tagging worklist blocks report
  generation; the source data has been captured, while tagging remains a
  separate lifecycle stage.
- Broad shared datasources such as Gmail, Fireflies, and future chat readers
  must not be fetched once per project during reporting. One conversation can
  contain evidence for many projects.
- Some source entities are naturally project-scoped, such as GitHub repos,
  Railway projects, Vercel projects, Notion spaces/page trees, deployment
  environments, or client-specific Drive folders. Those may be discovered from
  project profiles and fetched per source entity.
- Source cursors maintain `seen_keys` so readers can reuse the same untouched
  source-log path for an already-seen artifact or source entity instead of
  creating duplicate files and duplicate tagging work.
- The report cursor advances only after the tagging worklist is clear,
  validation passes, extraction succeeds, and report generation succeeds.
- Source fetches should use a lookback overlap, such as 48 hours, to catch late
  updates and edited threads.

Example source cursor:

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
window.

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
- registry hash
- tagged file metadata
- validation state

This keeps queue state reproducible after restart. A persistent queue, cache,
index, database, vector store, or service is a future architecture decision.

The tagging worklist is source-artifact scoped. Some artifacts are broad shared
conversations; others are project-scoped source entities. In both cases, tagging
must process only items where `work_required: true`; `current` items are
skipped. The effective tagging cursor is the tagged file metadata:

- `source_content_hash`
- `registry_hash`
- `tag_status`
- `annotation_count`
- `uncertain_annotation_count`

This means a source artifact or project-scoped source entity is retagged only
when the source content changed, the project registry changed, a tagged copy is
missing/prepared, or the tagger marked the file failed or in need of review.
Project reports must not create separate duplicate tagging passes for source
artifacts that are already current.

Prepared tagged files use `tag_status: "prepared"` and remain in the derived
worklist as `needs_tagging` until Codex adds canonical annotations and reruns the
deterministic tag metadata command.

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
status, tagging worklist status, validation, extraction, report path, cursor
updates, source status counts, trigger source, start/end timestamps, duration,
mutation flag, external delivery flag, warnings, and errors.
