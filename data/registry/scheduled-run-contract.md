# Scheduled Run Contract

Last updated: 2026-06-24

Project Intel does not own scheduling yet. An external scheduler triggers
data-fetch runs and project-specific report runs:

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
- project-resource discovery behavior for project-linked sources
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
- Fetch cursor ownership follows the source family contract: source-linked for
  broad shared datasources, project-linked for project-specific source
  entities, and entity-dependent for mixed sources.
- Project-linked source families may run project-resource discovery before
  fetch/tag work. This scans provider inventory for new repos, deployments,
  environments, folders, or similar source entities that may belong to the
  project.
- High-confidence discovered resources may be added to the local project-linked
  resource list only when source-family policy allows it and the run manifest
  records evidence. Uncertain resources must be routed to review and mentioned
  in the report.
- Shared-source fetch cursors are not individual project report cursors.
  Project-linked source cursors are valid for project-specific resources and
  prevent newly added projects from inheriting old global source windows.
- Tagging cursor ownership follows the same source shape with one extra rule:
  shared resources use source-linked tagging cursors for existing registry
  projects, but a newly added canonical project starts with a seven-day
  shared-source retag window by default.
- Tagging is scoped to source artifacts or project-specific source entities, not
  individual report renderings. The derived worklist, cursor-selected candidate
  set, and tagged metadata decide whether tagging work is required.
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
