# Scheduled Run Contract

Last updated: 2026-06-23

Project Intel does not own scheduling yet. An external scheduler triggers a
named project run:

```bash
python3 scripts/project_intel.py run-project <Project-tag>
```

This file defines the metadata every future scheduled job must provide or make
recoverable from configuration.

## Required Job Definition

Every scheduled `state-of-project` job should define:

- owner
- job name
- schedule
- timezone
- project tag
- source-family scope
- report window policy
- destination for reports or notifications
- mutation behavior
- skip rules
- failure notification path
- cursor behavior
- audit output path

## Current Manual Equivalent

The current CLI assumes:

- owner: user running the command
- trigger source: `manual_cli`
- project tag: command argument
- source-family scope: `default_project_run` entries from
  `data/registry/source-families.yaml`
- mutation behavior: no external writes
- external delivery: none
- failure notification: command output plus run manifest
- audit output: `logs/runs/<run-id>/manifest.json`

## Cursor Rules

- Source cursors advance only after a source fetch succeeds and untouched logs
  are safely written.
- The report cursor advances only when source coverage is acceptable, the
  derived tagging worklist is clear, validation passes, extraction succeeds,
  and report generation succeeds.
- Runs with skipped source readers may write private reports and manifests, but
  must not advance the report cursor.

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
