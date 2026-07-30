# State Of Project Architecture

This diagram captures the current filesystem-first Project Intel architecture
for the State of Project automation. It distinguishes external scheduling,
deterministic filesystem/CLI plumbing, Codex intelligence skills, registry
contracts, private runtime artifacts, and future read-only action auditing.

## Component Architecture

```mermaid
flowchart TB
  classDef external fill:#f8fafc,stroke:#94a3b8,color:#0f172a
  classDef registry fill:#eef2ff,stroke:#6366f1,color:#111827
  classDef cli fill:#ecfeff,stroke:#0891b2,color:#0f172a
  classDef skill fill:#f0fdf4,stroke:#16a34a,color:#0f172a
  classDef artifact fill:#fff7ed,stroke:#f97316,color:#111827
  classDef guard fill:#fef2f2,stroke:#dc2626,color:#111827

  subgraph External["Outside Project Intel"]
    Scheduler["External scheduler or human trigger"]
    Sources["Datasource APIs and CLIs<br/>Gmail, GitHub, Fireflies, Drive, deployments"]
    Management["AiStudio management"]
    Reviewers["Human reviewers"]
  end

  subgraph Registry["Governed Registry And Contracts"]
    ProjectRegistry["project-tags.yaml<br/>canonical projects, aliases, project-linked resources"]
    SourceRegistry["source-families.yaml<br/>reader status, source policies, cursor ownership"]
    Contracts["Registry docs<br/>filesystem, annotation, runtime, reporting, schedule"]
    SkillContracts[".agents/skills/*<br/>durable skill instructions"]
  end

  subgraph Runtime["Private Filesystem Runtime"]
    Cursors["state/cursors<br/>resource discovery, fetch, tagging, report"]
    Manifests["logs/runs<br/>manifests, coverage, errors, skipped sources"]
    Untouched["data/raw/untouched<br/>reader-written immutable source logs"]
    Tagged["data/raw/tagged<br/>tagger-owned annotated copies"]
    Derived["data/derived<br/>derived worklists, extracted records, review items"]
    Synthesis["data/projects/&lt;Project&gt;/synthesis<br/>canonical synthesis JSON/Markdown"]
    Reports["data/reports/&lt;Project&gt;/&lt;Date&gt;<br/>report JSON/Markdown plus HTML/PDF brief"]
    Actions["data/projects/&lt;Project&gt;/actions<br/>future candidate actions and issue audit"]
  end

  subgraph CLI["Deterministic CLI In scripts/project_intel.py"]
    Fetch["run-data-fetch<br/>cursor windows and source readers"]
    Worklist["queue<br/>derived tagging worklist, not durable queue"]
    Validate["validate and extract<br/>syntax, metadata, evidence records"]
    PrepareSynthesis["synthesize-project-state<br/>evidence pack and synthesis scaffold"]
    WriteReport["write-state-report<br/>canonical report plus PDF derivative"]
    AuditActions["future audit-actions<br/>read-only task and issue candidates"]
  end

  subgraph Skills["Codex Intelligence Skills"]
    Runner["run-state-of-project<br/>workflow conductor"]
    Tagger["project-tagger<br/>canonical annotations and uncertainty"]
    Synthesizer["project-state-synthesizer<br/>chronology, decisions, blockers, shipped work"]
    ReportWriter["state-report-writer<br/>management brief and audit report presentation"]
    Teacher["capture-project-intel-teachings<br/>durable corrections and process learning"]
  end

  subgraph Guardrails["Safety Boundaries"]
    NoExternalWrites["No emails, issues, PRs, deployments, or external writes<br/>unless explicitly approved"]
    NoPrivateGit["Do not commit private runtime artifacts<br/>raw data, logs, reports, auth, cursors"]
    NoNavigatorYet["No navigator until multiple workflows create routing ambiguity"]
  end

  Scheduler -->|"nightly or manual"| Runner
  Runner --> Fetch
  Runner --> Worklist
  Runner --> Validate
  Runner --> PrepareSynthesis
  Runner --> WriteReport

  ProjectRegistry --> Fetch
  ProjectRegistry --> Worklist
  ProjectRegistry --> Tagger
  ProjectRegistry --> PrepareSynthesis
  SourceRegistry --> Fetch
  SourceRegistry --> Worklist
  Contracts --> Runner
  Contracts --> Tagger
  Contracts --> Synthesizer
  Contracts --> ReportWriter
  SkillContracts --> Runner
  SkillContracts --> Tagger
  SkillContracts --> Synthesizer
  SkillContracts --> ReportWriter

  Cursors -->|"select windows and entities"| Fetch
  Fetch -->|"read once per source window/entity"| Sources
  Sources --> Fetch
  Fetch --> Untouched
  Fetch --> Manifests
  Fetch -->|"advance after successful source capture"| Cursors

  Untouched --> Worklist
  Tagged --> Worklist
  Cursors --> Worklist
  Worklist -->|"only work_required items"| Tagger
  Tagger --> Tagged
  Tagger -->|"advance selected tagging cursor after success"| Cursors

  Tagged --> Validate
  Validate --> Derived
  Validate --> Manifests
  Derived --> PrepareSynthesis
  PrepareSynthesis --> Synthesis
  Synthesis --> Synthesizer
  Synthesizer --> Synthesis
  Synthesis --> WriteReport
  WriteReport --> Reports
  WriteReport -->|"advance only after successful report stage"| Cursors
  Reports --> Management
  Reports --> Reviewers

  Synthesis --> AuditActions
  Reports --> AuditActions
  AuditActions --> Actions
  Actions --> Reviewers

  Reviewers -->|"corrections and architecture feedback"| Teacher
  Teacher --> Contracts
  Teacher --> SkillContracts

  Runner -.-> NoExternalWrites
  Fetch -.-> NoPrivateGit
  WriteReport -.-> NoPrivateGit
  Runner -.-> NoNavigatorYet

  class Scheduler,Sources,Management,Reviewers external
  class ProjectRegistry,SourceRegistry,Contracts,SkillContracts registry
  class Fetch,Worklist,Validate,PrepareSynthesis,WriteReport,AuditActions cli
  class Runner,Tagger,Synthesizer,ReportWriter,Teacher skill
  class Cursors,Manifests,Untouched,Tagged,Derived,Synthesis,Reports,Actions artifact
  class NoExternalWrites,NoPrivateGit,NoNavigatorYet guard
```

