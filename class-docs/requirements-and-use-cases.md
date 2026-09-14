# Requirements and Use Cases

CSCI 360: Software Architecture, Security, and Testing | Fall 2026 - Tyler McGuire

Prepared with Claude Code (Anthropic), run directly inside the local clone of this fork on
branch `coursework/csci360-project-outcome-analysis`. Every requirement, actor, and use-case
step below cites a real file, class, or setting checked directly against this repository, not
recalled from general knowledge of DefectDojo. Full disclosure is in the AI Use Log at the
bottom.

## Part 1: Requirements (FURPS+)

**Functional** - The system must deduplicate Findings from repeated scans of the same target
using a set of fields configurable per scanner, not a single fixed comparison. Evidence:
`HASHCODE_FIELDS_PER_SCANNER` (`dojo/settings/settings.dist.py:1067`) keys the dedupe fields off
scan type - e.g. `"Checkmarx Scan": ["cwe", "severity", "file_path"]` versus
`"Bandit Scan": ["file_path", "line", "vuln_id_from_tool"]` - and is consumed by
`Finding.compute_hash_code()` (`dojo/finding/models.py:783`).

**Usability** - Every primary navigation control, alert banner, and icon-only button in the main
layout must carry an ARIA label or role so the app is usable with a screen reader, not only
visually. Evidence: `dojo/templates/base.html` sets `aria-label="Main navigation"` (line 154),
`aria-label="Search"` on the search box and its submit button (lines 407-408),
`aria-label="Alerts"` on the alerts menu (lines 421, 434), `aria-label="User Menu"` (line 450),
and `role="alert"` on the announcement/system-message banners (lines 497, 507) with
`aria-label="Close"`/`"Dismiss"` on their dismiss buttons (lines 499, 513).

**Reliability** - Calls out to the JIRA API must tolerate transient failures instead of failing
the whole import or triage action on the first blip. Evidence:
`DD_JIRA_MAX_RETRIES=3`, `DD_JIRA_CONNECT_TIMEOUT=10`, `DD_JIRA_READ_TIMEOUT=30`
(`dojo/settings/settings.dist.py:195,197,199`), with an inline comment pointing at Atlassian's
own rate-limiting documentation and noting the underlying `jira` library caps any single retry
wait at 60 seconds regardless of what JIRA's `Retry-After` header asks for.

**Performance** - List endpoints on the REST API must return results in bounded pages rather
than the whole table, and expensive per-request settings lookups must be cacheable instead of
hitting Postgres on every request. Evidence: `REST_FRAMEWORK["PAGE_SIZE"] = 25` with
`DEFAULT_PAGINATION_CLASS = "rest_framework.pagination.LimitOffsetPagination"`
(`dojo/settings/settings.dist.py:715-716`), and a Redis-backed `CACHES` entry gated on
`DD_CACHE_URL` plus a `SETTINGS_CACHE_L1_TTL` (default 30 seconds)
(`dojo/settings/settings.dist.py:297,301,353-357,362`).

**Supportability** - Nearly every operational behavior (JIRA timeouts, dedupe fields, search
result limits, autocomplete size, logging format, and more) must be configurable through
environment variables rather than a code change, and the UI must ship translated strings for
more than one locale. Evidence: the `env()` block in `dojo/settings/settings.dist.py` declares
well over a hundred `DD_*` settings (e.g. `DD_HASHCODE_FIELDS_PER_SCANNER` at line 273,
`DD_SEARCH_MAX_RESULTS`/`DD_SIMILAR_FINDINGS_MAX_RESULTS`/`DD_MAX_REQRESP_FROM_API` at lines
180-183); `dojo/locale/` contains populated translation directories for `en`, `pt_BR`, and `ru`,
consumed via `{% trans %}` tags such as the one on `dojo/templates/base.html:407`.

**Plus** - The project must ship under a specific redistribution license restricting use of the
DefectDojo name, and the officially supported deployment path is container/Helm packaging, not a
bare `pip install`. Evidence: `LICENSE.md` is a 3-clause BSD-style license whose third clause
forbids using "the name of the copyright holder nor the names of its contributors" to endorse or
promote derived products; `docker-compose.yml` plus `readme-docs/DOCKER.md` document the
supported development path, and `helm/defectdojo/Chart.yaml` documents the supported production
Kubernetes path.

## Part 2: Actors

