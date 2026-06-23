# State of Project Codex Automation

This directory is a separate local Codex automation sandbox. It does not modify
the OpenClaw repo.

The public/private boundary is strict:

- GitHub stores reproducible code, contracts, plans, and sanitized docs.
- The local filesystem stores auth, logs, private source captures, downloaded
  state, manifests, and derived runtime data.

Auth is intentionally isolated under `auth/` and wrappers in `bin/` opt into it:

- `bin/gh-sharad`
- `bin/vercel-sharad`
- `bin/gog-sharad`
- `bin/fireflies-sharad`
- `bin/fireflies-team`

The wrappers use copied Sharad/Hermes credentials only for commands launched
through them. Your normal shell auth under `/home/utkarsh-aistudio` is unchanged.

Treat `auth/`, `state/`, `logs/`, `config/`, `data/raw/`, and `data/derived/`
as private runtime data. Do not commit or print their contents.

## GitHub Sync Rule

Push significant changes to `utkarsh-aistudio-ae/state-of-project-codex`, such
as new contracts, scripts, tests, or plan/vision updates. Do not push every tiny
edit immediately. Batch coherent changes after they pass local checks.

Never push auth material, private transcripts, email exports, Drive downloads,
runtime manifests with private content, or generated derived records.

## Architecture Decision Rule

Project Intel is a long-term, multi-datasource internal intelligence system for
production client work. Do not treat the current Fireflies/Argos slice as the
architecture.

Codex may implement deterministic helpers, readers, validators, extractors, and
skills that preserve agreed contracts. Larger architecture choices, including
orchestration boundaries, queue storage, scheduler model, state stores,
database/index introduction, review UX, and external-write pipelines, require
explicit user discussion before being encoded as durable design.

## Current CLI

The first implemented slice fetches one Fireflies transcript and writes:

- an untouched Markdown source log under `data/raw/untouched/`
- a private run manifest under `logs/runs/`

Example:

```bash
python3 scripts/project_intel.py fireflies fetch 01KV7H2GX5ACK0J3T8W5K1WHD2
```

The command uses the local `bin/fireflies-team` wrapper. Generated source logs
and manifests are ignored by git.

Derived tagging queue:

```bash
python3 scripts/project_intel.py queue
```

The `queue` command is a derived filesystem worklist, not a durable queue. It is
computed from untouched files, tagged files, source hashes, registry hash, and
tagger metadata.

The tagger, not the reader, creates or updates matching files under
`data/raw/tagged/`. The deterministic helper for preparing or finalizing a
tagged copy is:

```bash
python3 scripts/project_intel.py tag data/raw/untouched/<Source>/<YYYY-MM>/<YYYY-MM-DD>/<file>.md
```

Tagged-log checks:

```bash
python3 scripts/project_intel.py validate
python3 scripts/project_intel.py extract
```

The repo-local Codex tagging workflow lives at
`.agents/skills/project-tagger/SKILL.md`. Codex uses that skill for the
non-deterministic project judgment; the script validates syntax, registry use,
metadata, queue state, and JSONL extraction.

The repo-local teaching-capture workflow lives at
`.agents/skills/capture-project-intel-teachings/SKILL.md`. Use it when user
corrections, architecture feedback, source-routing fixes, or "next time" process
instructions should become durable Project Intel behavior instead of remaining
only in chat.

Nightly data-fetch and report skeleton:

```bash
python3 scripts/project_intel.py run-data-fetch
python3 scripts/project_intel.py run-state-report Argos-ddt
```

The external scheduler owns timing. `run-data-fetch` computes shared source
cursors/windows, reads data-fetch source families from
`data/registry/source-families.yaml`, writes untouched source logs, advances
shared source cursors after successful capture, and records a private manifest.
`run-state-report <Project-tag>` checks the derived tagging worklist,
validates/extracts tagged evidence, writes a private report under
`data/reports/`, records a private manifest under `logs/runs/`, and advances the
project report cursor after the report stage succeeds.

The current orchestration recipe is:

```text
orchestrations/state-of-project-nightly.md
```