## Nightly Run Sequence

```mermaid
sequenceDiagram
  autonumber
  participant Scheduler as External scheduler or human
  participant Runner as run-state-of-project
  participant Registry as Registry contracts
  participant CLI as scripts/project_intel.py
  participant Sources as Datasources
  participant FS as Private filesystem
  participant Tagger as project-tagger
  participant Synth as project-state-synthesizer
  participant Writer as state-report-writer
  participant Mgmt as AiStudio management

  Scheduler->>Runner: Trigger data fetch and project report
  Runner->>Registry: Load project profiles, source policies, cursor rules
  Runner->>CLI: run-data-fetch
  CLI->>FS: Read fetch cursors
  CLI->>Sources: Fetch implemented source windows/entities once
  Sources-->>CLI: Source records
  CLI->>FS: Write untouched logs and run manifest
  CLI->>FS: Advance fetch cursors after successful capture

  Runner->>CLI: Build derived tagging worklist
  CLI->>FS: Compare untouched logs, tagged logs, hashes, registry state, metadata
  alt Tagging work is required
    Runner->>Tagger: Annotate only work_required source artifacts/entities
    Tagger->>FS: Create or update tagged copies with canonical annotations
    Runner->>CLI: Validate tagged logs and advance selected tagging cursors
  else Tagged logs are current
    Runner->>CLI: Skip current items
  end

  Runner->>CLI: synthesize-project-state &lt;Project&gt;
  CLI->>FS: Extract confirmed and uncertain evidence for the report window
  CLI->>FS: Write synthesis scaffold and evidence pack
  Runner->>Synth: Fill reasoning from confirmed evidence
  Synth->>FS: Write completed synthesis with self-evaluation

  Runner->>Writer: write-state-report &lt;Project&gt;
  Writer->>FS: Write report JSON and Markdown with evidence links
  Writer->>FS: Render HTML/PDF management brief and preview
  Writer->>FS: Advance report cursor after successful report stage
  Writer-->>Mgmt: Human-readable state-of-project brief
```

## Architecture Notes

- Fetching and tagging are source-artifact or source-entity stages, not
  per-report stages.
- Shared datasources use source-linked cursors; project-specific resources use
  project-linked cursors; new canonical projects get a default seven-day
  shared-source tagging lookback.
- The `queue` command is a reproducible derived worklist, not a durable queue.
- Untouched logs are reader-owned; tagged logs are tagger-owned; synthesis owns
  reasoning; report writing owns presentation.
- JSON and Markdown are canonical audit artifacts. HTML/PDF are management
  derivatives.
- Current implemented readers are Gmail and GitHub. Fireflies batch discovery,
  Drive, and deployment-provider readers remain planned source coverage gaps.
- The next planned layer is a read-only action/issue auditor that produces
  reviewable candidate actions before any external write capability exists.
