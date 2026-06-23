# Filesystem Layout

Last updated: 2026-06-23

This file is the source of truth for Project Intel source-log storage.

Project Intel uses source logs as the primary object. Readers write an untouched
source log first, then create an editable tagged copy. The tagger edits only
tagged logs.

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

- Readers write untouched logs first.
- Tagged logs are editable copies.
- The tagger edits only `data/raw/tagged/...`.
- Untouched logs should remain stable for audit and reprocessing.
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
