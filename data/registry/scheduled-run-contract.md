# Scheduled Run Contract

Last updated: 2026-06-23

Project Intel does not own scheduling yet. An external scheduler triggers shared
data fetches and project-specific report runs:

```bash
python3 scripts/project_intel.py run-data-fetch
python3 scripts/project_intel.py run-state-report <Project-tag>
```

This file defines the metadata every future scheduled job must provide or make
recoverable from configuration.

## Required Job Definition

Every scheduled `run-data-fetch` job should define:

- owner
- job name
- schedule
- timezone
- source-family scope
- mutation behavior
- skip rules
- failure notification path
- source cursor behavior
- audit output path

Every scheduled `run-state-report` job should define:

- owner
- job name
- schedule or upstream dependency
- timezone
- project tag
- report window policy
- destination for reports or notifications
- mutation behavior
- skip rules
- failure notification path
- report cursor behavior
- audit output path

## Current Manual Equivalent

The current CLI assumes:

- owner: user running the command
- trigger source: `manual_cli`
- source-family scope: `default_data_fetch` entries from
  `data/registry/source-families.yaml`
- project tag: command argument for `run-state-report`
- mutation behavior: no external writes
- external delivery: none
- failure notification: command output plus run manifest
- audit output: `logs/runs/<run-id>/manifest.json`

## Cursor Rules

- Source cursors advance only after a source fetch succeeds and untouched logs
  are safely written.
- Source cursors are scoped to shared data-fetch source families, not individual
  project reports.
- Tagging is scoped to source artifacts, not individual project reports. The
  derived worklist and tagged metadata decide whether tagging work is required.
- The report cursor advances only when the derived tagging worklist is clear,
  validation passes, extraction succeeds, and report generation succeeds.
- Runs with skipped source readers may write private data-fetch manifests; the
  report stage should preserve source coverage warnings rather than pretending
  missing sources were checked.

## Skip Rules

Valid skip reasons include:

- reader not implemented
- source unavailable
- missing credentials
- missing stable project/source identifier
- no material source window
- validation failed
- tagging required
- confidence too low for external delivery
- mutation not approved

Skipping must be explicit in the manifest. A skipped source must not be reported
as checked.
