# Annotation Syntax

Last updated: 2026-06-23

This file is the source of truth for Project Intel annotations in tagged source
logs.

Supported annotations:

```md
[Argos-ddt] {Minimal note useful to downstream skills.}

[?Argos-ddt] {Uncertain project assignment; include why it is uncertain.}

[untagged] {Personal/admin context, not relevant to any AiStudio projects}
```

## Rules

- Tags go before the relevant paragraph, source block, message block, speaker
  block, or conversation snippet.
- Multiple tags are allowed before one block if genuinely needed.
- There is no rejected tag syntax.
- Wrong tags are replaced, not negated.
- Uncertain tags are surfaced in reports and review queues.
- Downstream skills must not create authoritative timeline entries or tickets
  from uncertain tags alone.
- Notes must be concise and minimal.
- Notes should add only context useful to downstream skills that is not already
  obvious from nearby source text.
- The tagger must use canonical tags from `project-tags.yaml` only.
- The tagger may suggest registry additions later, but must not create them
  silently.
- Generic tagging skills and scripts must not hardcode project-specific signals.
  Project-specific aliases, strong signals, weak signals, repos, domains, and
  people belong in the registry or confirmed project profiles.
