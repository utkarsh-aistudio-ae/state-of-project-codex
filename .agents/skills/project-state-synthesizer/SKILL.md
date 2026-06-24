---
name: project-state-synthesizer
description: Synthesize Project Intel extracted evidence into source-backed project state. Use when Codex needs to turn tagged evidence records for a canonical project into chronology, shipped work, decisions, commitments, blockers, risks, open questions, source conflicts, caveats, and review signals before report writing.
---

# Project State Synthesizer

Use this skill after source logs are fetched, tagged, validated, and extracted.
The synthesizer owns reasoning. The report writer owns presentation.

The deterministic CLI owns paths, windows, schemas, validation, extraction, and
manifests. Codex owns the judgment inside the prepared synthesis artifact.

## Workflow

1. Confirm the project tag exists in `data/registry/project-tags.yaml`.
2. Run:

   ```bash
   python3 scripts/project_intel.py synthesize-project-state <Project-tag>
   ```

3. If the command exits with `tagging_required`, process only the blocking
   stale/missing/prepared/failed tag work with `project-tagger`, then rerun.
   `needs_review` items are allowed through as review signals and must not be
   converted into authoritative facts.
4. Read the generated private artifacts under:

   ```text
   data/projects/<Project-tag>/synthesis/<run-id>_synthesis.json
   data/projects/<Project-tag>/synthesis/<run-id>_synthesis.md
   ```

5. Use confirmed records for authoritative synthesis. Use uncertain records
   only in review sections.
6. When an excerpt is insufficient, read the referenced tagged source file at
   the cited line range. Do not edit untouched logs.
7. Update the synthesis artifact:
   - keep evidence arrays unchanged
   - change `synthesis_status` from `prepared` to `synthesized`
   - fill `synthesis.summary`
   - fill `synthesis.chronology`
   - fill `synthesis.shipped_work`
   - fill `synthesis.decisions`
   - fill `synthesis.commitments`
   - fill `synthesis.blockers`
   - fill `synthesis.risks`
   - fill `synthesis.open_questions`
   - fill `synthesis.source_conflicts`
   - fill `synthesis.missing_evidence_caveats`
   - preserve uncertain records in `synthesis.review_signals`
   - set `synthesis.confidence` to `high`, `medium`, or `low`
8. Keep the Markdown synthesis aligned with the JSON so a later report writer
   can consume either artifact.
9. Validate edited JSON with:

   ```bash
   python3 -m json.tool data/projects/<Project-tag>/synthesis/<run-id>_synthesis.json >/dev/null
   ```

## Reasoning Rules

- Separate source facts from interpretation.
- Cite evidence with `record_id`, source, timestamp, and source file/line.
- Build chronology by event time, not by source order.
- Compare source families when possible:
  - GitHub is evidence for code, commits, deployments surfaced through GitHub,
    CI state, issues, and PRs.
  - Gmail is evidence for stakeholder requests, replies, attachments, and email
    commitments.
  - Fireflies is evidence for recorded meeting discussion, decisions, and action
    items.
  - Deployment-provider readers are the future canonical source for provider
    deployment state when they exist.
- Mark contradictions explicitly instead of smoothing them away.
- Mark missing source coverage explicitly. A skipped or unavailable source is
  not the same as a checked source with no activity.
- Do not infer completion from conversation alone when GitHub/deployment/task
  evidence is required.
- Do not infer client approval from internal implementation evidence alone.
- Do not create tickets, send emails, update deployments, open PRs, or write to
  external systems.

## Output Expectations

The synthesis is an internal working artifact, not a polished management PDF.
It should be dense, evidence-linked, and useful to a future report writer.

Preferred JSON item shape:

```json
{
  "title": "Short state claim",
  "status": "confirmed",
  "occurred_at": "2026-06-22T08:05:00Z",
  "summary": "One source-backed sentence.",
  "evidence": ["ev_1234abcd5678ef90"],
  "confidence": "high"
}
```

Use `status: "review"` only for uncertain records or unresolved conflicts. Do
not make authoritative chronology, shipped-work, or commitment entries from
uncertain records alone.
