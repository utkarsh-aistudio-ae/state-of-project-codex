# Source Families

Last updated: 2026-06-23

This file explains the source-family registry in
`data/registry/source-families.yaml`.

The YAML file is the machine-readable contract. This Markdown file is the
human-facing source map for readers, taggers, synthesizers, and report writers.

## Purpose

Project Intel should not hardcode source families inside generic scripts when a
filesystem contract can describe them. Source-family metadata records:

- whether a source participates in default shared data-fetch runs
- current reader implementation status
- cursor scope and lookback policy
- stable source entity key, when the source is naturally split into repos,
  projects, folders, threads, environments, or similar objects
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

## Cursor Scope

Use these labels:

- `shared_source`: broad datasource stream where one artifact can contain
  evidence for many projects, such as Gmail threads, Fireflies transcripts, or
  Slack threads.
- `source_entity`: named datasource entity that often comes from a project
  profile, such as a GitHub repo, Railway project, Vercel project, Notion
  workspace/page tree, or deployment environment.
- `mixed_source`: source family may contain both shared artifacts and
  project-scoped entities, such as Drive folders and files.

Project-scoped source entities are valid. They should be fetched and tagged for
the relevant source entity, but not repeatedly for every report run. The stable
entity key, such as repo name or provider project id, is the dedupe boundary.

## Reader Status

Use these values:

- `planned`: no reader is implemented yet
- `single_fetch_only`: one-off fetch exists, but batch cursor fetch is not wired
- `implemented`: reader can participate in `run-data-fetch`
- `unavailable`: source is known but credentials/tooling are unavailable
- `disabled`: source exists but is intentionally excluded

## Current Default Data-Fetch Sources

`run-data-fetch` reads `source-families.yaml` and includes sources where
`default_data_fetch: true`.

Current default sources:

- GitHub (`implemented`)
- Gmail (`implemented`)
- Fireflies
- Drive
- Deployments

GitHub and Gmail are implemented as registry-driven batch readers. They use
project profiles from `data/registry/project-tags.yaml` as discovery signals and
reader settings from `source-families.yaml`; generic reader code must not
hardcode a project name, repo, email subject, account, or keyword.

Fireflies still has only single-transcript fetch support. Drive and deployment
readers are planned. Skipped sources must remain visible in run manifests and
reports as source coverage gaps.

## Contract Rules

- Readers write untouched logs only.
- Tagging belongs to `project-tagger`.
- Source family membership does not imply project ownership.
- Fetch context such as `fetch_context.project_candidates` is not a project
  annotation; it only records why the reader pulled the source log.
- Broad shared datasources must be fetched once per source window, not once per
  project report. Tagging and extraction decide which blocks matter to which
  project.
- Named/project-shaped datasources such as GitHub repos, Railway projects,
  Vercel projects, or Notion spaces may be fetched from project profiles, but
  should still reuse stable source entity identities and cursor `seen_keys` so
  the same entity is not fetched or tagged repeatedly for multiple reports.
- Source status must be recorded in run manifests.
- A skipped source is not the same as a source with no data.
- Presentation surfaces can provide pointers, but canonical backing sources
  should provide evidence.