- **Primary actor - AppSec Engineer.** A user who is a member of the Product or Product Type
  being worked on (`Product_Member`, `Product_Type_Member` in `dojo/models.py:654,656`) and logs
  into the DefectDojo UI to import scan results and triage the Findings that result.
- **Supporting actor - JIRA.** The external issue tracker DefectDojo calls out to in order to
  create, link, and comment on tickets for Findings (`dojo/jira/services.py`), governed by the
  retry/timeout settings cited in the Reliability requirement above.
- **Offstage actor - Compliance Reviewer.** Someone who never logs into DefectDojo directly but
  consumes the PDF/CSV product report it generates (`generate_report`,
  `dojo/reports/ui/views.py:353`) after the fact, to confirm Findings were remediated or formally
  risk-accepted within SLA.

## Part 3: Brief Use Cases

**Import Scan Results.** An AppSec Engineer uploads a scan report file from a security tool
(for example a Checkmarx or Bandit export) against a Product's Engagement. DefectDojo parses the
file into Findings, deduplicates them against existing Findings using the scanner's hash-code
rule, closes any previously-imported Finding that no longer appears in the new report, and
notifies subscribed users that the test finished. Implemented in: `ImportScanResultsView`
(`dojo/engagement/ui/views.py:693`), `dojo/importers/default_importer.py`.

**Triage a Finding.** An AppSec Engineer opens a Finding, reviews its detail, and records a
disposition - changing its severity or status, optionally accepting risk inline, and optionally
linking or pushing it to a JIRA ticket so the fix work is tracked where engineering already
works. Implemented in: `ViewFinding` (`dojo/finding/ui/views.py:444`), `EditFinding`
(`dojo/finding/ui/views.py:722`).

**Accept Risk for a Finding.** An AppSec Engineer who has decided a Finding is not worth fixing
right now formally accepts the risk: giving the acceptance an owner, a justification, and
(optionally) an expiration date, so the Finding stops counting against SLA metrics until the
acceptance itself expires or is reinstated. Implemented in: `add_risk_acceptance`
(`dojo/engagement/ui/views.py:1220`), `dojo/risk_acceptance/helper.py`.

## Part 4: Fully-Dressed Use Cases

### Use Case: Import Scan Results

**Primary Actor:** AppSec Engineer

**Stakeholders and Interests:**
- AppSec Engineer: wants the new scan's findings reflected accurately without manually
  re-entering ones already tracked.
- JIRA (supporting): wants only genuinely new or reopened Findings to generate tickets, not the
  same Finding again on every import.
- Compliance Reviewer (offstage): wants the Finding count and SLA clock for the Product to stay
  accurate across imports.

**Preconditions:** The Engineer is authenticated and a member of the Product/Engagement being
imported into; a `Tool_Configuration` exists if the chosen parser pulls from an API rather than a
file upload.

**Success Guarantee:** A `Test` exists recording the import; every new vulnerability in the scan
is a `Finding` linked to that Test; Findings absent from the new report but present in the prior
import are closed as implied-mitigated; a notification is queued.

**Main Success Scenario:**
1. Engineer selects "Import Scan Results" on an Engagement, chooses the scan type, and uploads
   the report file.
2. System verifies the tool configuration for the Engagement.
3. System selects the parser for the chosen scan type and parses the file into an in-memory list
   of Findings.
4. System processes the parsed Findings, computing each one's hash code from the scanner's
   dedupe field set and creating a `Finding` row for each one not already present.
5. System closes any previously-imported Finding for this Engagement that no longer appears in
   the new report.
6. System updates the Test's and Engagement's timestamps and records an import-history entry.
7. System queues a notification that the test finished, summarizing new and closed Finding
   counts.
8. System displays the updated Finding list for the Engagement.

**Extensions:**
- 3a. The chosen scan type has no registered parser:
  1. System raises an unsupported-scan-type error and displays it to the Engineer without
     creating a Test.
- 4a. A parsed Finding's hash code matches an existing Finding's hash code for this Engagement:
  1. System marks the parsed Finding as a duplicate of the existing one instead of creating a
     new row (`Finding.compute_hash_code()`).
- 4b. The Engagement's Product has JIRA push-on-import enabled:
  1. System pushes each qualifying new Finding to JIRA as it is created.
  2. JIRA returns a transient error (429, 503, or a connection error): system retries the call
     up to `DD_JIRA_MAX_RETRIES` times before giving up on that Finding and recording the
     failure.

