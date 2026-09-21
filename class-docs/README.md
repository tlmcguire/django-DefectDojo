# CSCI 360 Course Materials

This directory holds diagrams, model source files, and other documents produced for
CSCI 360 (Software Architecture, Security, and Testing) assignments against this fork.

It is kept separate from [`/docs`](../docs), which is DefectDojo's own Hugo-based
documentation site (built from `docs/content/`) - course material does not belong mixed
into the upstream project's docs.

## Contents

- `project-outcome-analysis.md` - source for the "Project Outcome Analysis" wiki page
  (assignment A1c): how this project demonstrates each of the seventeen course outcomes,
  with citations to real files/classes/functions in the codebase.
- `build-demo-and-applied-analysis.md` - source for the "Build Demo and Applied Analysis" wiki
  page (assignment A2): build notes from an actual from-source build, an analysis-versus-design
  example, the representational gap trace, and the Unified Process iteration discussion.
- `domain-model.md` - source for the domain model referenced from that same wiki page: a
  Mermaid conceptual class diagram of the vulnerability-management domain this project
  addresses, plus the reasoning behind which concepts were included.
- `requirements-and-use-cases.md` - source for the "Requirements and Use Cases" wiki page
  (assignment A1b): FURPS+ requirements, actors, brief and fully-dressed use cases, and a use
  case diagram, all cited against real files/classes in the codebase.
- `use-case-diagram.puml` / `use-case-diagram.png` - PlantUML source and rendered diagram
  referenced from that same wiki page.
- `ssds-and-operation-contracts.md` - source for the "SSDs and Operation Contracts" wiki page
  (assignment A2b): a noun-phrase analysis of the three fully-dressed use cases that revises
  the domain model to eleven classes, one system sequence diagram per use case, and three
  operation contracts, all cited against real files/classes in the codebase.
- `ssd-import-scan-results.mmd`, `ssd-triage-a-finding.mmd`,
  `ssd-accept-risk-for-a-finding.mmd` - Mermaid source for the three SSDs referenced from that
  same wiki page.
- `keynotes/` - slide decks for in-class presentation of each assignment:
  - `Project-Outcome-Analysis.pptx` (assignment A1c)
  - `Build-Demo-and-Applied-Analysis.pptx` (assignment A2), including a native redraw of
    the domain model above with the same associations and multiplicities.
