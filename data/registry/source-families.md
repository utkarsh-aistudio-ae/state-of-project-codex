# Source Families

Last updated: 2026-06-23

This file explains the source-family registry in
`data/registry/source-families.yaml`.

The YAML file is the machine-readable contract. This Markdown file is the
human-facing source map for readers, taggers, synthesizers, and report writers.

## Purpose

Project Intel should not hardcode source families inside generic scripts when a
filesystem contract can describe them. Source-family metadata records:

- whether a source participates in default project runs
- current reader implementation status
- cursor scope and lookback policy
- what the source is canonical for
- what the source is not canonical for
- privacy and redaction rules
- why the source is skipped when a reader is not implemented

## Source Classes

Use these labels:

- `canonical`: current source of truth for a specific question
- `derived`: generated from another source
- `historical`: true for past state, not current state
- `presentation`: UI over another source
- `scratch`: temporary analysis output
- `mixed`: contains more than one source class depending on section or object

## Reader Status

Use these values:

- `planned`: no reader is implemented yet
- `single_fetch_only`: one-off fetch exists, but batch cursor fetch is not wired
- `implemented`: reader can participate in `run-project`
- `unavailable`: source is known but credentials/tooling are unavailable
- `disabled`: source exists but is intentionally excluded

## Current Default Project Sources

`run-project` reads `source-families.yaml` and includes sources where
`default_project_run: true`.

Current default sources:

- GitHub
- Gmail
- Fireflies
- Drive
- Deployments

All default batch readers are still skipped until implemented. Skipped sources
must remain visible in run manifests and reports as source coverage gaps.

## Contract Rules

- Readers write untouched logs only.
- Tagging belongs to `project-tagger`.
- Source family membership does not imply project ownership.
- Source status must be recorded in run manifests.
- A skipped source is not the same as a source with no data.
- Presentation surfaces can provide pointers, but canonical backing sources
  should provide evidence.