**Special Requirements:** JIRA calls made in extension 4b are bound by
`DD_JIRA_CONNECT_TIMEOUT`/`DD_JIRA_READ_TIMEOUT` (the Reliability requirement in Part 1).

**Implemented in:** `dojo/engagement/ui/views.py:693` (`ImportScanResultsView`),
`dojo/importers/default_importer.py:93` (`process_scan`),
`dojo/importers/base_importer.py:205,217` (`process_findings`, `close_old_findings`),
`dojo/finding/models.py:783` (`compute_hash_code`).

### Use Case: Triage a Finding

**Primary Actor:** AppSec Engineer

**Stakeholders and Interests:**
- AppSec Engineer: wants to record a triage decision once and have it reflected everywhere
  (JIRA, reports, SLA clock).
- JIRA (supporting): needs a consistent internal issue reference to keep its own ticket in sync
  with the Finding.
- Compliance Reviewer (offstage): needs the Finding's status/severity history to be trustworthy
  for later reporting.

**Preconditions:** The Finding exists and the Engineer has edit permission on its Product.

**Success Guarantee:** The Finding's fields (status, severity, reviewer, reviewed date) are
saved; if a JIRA link was requested, the Finding is linked or updated in JIRA; if risk was
accepted inline, a risk-acceptance record covers the Finding.

**Main Success Scenario:**
1. Engineer opens a Finding's edit view.
2. System displays the current Finding detail and, if a JIRA project is configured for the
   Product, a JIRA sub-form.
3. Engineer changes fields such as severity or status and submits the form.
4. System validates and saves the Finding, recording the Engineer as `last_reviewed_by` and the
   current time as `last_reviewed`.
5. System checks whether the change flips the Finding between false-positive and active and
   updates the false-positive history accordingly.
6. System displays the saved Finding with a success message.

**Extensions:**
- 3a. Engineer also fills in the JIRA sub-form to link an existing JIRA issue key:
  1. System calls out to JIRA to confirm the issue exists, retrying on a transient JIRA error per
     the Reliability requirement in Part 1.
  2. System links the Finding to that JIRA issue and displays "Linked a JIRA issue successfully."
- 3b. Engineer checks "risk accepted" and the Product has simple risk acceptance enabled:
  1. System calls `simple_risk_accept()` instead of routing the Engineer through the full
     risk-acceptance workflow (see the next use case).
- 4a. The submitted form fails validation (for example, a required field left blank):
  1. System re-renders the edit view with the field-level errors attached and makes no changes
     to the Finding.
- 5a. Engineer instead unchecks a previously-accepted risk:
  1. System calls `risk_unaccept()` for the Finding.

**Special Requirements:** none beyond the JIRA reliability requirement already stated.

**Implemented in:** `dojo/finding/ui/views.py:444` (`ViewFinding`),
`dojo/finding/ui/views.py:722` (`EditFinding`),
`dojo/finding/ui/views.py:962` (`process_jira_form`),
`dojo/finding/ui/views.py:906` (`process_finding_form`),
`dojo/risk_acceptance/helper.py:427,453` (`simple_risk_accept`, `risk_unaccept`).

### Use Case: Accept Risk for a Finding

**Primary Actor:** AppSec Engineer

**Stakeholders and Interests:**
- AppSec Engineer: wants a documented, time-boxed exception instead of leaving the Finding open
  indefinitely or closing it dishonestly.
- Compliance Reviewer (offstage): needs the acceptance's owner, justification, and expiration
  date to evaluate whether the exception is still valid at audit time.

**Preconditions:** The Finding(s) exist and are not already covered by an active risk
acceptance; the Engagement's Product has full risk acceptance enabled
(`enable_full_risk_acceptance`).

**Success Guarantee:** A `Risk_Acceptance` record exists linking the accepted Finding(s), with an
owner, a name, and (optionally) an expiration date; the covered Findings are marked
risk-accepted.

**Main Success Scenario:**
1. Engineer selects "Accept Risk" from a Finding and is shown a form pre-filled with a suggested
   acceptance name ("Accept: \<finding\>") and themselves as owner.
2. Engineer selects which Finding(s) the acceptance covers, enters a justification, and
   optionally sets an expiration date.
3. Engineer submits the form.
4. System saves the `Risk_Acceptance`, attaches it to the Engagement, and adds the selected
   Findings to it (`add_findings_to_risk_acceptance()`).
5. System adds the Engineer's justification as a Note on the acceptance.
6. System displays the Engagement's risk-acceptance list including the new record.

