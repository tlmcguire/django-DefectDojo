# Project Outcome Analysis

**Project:** [DefectDojo](https://github.com/DefectDojo/django-DefectDojo) (fork: [tlmcguire/django-DefectDojo](https://github.com/tlmcguire/django-DefectDojo))
**Course:** CSCI 360 - Software Architecture, Security, and Testing
**Student:** Tyler McGuire
**Tool used:** Claude Code (Anthropic), run directly in the cloned fork directory.

DefectDojo is a Django application for tracking application-security findings across
products, engagements, and scans, with a REST API, Celery-based async processing, and
integrations for dozens of scanning tools.

Every file path, class name, function name, and line number cited below was checked
directly against this repository (`grep`/`find`, not memory) before being written down,
and every yes/no/partial verdict was reconsidered against what the outcome actually asks
for rather than just whether related code exists.

## Screenshots

**1. Fork verification** - this repository's GitHub page, showing it under my own account
with "forked from DefectDojo/django-DefectDojo" underneath.

<img width="468" height="269" alt="Fork page showing forked from DefectDojo/django-DefectDojo" src="https://github.com/user-attachments/assets/45203187-b230-4ef9-bea5-71a7d8077e5e" />

**2. Remote configuration** - `git remote -v` and `git log --oneline -5` in the local
clone, showing `origin` pointing at my fork and `upstream` pointing at the original
project.

<img width="468" height="204" alt="Terminal output of git remote -v and git log" src="https://github.com/user-attachments/assets/9828ca57-05eb-4db3-9405-9e926541ebd6" />

**3. AI assistant reading the real repository** - Claude Code answering "list the
top-level directories in this repository and describe what each one contains" with this
project's actual directory names, not generic knowledge.

<img width="468" height="377" alt="Claude Code listing the repository's real top-level directories" src="https://github.com/user-attachments/assets/6e5450ed-e655-4201-9722-d9a87cae63c7" />

## The Seventeen Outcomes

### 1. Iteration with an agile approach / a resilient OO analysis and design process (Unified Process)

Yes, with a caveat - the evidence for iterative, agile-style delivery is strong, but DefectDojo doesn't document itself in formal Unified Process terms (inception/elaboration/construction/transition), so this supports the "iteration and resilience" half of the outcome more directly than the "Unified Process" label itself. [`dojo/db_migrations/`](../dojo/db_migrations) holds 292 sequential migration files (`0001_initial.py` through `0291_dojometa_location_product.py` as of this writing), each a small, independently reviewable schema increment rather than one big upfront design. Pairs like `0287_vulnerability_id_entity_tables.py` followed by `0288_backfill_vulnerability_id_entities.py` show the classic "add schema, then backfill data" two-step of iterative delivery. [`readme-docs/RELEASING.md`](../readme-docs/RELEASING.md) documents a formal two-track release cadence (monthly feature releases from `dev` via `release/x.y.z` branches, weekly bugfix releases from `bugfix`), and [`readme-docs/CONTRIBUTING.md`](../readme-docs/CONTRIBUTING.md) describes `django-linear-migrations` with a `max_migration.txt` tracking file specifically to keep many people's iterative schema changes from colliding. `dojo/__init__.py` currently pins `__version__ = "3.2.300"`.

### 2. Work in teams to design software

Partially - the upstream project is a strong example of team-based design, but this assignment is individual, so I can only point to how DefectDojo's maintainers collaborate rather than demonstrate it through my own work yet. [`.github/CODEOWNERS`](../.github/CODEOWNERS) assigns `/docs/content/` to `@paulOsinski`/`@Maffooch` and all other code to `@Maffooch`/`@blakeaowens`, [`.github/pull_request_template.md`](../.github/pull_request_template.md) standardizes what every contributor must fill out, and [`readme-docs/CONTRIBUTING.md`](../readme-docs/CONTRIBUTING.md) has explicit "Submission Pre-Approval" and "Code Review Process" sections, with `.github/workflows/unit-tests.yml` gating merges as a required check in a merge queue (`merge_group` trigger). Right now the evidence is "I can point at how the real maintainers do it," not "I have done it myself" - that would need a later team assignment or an upstream PR to close the gap.

### 3. Analyze a software application problem with use cases

Yes - the API layer reads directly as a set of use cases without needing to be forced into that shape. `class ImportScanView` (line 344) and `class ReImportScanView` (line 462) in [`dojo/api_v2/views.py`](../dojo/api_v2/views.py) are two distinct actor-facing operations: "import a brand-new scan" versus "reimport/update an existing scan against history." `close_old_findings` in [`dojo/importers/base_importer.py:217`](../dojo/importers/base_importer.py) is its own use case - "findings a rescan no longer reports should be automatically mitigated." `class CeleryViewSet` (line 915) exposes yet another: "check the status of an in-flight async import job." These map cleanly onto a use-case diagram with an actor (API client / CI pipeline) and a handful of named use cases.

### 4. Produce a conceptual domain model with UML class diagram, associations, roles, multiplicities

Yes - the Django models already express real associations and multiplicities I can transcribe rather than invent. `class Finding(BaseModel)` in [`dojo/finding/models.py:55`](../dojo/finding/models.py) is the center of the model: a many-to-many `endpoints` association to `Endpoint` (line 205), a many-to-one `test` association to `Test` (line 215), and a self-referential `duplicate_finding = ForeignKey("self", ...)` (line 234) for the duplicate-cluster relationship. `class Finding_Group` (line 1537) is a many-to-many aggregation over `Finding`. `class Engagement(BaseModel)` in [`dojo/engagement/models.py:44`](../dojo/engagement/models.py) has a many-to-one association to `Product` (line 56). `class Endpoint` in [`dojo/endpoint/models.py:104`](../dojo/endpoint/models.py) has the reciprocal many-to-many back to `Finding`.

### 5. Use System Sequence Diagrams to illustrate operations

Yes - the import flow is a clean, already-layered actor-boundary-controller-service chain. An API client hits `ImportScanView` ([`dojo/api_v2/views.py`](../dojo/api_v2/views.py)), which delegates to `DefaultImporter.process_scan` ([`dojo/importers/default_importer.py:93`](../dojo/importers/default_importer.py)), an implementation of the abstract contract defined by `BaseImporter` ([`dojo/importers/base_importer.py:72`](../dojo/importers/base_importer.py), with `process_scan` at line 192, `process_findings` at 205, `close_old_findings` at 217, `process_scan_file` at 241). That's a direct System Sequence Diagram: `:Client -> :ImportScanView -> :DefaultImporter -> :Parser -> :Finding(db)`.

### 6. Produce operation contracts

Partially - this is a weaker fit than I'd like. `validate_scan_date` ([`dojo/api_v2/serializers.py:609`](../dojo/api_v2/serializers.py)) and four other `validate(self, data)` methods (lines 224, 279, 1001, 1162) do enforce real preconditions - correct `scan_type`, a valid date, required fields present - before an import or update is allowed to proceed. But that's DRF input validation, not a Larman-style operation contract, which describes preconditions and postconditions on the *conceptual domain model's* state, not on API request payloads. I can use these `validate()` methods as the precondition half of a contract and the resulting `Finding`/`Test` state changes as the postcondition half, but I'll be constructing the contract myself rather than pointing at one that already exists in this form.

### 7. Logical architectures and message passing among components

Yes - the deployment config names a textbook layered architecture, and the code shows two distinct, real message-passing mechanisms. `docker-compose.yml` lays it out directly: `nginx`, `uwsgi` (the Django app tier), `celerybeat` + `celeryworker` (the async task tier), `postgres` (data tier), and `valkey` (Redis-compatible broker). Message passing happens two ways in code: Celery tasks in [`dojo/tasks.py`](../dojo/tasks.py) (`async_dupe_delete` at line 38, `jira_status_reconciliation_task` at line 152) for cross-process asynchronous work, and Django signal receivers in [`dojo/finding/helper.py`](../dojo/finding/helper.py) (`pre_save_finding_status_change` at line 85, `finding_pre_delete`/`finding_post_delete` at lines 588/698) for decoupled in-process notification between components.

### 8. Explain the nature and use of software patterns, with a code example

Yes - there are at least two clean, real pattern implementations to walk through with actual code. **Factory/Registry:** [`dojo/tools/factory.py`](../dojo/tools/factory.py) keeps a `PARSERS` dict (line 11) and `register_parser()`/`get_parser()` functions (lines 24, 33), auto-discovering every `dojo/tools/<name>/parser.py` at startup so a brand-new scanner integration self-registers without anyone editing `factory.py`. **Observer/Strategy:** [`dojo/notifications/helper.py`](../dojo/notifications/helper.py) defines a `NotificationManagerHelpers` base (line 100) with polymorphic subclasses `SlackNotificationManger`, `MSTeamsNotificationManger`, `EmailNotificationManger`, `WebhookNotificationManger`, and `AlertNotificationManger`, all invoked uniformly through the `create_notification()` entry point (module-level at line 65, with `NotificationManager` - line 632 - providing the class-based dispatch).

### 9. Basics of software object design and responsibilities/collaborations (GRASP)

Yes - the codebase already separates responsibilities the way GRASP principles describe, rather than concentrating logic in one place. **Information Expert:** `Finding.status()` ([`dojo/finding/models.py:1037`](../dojo/finding/models.py)) computes the finding's own derived state from its own fields, rather than pushing that logic into a view. **Controller:** `ImportScanView`/`ReImportScanView` stay thin and delegate the actual work to `DefaultImporter` - a domain-service Controller collaborator. **Pure Fabrication / Low Coupling:** [`dojo/finding/helper.py`](../dojo/finding/helper.py) holds deduplication and grouping logic (`create_finding_group` at line 211, `group_findings_by` at line 325) in its own module instead of bloating the `Finding` model or its serializer.

### 10. Use UML activity diagrams to analyze and model processes

Yes - there are at least two multi-step, branching processes already implemented in code that map directly to an activity diagram. `DefaultReImporter.process_scan` ([`dojo/importers/default_reimporter.py:91`](../dojo/importers/default_reimporter.py)) branches into `process_matched_finding` (line 740) → `process_matched_special_status_finding` (764) / `process_matched_mitigated_finding` (800) / `process_matched_active_finding` (911) / `process_finding_that_was_not_matched` (979). The bulk-delete path in [`dojo/finding/helper.py`](../dojo/finding/helper.py) (`prepare_duplicates_for_delete` at 791 → `resolve_inbound_duplicate_references` at 1040 → `_bulk_delete_findings_internal` at 1120) is a second clean multi-step activity with genuine forks.

### 11. Use UML state diagrams to analyze and model states

Yes - `Finding` and `Engagement` both carry explicit, named lifecycle states rather than an implicit or ad hoc status. `Finding` carries boolean state fields `active`, `verified`, `false_p`, `duplicate`, `out_of_scope`, `risk_accepted`, and `is_mitigated` (lines 220-281), which `Finding.status()` (line 1037) reduces to named composite states - Active, Verified, Mitigated, False Positive, Duplicate, Risk Accepted. `Engagement.status` ([`dojo/engagement/models.py:66`](../dojo/engagement/models.py)) uses `ENGAGEMENT_STATUS_CHOICES` (line 34) for its own lifecycle states.

### 12. Demonstrate basic design principles

Yes - the codebase's module boundaries embody Open/Closed, Separation of Concerns, and Single Responsibility in ways I can point to directly. **Open/Closed:** [`dojo/tools/factory.py`](../dojo/tools/factory.py)'s auto-discovery means adding a new scanner never requires editing the factory itself. **Separation of Concerns:** models ([`dojo/finding/models.py`](../dojo/finding/models.py)), serializers ([`dojo/api_v2/serializers.py`](../dojo/api_v2/serializers.py)), and business logic ([`dojo/finding/helper.py`](../dojo/finding/helper.py)) are deliberately kept in separate modules instead of fat models or views. **Single Responsibility:** [`dojo/authorization/`](../dojo/authorization) is split into ten single-purpose files, including `roles_permissions.py`, `authorization.py`, `query_filters.py`, `url_permissions.py`, `api_permissions.py`, `template_filters.py`, `serializer_guards.py`, and `middleware.py`.

### 13. Explain and implement test-driven development

Partially - the project has an unusually large, CI-enforced test suite ([`unittests/`](../unittests) holds 442 `test_*.py` files, with a shared base in [`unittests/dojo_test_case.py`](../unittests/dojo_test_case.py)'s `DojoTestCase` (line 573) and `DojoAPITestCase` (line 588), run as a required check via `.github/workflows/unit-tests.yml`). That's strong evidence I can study existing tests and add my own new tests against a real, enforced convention. But a large test suite is evidence that testing is taken seriously, not proof the code was written test-first - I have no evidence from the codebase itself that any specific feature followed a red-green-refactor cycle, so demonstrating TDD will mean practicing it myself going forward rather than pointing at history that already shows it.

### 14. Exhibit a basic working knowledge of GUI development using an IDE

Weak fit - the project has a real, working UI layer, but it's server-rendered Django templates rather than the kind of IDE-driven GUI-builder work (Swing, WinForms, a modern SPA component framework) this outcome likely has in mind. [`dojo/templates/dojo/`](../dojo/templates/dojo) holds the page templates plus `partials/` and `snippets/` subdirectories, and `dojo/static/dojo/` holds `css/`, `js/`, `img/`, and `fonts/`. It's enough to demonstrate basic GUI development, but it won't be the strongest example in my portfolio.

### 15. Produce a Software Architecture Document

No, not yet - I checked the existing architecture material directly ([`docs/content/get_started/open_source/architecture.md`](../docs/content/get_started/open_source/architecture.md), 51 lines) and it's a short component list (NGINX, uWSGI, Message Broker, Celery Worker, Celery Beat, Initializer, Database), not a document with explicit architectural views (logical, process, deployment, etc.). It's a real, accurate starting point I can extend, backed by `readme-docs/RELEASING.md`, `DOCKER.md`, and `KUBERNETES.md` for supporting operational detail, but a genuine Software Architecture Document doesn't exist in this repository today - I'll be writing nearly all of it myself.

### 16. Write and present orally analyses of topics in software analysis and design

Not evaluable from the codebase - this outcome is demonstrated through the class presentation itself, not a file citation. I'll cover this project, its two or three strongest outcomes (likely 8, 9, and 17), and its two or three weakest (6, 13, 15), and be ready to open the actual files behind every claim above.

### 17. Incorporate misuse/abuse cases in the system design

Yes - this is one of the project's strongest outcomes, with fine-grained, explicit permission and disclosure logic already in place rather than something I'd have to bolt on. [`dojo/authorization/api_permissions.py`](../dojo/authorization/api_permissions.py) defines fine-grained per-resource permission classes - `UserHasEngagementPermission` (line 382), `UserHasFindingPermission` (464), `UserHasImportPermission` (529) - and [`dojo/authorization/roles_permissions.py`](../dojo/authorization/roles_permissions.py)'s `class Permissions(IntEnum)` (line 69) enumerates granular actions, each encoding an explicit misuse boundary. [`SECURITY.md`](../SECURITY.md) documents the HackerOne-based disclosure process and an explicit "Exclusions" section asking researchers to refrain from denial of service, spamming, and social engineering during testing, and [`.dryrunsecurity.yaml`](../.dryrunsecurity.yaml) wires an automated security reviewer into every pull request.

## Honest weak spots

Five outcomes are a real stretch for this project as it stands today, and I'd rather flag that now than discover it in Week 11:

- **Outcome 2 (team-based design):** the *project's* process is team-based; *my* work on my fork, for this assignment, is not.
- **Outcome 6 (operation contracts):** the closest evidence - DRF serializer `validate()` methods - enforces API input preconditions, not domain-model pre/postconditions in the Larman sense.
- **Outcome 13 (TDD):** a large, CI-enforced test suite proves testing discipline, not that any of it was written test-first.
- **Outcome 14 (GUI/IDE development):** server-rendered Django templates satisfy the letter of the outcome but not really its spirit of hands-on IDE GUI-builder work.
- **Outcome 15 (Software Architecture Document):** the existing architecture page is a 51-line component list, not a formal SAD - this one doesn't exist yet.

## AI Use Log

**Tool:** Claude Code (Anthropic), run directly inside this cloned fork at `/Users/tyler/Projects/django-DefectDojo`, with shell, file-edit, and read access to the whole repository.

**What I asked it to do, and what it did:**

1. Verified the fork/remote setup was already correct (`origin` → `tlmcguire/django-DefectDojo`, `upstream` → `DefectDojo/django-DefectDojo`) by running `git remote -v` and cross-checking with `gh repo view --json isFork,parent`, rather than assuming.
2. Checked whether the fork's wiki was actually initialized (not just the `has_wiki` flag) by attempting to clone `django-DefectDojo.wiki.git`, which confirmed no wiki pages exist yet.
3. Created a `coursework/csci360-project-outcome-analysis` branch off `master` rather than committing coursework directly to the branch that mirrors the current release line.
4. Created the top-level `class-docs/` directory (avoiding `/docs`, which is DefectDojo's own Hugo documentation site) to hold this file and future diagrams.
5. Ran a dedicated research pass across the codebase - `dojo/finding/models.py`, `dojo/engagement/models.py`, `dojo/importers/`, `dojo/tools/factory.py`, `dojo/notifications/helper.py`, `dojo/authorization/`, `.github/`, `docker-compose.yml`, and the `unittests/` tree - to find candidate evidence for each of the seventeen outcomes.
6. Ran a second, dedicated verification pass: re-checked every citation above (file path, class name, function name, line number) with direct `grep`/`find` commands against the repository, rather than trusting the first pass's memory of the code.
7. That verification pass changed three verdicts: outcomes 6 (operation contracts) and 13 (TDD) were downgraded from an unqualified Yes to Partially, because the cited code supports an analogy to the outcome rather than the outcome itself; outcome 1 (Unified Process) was qualified to distinguish "iterative delivery" (well supported) from "formal Unified Process phases" (not documented anywhere in this project). Outcome 15 was confirmed as a clear No after actually reading the architecture document (51 lines, a component list) rather than assuming its content.
8. Flagged five outcomes (2, 6, 13, 14, 15) as genuinely weak or partial fits, with the specific reasoning behind each, instead of claiming full support across the board.

**Net effect:** every citation in this document points at a real file and was checked against this repository before being written down, and every yes/no/partial verdict was reconsidered against what the outcome actually asks for rather than just whether related code exists.
