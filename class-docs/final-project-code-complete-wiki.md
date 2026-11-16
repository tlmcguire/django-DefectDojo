# Final Project: Code Complete

CSCI 360 Software Architecture, Security, and Testing | Tyler McGuire | Fall 2026

## Feature and acceptance criteria

The feature implements DefectDojo issue [#13592](https://github.com/DefectDojo/django-DefectDojo/issues/13592). A Product can opt in to an Engagement number format such as `ENG-{number:04d}`. New Engagements get a product-local reference, shown in the UI and read APIs. The complete design record is [DESIGN.md](https://github.com/tlmcguire/django-DefectDojo/blob/coursework/final-project-engagement-numbering/docs/DESIGN.md), and the reviewer-facing summary is [PR.md](https://github.com/tlmcguire/django-DefectDojo/blob/coursework/final-project-engagement-numbering/docs/PR.md).

The acceptance criteria were: valid restricted formats; opt-in without backfill; product-local, non-reused numbers; distinct numbers under concurrent creation; rollback after failed creation; consistent behavior through UI, both APIs, imports, copy and Product moves; read-only issued numbers and counters. Automated model and API tests cover those behaviors, with a direct Postgres concurrency check for simultaneous creation. A browser check created an Asset with `ENG-{number:04d}` and two Engagements; the Asset's Engagement table and detail pages displayed `ENG-0001` and `ENG-0002`. The earlier issue discussion rejected a global primary-key-based counter because it advanced across unrelated products.

## What an Engagement represents

DefectDojo organizes security work as **Organization → Asset → Engagement → Test → Finding**. An Engagement is a time- or pipeline-bound testing effort for one Asset. A penetration test, quarterly scan, bug bounty review period, release security review, or CI/CD pipeline run can each have its own Engagement. It records the scope, dates, status, lead, and related Tests; those Tests hold the findings. The [project's Engagement guide](https://github.com/tlmcguire/django-DefectDojo/blob/coursework/final-project-engagement-numbering/docs/content/asset_modelling/engagements_tests/OS__engagements.md) describes this hierarchy and the Interactive and CI/CD types.

Engagements matter because they keep results tied to the testing effort that produced them. Teams can distinguish a current scan from an earlier assessment, assign a lead, track progress, and review findings in the context of an Asset and time period. Recurring tests and imports can be organized without mixing every result into one undifferentiated history.

A readable reference helps people identify an Engagement in a report, ticket, meeting, or API response. Names can be long or similar across repeated assessments, while a database ID is global and may jump between unrelated Assets. Product-local numbering gives each Asset a recognizable sequence such as `ENG-0001`, `ENG-0002`. The number is a human-facing reference; the database ID and URL remain the technical identity. Moving an Engagement to another Asset gives it a new reference from the destination Asset's sequence.

## Before and after

These screenshots show two **local demo Assets in the implemented application**. “Before” means an Asset with no number format configured; it is not a screenshot of an older DefectDojo release. “After” means an Asset configured with `ENG-{number:04d}`. This comparison shows the opt-in behavior without claiming that existing Engagements are backfilled.

### Before: no format configured

The Engagement list shows **Baseline engagement** by name with no reference prefix.

![Before numbering: a local Asset with an unnumbered Baseline engagement](https://raw.githubusercontent.com/wiki/tlmcguire/django-DefectDojo/images/engagement-numbering-before.jpg)

### After: format configured

The Engagement list shows two new Engagements with distinct, Asset-local references: `ENG-0001` and `ENG-0002`.

![After numbering: a local Asset whose Engagement list shows ENG-0001 and ENG-0002](https://raw.githubusercontent.com/wiki/tlmcguire/django-DefectDojo/images/engagement-numbering-after.jpg)

## Project rules that shaped the work

- [AGENTS.md](https://github.com/tlmcguire/django-DefectDojo/blob/coursework/final-project-engagement-numbering/AGENTS.md) states, “Base every change on `dev`,” and “The PR base branch is `dev`.” The feature branch contains `origin/dev`; the coursework branch builds on that feature commit.
- [CONTRIBUTING.md](https://github.com/tlmcguire/django-DefectDojo/blob/coursework/final-project-engagement-numbering/readme-docs/CONTRIBUTING.md) says, “Pull requests should be submitted to the `dev` branch,” requires the project's test scripts, Python 3.13 compatibility, and migrations for model changes. It recommends pre-approval for uncertain enhancements. Issue #13592 already has a maintainer invitation to submit a PR, although no `enhancement-approved` label was relied on as a substitute for that discussion.
- [The PR template](https://github.com/tlmcguire/django-DefectDojo/blob/coursework/final-project-engagement-numbering/.github/pull_request_template.md) calls for a description, test results, feature documentation, Ruff compliance, migrations, and a meaningful title. The project CI runs `ruff check` using `ruff==0.16.10` from `requirements-lint.txt`.
- Recent project commits use `feat(scope):` or `docs(scope):` subjects. The feature commit uses `feat(engagement): add per-product numbering (#13592)`. No DCO sign-off or contributor license agreement requirement was found in the checked repository guidance; no sign-off was added.

## Test evidence

Focused tests used `./run-unittest.sh --test-case <module>` in the local Docker development stack:

| Suite | Result |
| --- | --- |
| `unittests.test_engagement_numbering` | 8 tests, OK |
| `unittests.test_apiv2_engagement` | 4 tests, OK, one skipped |
| `unittests.api_v3.test_apiv3_engagements` | 33 tests, OK |
| `unittests.api_v3.test_apiv3_assets` | 27 tests, OK |

`python manage.py makemigrations --check --dry-run` printed `No changes detected`. `python manage.py spectacular --fail-on-warn --file /tmp/engagement-schema.yml` exited successfully. A direct check with two Postgres connections created the distinct references `ENG-0001` and `ENG-0002` and confirmed the Product counter was 2. The complete suite command was `./run-unittest.sh --test-case unittests`; its final result is recorded below after the run completes.

Full suite result: pending.

Pinned Ruff result: `ruff==0.16.10` reported `All checks passed!` for `ruff check .`; the two new Python files passed `ruff format --check`.

## Self review

I read the complete feature diff against `origin/dev`. Three changes followed that review and verification:

1. I found that saving an older Product instance could overwrite a newly incremented counter. Normal Product saves now exclude the server-managed counter, with a regression test.
2. Django's migration drift check exposed missing Product and Engagement audit event fields and trigger updates. I generated a second migration and reran the check until it reported no changes.
3. I found that routine Engagement saves would add a Product comparison query, affecting importers. Loaded Engagements now remember their original Product ID; moves and refreshes update that snapshot.

The area most likely to draw reviewer scrutiny is putting allocation in `Engagement.pre_save_logic()`. A dedicated service would look cleaner, but direct creation through the UI, both APIs, imports, and copy currently converges on `save()`. The model hook gives one rule for all of them; its original-Product snapshot avoids routine lookup costs but needs careful updates after refreshes and moves.

## In class demonstration

1. Show an Asset with no format and an unnumbered Engagement. Set `ENG-{number:04d}` in the Asset edit form and create two Engagements. Show the references in the list and detail views.
2. Show the design choice in the architecture diagram: Product owns the counter; Engagement allocates under a Product row lock. Explain why a global ID and count of existing rows were rejected.
3. Open the `Product.save()` change that excludes the counter and explain the stale-instance concern. If starting again, I would measure importer query counts earlier and add the original Product ID tracking from the start.

The five-minute presentation and OAKS submission must be performed in class or in the course site; this page supplies the script and evidence.