**Extensions:**
- 1a. The Product has full risk acceptance disabled:
  1. System does not offer this form; risk can only be accepted inline through the simple path
     in the "Triage a Finding" use case.
- 4a. The acceptance's expiration date arrives before it is reinstated:
  1. System's scheduled `expiration_handler` job calls `expire_now()`, which un-accepts the
     covered Findings and reopens their SLA clock.
- 4b. Engineer later reverses an expired acceptance:
  1. System's `reinstate()` restores the acceptance's prior expiration date and re-marks the
     covered Findings as risk-accepted.

**Special Requirements:** expiration is evaluated by a scheduled job, not only when a user
happens to open the Engagement, so an acceptance expires on schedule even if nobody visits that
day.

**Implemented in:** `dojo/engagement/ui/views.py:1220` (`add_risk_acceptance`),
`dojo/risk_acceptance/helper.py:101,151,235,265` (`expire_now`, `reinstate`,
`add_findings_to_risk_acceptance`, `expiration_handler`).

## Part 5: Use Case Diagram

Diagram source: [`class-docs/use-case-diagram.puml`](https://github.com/tlmcguire/django-DefectDojo/blob/master/class-docs/use-case-diagram.puml)
(PlantUML), rendered below. Kept in `/class-docs` rather than `/docs` for the same reason as the
domain model - `/docs` is DefectDojo's own Hugo documentation site, not a place for course
material.

![Use case diagram: AppSec Engineer (primary) connects to Import Scan Results, Triage a Finding, and Accept Risk for a Finding inside the DefectDojo system boundary; Triage a Finding uses JIRA (supporting); Compliance Reviewer (offstage) reviews the outcomes of Triage a Finding and Accept Risk for a Finding without touching the system directly.](https://raw.githubusercontent.com/tlmcguire/django-DefectDojo/master/class-docs/use-case-diagram.png)

The offstage actor is drawn with a dashed line labeled by what they review, not a solid
interaction line, since Larman's definition of an offstage actor is explicitly that they never
touch the system directly.

## AI Use Log

**Tool:** Claude Code (Anthropic), run directly inside this cloned fork at
`/Users/tyler/Projects/django-DefectDojo`, with shell, file-edit, and read access to the whole
repository.

**What I asked it to do, and what it did:**

1. Read the prior A1c and A2 class-docs (`project-outcome-analysis.md`,
   `build-demo-and-applied-analysis.md`, `domain-model.md`) to match established house style
   (no em dashes, no filler, real file:line citations, an honest AI Use Log) before writing
   anything new.
2. Ran a research pass across the codebase for FURPS+ evidence: grepped
   `dojo/settings/settings.dist.py` for JIRA retry/timeout settings, cache/pagination settings,
   and the `DD_*` environment-variable block; grepped `dojo/templates/base.html` for ARIA
   attributes; checked `dojo/locale/` for populated translation directories; read `LICENSE.md`,
   `docker-compose.yml`, and `helm/defectdojo/Chart.yaml` directly rather than assuming their
   contents.
3. Located the real UI view classes and helper functions behind each candidate use case
   (`ImportScanResultsView`, `process_scan`/`process_findings`/`close_old_findings` in the
   importers package, `ViewFinding`/`EditFinding` and their JIRA/finding-form processing methods,
   `add_risk_acceptance` and the `expire_now`/`reinstate`/`simple_risk_accept`/`risk_unaccept`
   helpers) by reading the actual view and helper source, not by guessing plausible names.
4. Verified every function/class name and line number cited above with direct `grep`/`sed`
   reads against the current repository after drafting, catching and fixing one wrong assumption
   along the way (there is no separate UI-level "reimport" view class distinct from the API's
   `ReImportScanView`, so that path was left out of the use cases rather than cited incorrectly).
5. Wrote the PlantUML source for the use case diagram, then rendered it through the public
   PlantUML server and fetched the resulting PNG to `class-docs/use-case-diagram.png`, checking
   the rendered image directly (not just the source) to confirm the system boundary, all three
   actors, and all three use cases actually appear and the offstage actor's dashed lines read as
   intended.
6. Wrote the sections above; I reviewed and adjusted them before publishing, and checked the
   extensions in each fully-dressed use case against the cited code paths myself rather than
   accepting them on the model's word.

**Net effect:** every FURPS+ requirement, actor, use case, and extension above points at code,
settings, or documentation I checked directly in this repository, not general knowledge of what
software like DefectDojo might do.
