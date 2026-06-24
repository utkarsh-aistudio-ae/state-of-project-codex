# Management PDF Brief

Use this reference when rendering or reviewing the HTML/PDF derivative of a
Project Intel state report.

## Contract

The PDF is a management brief. It is not the canonical audit artifact.

- JSON and Markdown own full provenance, evidence IDs, source paths, uncertainty
  detail, and exhaustive audit sections.
- HTML and PDF own audience-specific presentation for AiStudio management.
- Do not copy, vendor, or derive content from external PDF skills with
  restrictive licenses. Learn general workflow patterns only.

## Content Shape

The PDF should answer: "What changed since the cursor, what matters now, and
what should management do next?"

Include:

- executive narrative of the current project state
- major themes or deltas since the cursor
- shipped work and implementation themes
- client or stakeholder signals
- risks, blockers, and open questions
- recommended next actions
- short source coverage caveat in plain language
- concrete links to the relevant conversation, email thread, PR, issue/ticket,
  commit, deployment, doc, repo, or resource when available

Exclude:

- evidence IDs
- evidence index
- local source paths
- raw transcript or email excerpts
- exhaustive event dumps
- internal-only review records unless they materially affect management action

## Presentation

- Prefer a concise 1-2 page brief as a soft target, not a hard gate.
- Aggregate related details into themes rather than listing every event.
- Use natural language paragraphs supported by short structured sections.
- Keep headings scannable: state, work completed, client signals, risks/open
  questions, next actions, coverage notes.
- Make confidence and source coverage visible without turning the report into a
  debug log.
- Surface user-openable links as short contextual link rows. Prefer specific
  links over generic source links, and omit links when they are unavailable or
  not relevant to the statement.
- Use restrained business styling: clear hierarchy, readable type, generous
  spacing, and no decorative clutter.

## Tooling

Current default:

- build an HTML/CSS management brief from the completed synthesis payload
- render PDF with Chromium
- validate PDF text with `pypdfium2`
- render a first-page preview PNG from the actual PDF with `pypdfium2`/Pillow

Keep HTML/CSS plus Chromium while it remains sufficient. Consider ReportLab only
if the workflow needs strict pagination, reusable branded components, or removal
of the browser dependency.

## Review Loop

After rendering:

- inspect the PDF-derived preview, not a screenshot of the source HTML
- confirm the first page is readable and visually hierarchical
- check that the report feels like a project-manager brief, not an agent audit
  log
- check for overflow, clipped text, blank pages, browser errors, or temp paths
- confirm source caveats are visible but concise
- confirm concrete conversation/PR/ticket/resource references are linked when
  the report names or depends on them
- confirm next actions are useful and not external writes

Do not use brittle formatting checks as a substitute for this review loop.
