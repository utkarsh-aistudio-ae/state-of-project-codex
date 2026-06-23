---
name: run-state-of-project
description: Run the Project Intel nightly workflow for one canonical project. Use when Codex needs to execute or review a filesystem-first state-of-project run, coordinate source fetches, tagging worklists, validation, extraction, report generation, cursors, manifests, and source coverage gaps.
---

# Run State Of Project

Use this skill for the current filesystem-first nightly project workflow. The
external scheduler chooses when to run and passes one canonical project tag.

Codex owns intelligent steps such as tagging and report judgment. Deterministic
scripts own paths, hashes, cursors, validation, extraction, manifests, and
private report files.

Before changing the workflow shape, read the orchestration recipe:

```text
orchestrations/state-of-project-nightly.md
```

## Workflow

1. Confirm the project tag exists in `data/registry/project-tags.yaml`.
2. Run:

   ```bash
   python3 scripts/project_intel.py run-project <Project-tag>
   ```

3. If the command exits with `tagging_required`, run the `project-tagger` skill
   on the blocking untouched logs listed in the manifest, then rerun
   `run-project`.
4. If validation fails, inspect the validation report and repair tagged logs
   without editing untouched logs.
5. If the run succeeds, review the generated private report under
   `data/reports/<Project-tag>/...` and the manifest under `logs/runs/...`.

## Current Behavior

The current deterministic CLI computes source fetch windows and report windows,
reads default project sources from `data/registry/source-families.yaml`, runs
implemented source readers, and records source coverage gaps for unavailable or
not-yet-implemented readers.

Current implemented batch readers:

- GitHub: uses project repos from `data/registry/project-tags.yaml` and reader
  limits from `data/registry/source-families.yaml`.
- Gmail: uses project aliases, strong signals, and reader settings from the
  registries to search and fetch full sanitized threads.

Current skipped source gaps:

- Fireflies batch discovery, because only single-transcript fetch exists.
- Drive.
- Deployment-provider-specific readers.

The `queue` command is a derived filesystem worklist, not a durable queue. The
report cursor advances only after source coverage is acceptable, the derived
worklist is clear, validation passes, extraction succeeds, and the private
report is written. With skipped source batch readers, the command may write a
report and manifest but should not advance the report cursor.

## Safety

- Do not send emails, create GitHub issues, open PRs, update deployments, or
  write to external services during this workflow.
- Treat generated reports and source logs as private runtime artifacts.
- Do not commit `state/`, `logs/`, `data/raw/`, `data/derived/`, or
  `data/reports/`.
- Do not resolve long-term orchestration architecture inside this skill. If the
  workflow needs a database, persistent queue, scheduler, review UI, service, or
  MCP boundary, surface that as an architecture question.
