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
- `keynotes/` - slide decks for in-class presentation of each assignment:
  - `Project-Outcome-Analysis.pptx` (assignment A1c)
  - `Build-Demo-and-Applied-Analysis.pptx` (assignment A2), including a native redraw of
    the domain model above with the same associations and multiplicities.
