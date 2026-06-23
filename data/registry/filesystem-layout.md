# Filesystem Layout

Last updated: 2026-06-23

This file is the source of truth for Project Intel source-log storage.

Project Intel uses source logs as the primary object. Readers write untouched
source logs only. The tagger creates or updates editable tagged copies.

```text
data/
  raw/
    untouched/
      <Source-name>/
        <YYYY-MM>/
          <YYYY-MM-DD>/
            <conversation-or-log-id>_<timestamp>.md
    tagged/
      <Source-name>/
        <YYYY-MM>/
          <YYYY-MM-DD>/
            <conversation-or-log-id>_<timestamp>.md
```

## Rules

- Readers write untouched logs only.
- Tagged logs are editable copies created or updated by the tagger.
- A tagged file's existence means the tagger has claimed or processed that
  source log, not merely that the source is waiting for tags.
- The tagger edits only `data/raw/tagged/...`.
- Untouched logs should remain stable for audit and reprocessing.
- Queue state is derived from untouched files, tagged files, source hashes, and
  registry metadata. It should be reproducible without in-memory state.
- Use ISO date folders: `YYYY-MM` and `YYYY-MM-DD`.
- The timestamp in the filename should come from source occurrence time where
  possible.
- Use UTC `HHMM` in filenames unless a better source-local convention is
  explicitly needed.
- Source logs and derived artifacts stay inside this private automation
  workspace.
- Do not copy raw credentials, tokens, or private auth material into source
  logs, tags, derived records, manifests, reports, or registry files.
- Commit only sanitized reproducible code, contracts, plans, and docs. Do not
  commit private source logs, auth material, downloaded state, runtime logs, or
  derived records with private content.
- Early Project Intel phases are external read-only. Do not send emails, create
  issues, update deployments, or write to external services without explicit
  human approval.

## Examples

```text
data/raw/untouched/Fireflies/2026-06/2026-06-17/transcript_01KV7H2GX5ACK0J3T8W5K1WHD2_1000.md
data/raw/tagged/Fireflies/2026-06/2026-06-17/transcript_01KV7H2GX5ACK0J3T8W5K1WHD2_1000.md

data/raw/untouched/Gmail/2026-06/2026-06-22/thread_19eef41d92cf4e40_1500.md
data/raw/tagged/Gmail/2026-06/2026-06-22/thread_19eef41d92cf4e40_1500.md
```

## Retagging Policy

When a new canonical project is added to the registry, retag all source logs
from the last seven days by default. Older backfill is explicit and can be
requested later by date range or project.

When an existing project profile changes materially, retag the last seven days,
files already tagged or uncertain for that project, and any files manually
selected for review.
