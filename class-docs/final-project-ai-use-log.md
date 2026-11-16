# Final Project AI Use Log

CSCI 360 Software Architecture, Security, and Testing | Tyler McGuire | Fall 2026

An OpenAI coding assistant was used to research issue #13592, compare alternative designs, inspect DefectDojo's existing models and creation paths, draft and edit code, generate tests and assignment documents, run Docker-based verification, and review the resulting diff. The assistant also drafted the wiki page and this log. The work was carried out in isolated worktrees so the upstream feature diff would not include coursework files.

The issue choice and constraints came from the student's instructions: target a valid feature likely to be merged, keep coursework documents out of any upstream PR, and omit assistant attribution from commits and PR text. The assistant selected the Product row counter design based on issue discussion and repository code. It first missed the audit history migration and a stale Product save race, then corrected both after verification and self review. A misplaced field was corrected before the final commit. A later performance review led to original Product ID tracking so routine Engagement saves avoid an extra comparison query.

Verification performed by the assistant included four focused Django suites, a migration drift check, API schema generation, pinned Ruff linting, and a direct two-writer Postgres concurrency check. A complete `unittests` suite was started separately. Its final output belongs in the wiki page and PR description once the run ends.

This log describes tool use and observed work. It does not claim that the student personally wrote, reviewed, or ran steps that were performed by the assistant. The student should inspect the code and documents, practice the demonstration, and confirm the course submission details before submitting.
