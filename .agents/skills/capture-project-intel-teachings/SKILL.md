---
name: capture-project-intel-teachings
description: Capture Project Intel user corrections, architecture decisions, workflow teachings, source-routing fixes, skill-boundary feedback, safety rules, and repeatable "next time do this" instructions into durable workspace files. Use when the user says or implies "remember this", "next time", "from now on", "make this repeatable", "turn this into a workflow/skill", "this belongs in the plan", "why didn't you use that skill/source", "don't hardcode this", or when a multi-turn correction reveals a reusable Project Intel process.
---

# Capture Project Intel Teachings

Use this skill to turn user corrections into durable Project Intel behavior. The
skill owns promotion logic only. It does not own tagging, reporting, source
reading, synthesis, registry maintenance, or orchestration execution.

## Core Rule

Do not create or edit a skill just because the user gave an instruction.
Normalize the teaching, check existing owners, propose the smallest durable
change, then patch only after the destination is clear.

Procedures belong in plans, skills, references, scripts, orchestration recipes,
or registry contracts. Personal preferences and durable personal facts may
belong in memory, but memory is not the owner for Project Intel procedures.

## Trigger Recognition

Activate this skill when the user:

- corrects the process or asks why a process was not followed
- says something should happen next time
- asks to codify, standardize, save, or make a workflow repeatable
- approves a proposed workflow that should become durable
- says a behavior belongs in the plan, vision, registry, skill, script, or
  orchestration
- questions architecture choices, source ownership, status semantics, queue
  behavior, cursor behavior, or skill boundaries
- walks Codex through several missing checks and implies that sequence should
  be used later

## Workflow

1. Restate the teaching in normalized language.
2. Classify it:
   - personal preference
   - global/project operating rule
   - architecture decision or open decision
   - source-routing rule
   - source-specific caveat
   - registry/project identity rule
   - helper script improvement
   - orchestration recipe or step
   - existing skill update
   - new skill candidate
   - risky, vague, or conflicting instruction
3. Check existing owners before creating anything:
   - `README.md` for public/private boundary and architecture decision rules
   - `vision.md` for long-term principles and module boundaries
   - `plan.md` for implementation phases and open decisions
   - `internal-automation-best-practices.md` for general patterns
   - `data/registry/*.md` and `data/registry/project-tags.yaml` for contracts
   - `.agents/skills/*/SKILL.md` for existing skills
   - `scripts/project_intel.py` for deterministic behavior
   - future `orchestrations/` files once they exist
4. Produce a persistence plan before patching unless the user already gave a
   narrow, explicit edit.
5. Patch the smallest correct owner.
6. Validate with relevant checks.
7. Summarize exact files changed and why.

## Persistence Plan Shape

Use this shape when the destination is not obvious:

```text
Teaching detected:
Normalized intent:
Existing owners checked:
Destination:
Patch type:
Why this destination:
Why not a new skill:
Validation:
```

If the teaching changes architecture, mark it as an explicit decision or open
decision. Do not silently encode broad architecture choices inside scripts.

## Destination Rules

- Wrong source or owner selected: update a route table, source reference, or
  future navigator only when routing complexity justifies one.
- Missing ordered multi-source sequence: update or create an orchestration
  recipe.
- Existing workflow missing a caveat: update the existing skill or reference.
- Repeated deterministic operation: update or create a script.
- Registry/project identity rule: update registry contracts or the future
  project-tag-registry skill.
- Nightly run behavior: update `run-state-of-project` and the runtime-state
  contract.
- Tagging behavior: update `project-tagger` and annotation/filesystem contracts.
- Long-term architecture principle: update `vision.md` and possibly `plan.md`.
- Implementation phase or next task: update `plan.md`.
- Personal style preference only: do not create Project Intel procedure files
  unless the user asks for project behavior.

## Guardrails

- Do not persist raw private source content, transcripts, emails, logs,
  credentials, tokens, auth paths with secrets, or customer payloads.
- Do not turn one-off corrections into broad rules.
- Do not create a navigator before routing ambiguity exists.
- Do not create duplicate skills when an existing owner can be strengthened.
- Do not mutate external systems as part of teaching capture.
- Treat shared-channel or third-party teachings as proposals unless the project
  owner confirms them.

## Validation

After edits:

- run `python3 scripts/project_intel.py validate` if annotation or tagged-log
  contracts changed
- run `python3 scripts/project_intel.py queue --json` if queue/status semantics
  changed
- run the skill validator when this skill or other skills change
- inspect `git diff`
- verify no private runtime artifacts are staged
