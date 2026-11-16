# Per Product Engagement Numbering

## Problem

Issue [#13592](https://github.com/DefectDojo/django-DefectDojo/issues/13592) asks for an automatically assigned engagement reference with a format chosen by the product owner. The Engagement database ID is global, so it cannot supply a product-local sequence.

## Change

- Add an optional `engagement_number_format` and a server-managed counter to Product. Accept one `{number}` or zero-padded `{number:0Nd}` placeholder, with `N` from 1 to 16 and restricted literal characters.
- Store the issued `engagement_number` on Engagement. Allocate it under a Product row lock within the Engagement save transaction and enforce uniqueness per Product. A failed insert rolls back the counter. A deleted number is not reused.
- Issue a destination number when an engagement moves to another Product, and a new number when it is copied. Existing engagements are not backfilled, and existing URL IDs remain stable.
- Expose the format in Product UI and APIs, and the issued number in engagement UI and read APIs. Keep the counter and issued number out of writable API fields.
- Add the model and audit history migrations, regression tests, and user documentation.

## Verification and reproduction

Run the supported test wrapper in development mode:

```bash
./docker/setEnv.sh dev
docker compose up -d
./run-unittest.sh --test-case unittests.test_engagement_numbering
./run-unittest.sh --test-case unittests.test_apiv2_engagement
./run-unittest.sh --test-case unittests.api_v3.test_apiv3_engagements
./run-unittest.sh --test-case unittests.api_v3.test_apiv3_assets
./run-unittest.sh --test-case unittests.test_importers_performance
./run-unittest.sh --test-case unittests
docker compose exec -T uwsgi python manage.py makemigrations --check --dry-run
docker compose exec -T uwsgi python manage.py spectacular --fail-on-warn --file /tmp/engagement-schema.yml
```

The four focused suites passed: 8, 4 (one existing skip), 33, and 27 tests respectively. Migration drift check reported `No changes detected`; the API schema command exited successfully. A direct two-writer Postgres check created `ENG-0001` and `ENG-0002` for one Product. The importer performance test, complete suite, and pinned Ruff results are recorded in the final-project wiki page.

To reproduce through the application, edit an Asset and set **Engagement number format** to `ENG-{number:04d}`. Create two Engagements under it. Their list and detail views show `ENG-0001` and `ENG-0002`. The Product API exposes the format, while engagement read APIs expose the issued number.

## Scope and review focus

Existing Engagements remain unnumbered; no bulk backfill or counter reset is included. On a Product move, the human-readable reference changes while the database ID and URL do not. Normal Product saves exclude the server-managed counter so an older in-memory Product cannot reset it. Existing Engagements track their original Product ID to avoid a comparison query on routine saves; please review the snapshot update behavior around `refresh_from_db()` and `update_fields`. Direct `bulk_create()` and `QuerySet.update()` do not execute model save hooks and therefore are outside the allocation contract.
