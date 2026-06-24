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
   - fill `self_evaluation`
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
- End with a compact self-evaluation. Do not grade generously just because the
  output is well written.
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

## Self Evaluation

Fill `self_evaluation` after the synthesis sections are complete. Use
`high`, `medium`, or `low` for the six score fields:

- `overall_confidence`
- `evidence_faithfulness`
- `chronology_quality`
- `cross_source_reasoning`
- `uncertainty_handling`
- `source_coverage_honesty`

Add concise bullets to:

- `known_weaknesses`: limitations in the synthesis, such as missing deployment
  provider evidence, thin GitHub/task evidence, weak chronology, or source
  coverage gaps.
- `needs_human_review`: concrete items a reviewer should confirm before the
  synthesis is used in a management report, ticket proposal, or external
  update.

Evaluation rules:

- Mark `evidence_faithfulness` low if any important claim lacks evidence.
- Mark `chronology_quality` low if ordering depends on inference rather than
  source timestamps.
- Mark `cross_source_reasoning` low if sources are merely listed instead of
  compared.
- Mark `uncertainty_handling` low if any `?Project` record becomes an
  authoritative fact.
- Mark `source_coverage_honesty` low if skipped or unavailable sources are not
  called out.
- Use `overall_confidence` as the minimum reasonable trust level across the
  material weaknesses, not as an average.
