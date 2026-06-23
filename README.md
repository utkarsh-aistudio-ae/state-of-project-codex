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

## Current CLI

The first implemented slice fetches one Fireflies transcript and writes:

- an untouched Markdown source log under `data/raw/untouched/`
- an initial tagged Markdown copy under `data/raw/tagged/`
- a private run manifest under `logs/runs/`

Example:

```bash
python3 scripts/project_intel.py fireflies fetch 01KV7H2GX5ACK0J3T8W5K1WHD2
```

The command uses the local `bin/fireflies-team` wrapper. Generated source logs
and manifests are ignored by git.
