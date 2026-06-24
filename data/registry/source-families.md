# Source Families

Last updated: 2026-06-24

This file explains the source-family registry in
`data/registry/source-families.yaml`.

The YAML file is the machine-readable contract. This Markdown file is the
human-facing source map for readers, taggers, synthesizers, and report writers.

## Purpose

Project Intel should not hardcode source families inside generic scripts when a
filesystem contract can describe them. Source-family metadata records:

- whether a source participates in default data-fetch runs
- current reader implementation status
- cursor scope, cursor ownership, and lookback policy
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

## Cursor Ownership

Cursor ownership is the rule that prevents double work without forcing all
sources into the same shape.

Fetch cursors:

- `source_linked`: one cursor for a broad shared source family and source
  window. Use for Gmail, Fireflies, Slack, and similar conversation streams.
- `project_linked`: one cursor for a project-specific source family/source
  entity window. Use for repos, deployment provider projects, environments,
  Notion project areas, and similar project-shaped entities.
- `source_or_project_linked_by_entity`: mixed families decide cursor ownership
  from the specific entity. A shared Drive file may be source-linked; a client
  Drive folder may be project-linked.

Tagging cursors:

- For shared resources and projects already in the registry, tagging is
  source-linked. A Gmail thread or Fireflies transcript that is current should
  not be retagged just because another project report runs.
- For a newly added canonical project, the shared-resource tagging cursor starts
  at the previous seven days by default. Older backfill is explicit by date
  range, source, or project.
- For project-specific resources, tagging is project-linked. A repo/deployment
  source entity can be tagged in the project context without forcing every
  shared conversation stream through the same project cursor.

The current prototype still uses tagged-file metadata as the immediate
per-source-log proof of currency. The long-term contract is that cursor policy
chooses the candidate set, and tagged metadata proves whether each candidate is
current.

## Reader Status

Use these values:

- `planned`: no reader is implemented yet
- `single_fetch_only`: one-off fetch exists, but batch cursor fetch is not wired
- `implemented`: reader can participate in `run-data-fetch`
- `unavailable`: source is known but credentials/tooling are unavailable
- `disabled`: source exists but is intentionally excluded

## Current Default Data-Fetch Sources

`run-data-fetch` reads `source-families.yaml` and includes sources where
`default_data_fetch: true`. A default data-fetch source can still use
project-linked cursors when its source entities are project-specific.

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
  Vercel projects, or Notion spaces should use project-linked fetch cursors so a
  newly added project gets its own initial window instead of inheriting an old
  global source cursor.
- Project-linked source cursors should still reuse stable source entity
  identities and cursor `seen_keys` so the same entity is not fetched or tagged
  repeatedly for multiple reports.
- New canonical projects trigger a default shared-source tagging lookback of
  seven days. Existing project reports do not.
- Source status must be recorded in run manifests.
- A skipped source is not the same as a source with no data.
- Presentation surfaces can provide pointers, but canonical backing sources
  should provide evidence.
