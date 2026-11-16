# Per Product Engagement Numbering Design

## Decision record

Status: implemented for issue [#13592](https://github.com/DefectDojo/django-DefectDojo/issues/13592). The design was drafted before implementation in an uncommitted note. This committed version records the implemented design and the revisions found during review; it is on the coursework branch so the upstream contribution remains free of assignment files.

DefectDojo users need a recognizable reference for an engagement within a product. A global database ID does not meet that need: an engagement created for one product can make the next product jump to an unrelated number. A product owner can now set a restricted format such as `ENG-{number:04d}`. New engagements for that product receive `ENG-0001`, `ENG-0002`, and so on. The reference appears in engagement lists, the detail page, and read APIs. The Product edit form and APIs expose the setting.

### Acceptance criteria

1. Numbering is opt in. Existing products and engagements remain unnumbered until a format is set; existing rows are not backfilled.
2. The format has exactly one `{number}` or `{number:0Nd}` placeholder, where `N` is 1 through 16. Literal characters are limited to ASCII letters, digits, `.`, `_`, and `-`. Invalid formats are rejected before saving the Product.
3. Each numbered engagement gets a product local sequence value. Two concurrent creations cannot receive the same value. Deleting an engagement does not reuse its number; a failed creation rolls its counter increment back.
4. The classic UI, API v2, API v3, scan imports, and engagement copying share the same allocation path. Moving an engagement to another product issues a destination number; moving to an unnumbered product clears it.
5. Callers cannot set an issued number or the counter through the APIs. The database enforces uniqueness for non-null numbers within a product.

This does not renumber old engagements when a format changes, guarantee gapless references after deletion, reset counters, replace IDs in URLs, or allow arbitrary Python format expressions. A displayed reference changes when an engagement moves to another product; its database ID and URL remain stable.

## Alternatives and trade offs

The earlier attempt in issue #13592 used the Engagement primary key. It needs no additional sequence state and is naturally concurrent, but numbers advance across unrelated products. A maintainer explicitly rejected that behavior in the issue discussion.

Counting existing engagements per product would avoid a new counter field. It fails under concurrent inserts because both writers can count the same rows, and deleting an engagement can make a number available again. A separate sequence model would handle concurrency but adds another table and lifecycle for state owned by an existing Product. A database sequence per product would also require dynamic database objects and migration complexity.

The chosen design stores `engagement_number_format` and `engagement_number_counter` on Product and the issued `engagement_number` on Engagement. The counter is incremented while the Product row is locked with `SELECT FOR UPDATE`; the Engagement insert and increment share a transaction. This serializes writers for one product without locking unrelated products or scanning the Engagement table. A uniqueness constraint on `(product, engagement_number)` is a second line of defense. The cost is one short Product row lock per numbered creation and extra storage in the audit history tables.

## Architectural placement and coupling

The [updated logical architecture diagram](engagement-numbering-architecture.mmd) marks the new responsibility on the earlier semester's `dojo/engagement/` and `dojo/product/` module diagram. Classic views, API views, and importers already call `Engagement.save()`, so allocation at its pre-save boundary covers every creation path. The Product owns configuration and counter state; `dojo/product/numbering.py` validates and renders the restricted format. The UI and API layers only expose configuration or the issued read value. Business logic does not accept an HTTP request or serializer.

This is GRASP Information Expert: Product owns the per-product sequence, while Engagement knows when it is created or moved. It also uses Low Coupling: neither the UI nor either API duplicates allocation. The established `BaseModel.save()` wraps `pre_save_logic()` and the insert in a transaction, so the allocator uses that existing extension point. I deliberately avoided a view-only service because scan imports and copy operations would bypass it. The resulting coupling is a narrow domain dependency from Engagement to Product; the existing single `dojo` Django app and backward-compatible re-exports remain intact.

Existing code changed in `dojo/product/models.py`, `dojo/engagement/models.py`, the Product form, API serializers and v3 schemas, and engagement templates. The API v2 Product serializer uses an exclusion list, so the new private counter required an explicit exclusion. The API v3 schemas list fields explicitly, so the format and issued number required explicit additions. Audit history mirrors model fields and triggers, so a second generated migration updates those tables. These details show that the domain change crosses several presentation and persistence adapters, but there is one allocation algorithm.

An existing Engagement loaded from the database remembers its original Product ID. An ordinary save can therefore skip the Product comparison query. `refresh_from_db()` and a successful Product move update that snapshot; deferred objects fall back to a database lookup. This matters for scan import workloads that repeatedly save an existing Engagement.

## Security and compatibility

The trust boundary from the earlier security analysis is untrusted browser/API input through the authenticated application into PostgreSQL. Existing Product edit permission controls who can set the format, and existing Engagement create/move authorization controls who can cause allocation. The format validator accepts one numeric placeholder and a small literal alphabet; it does not evaluate attributes, indexes, conversions, or arbitrary expressions. The number is read only in API v2 and omitted from v3 write schemas; the counter is excluded from API v2 and v3 responses. Database uniqueness protects integrity if application validation is bypassed.

Defaults and nullable columns preserve existing rows and callers. Unnumbered products add no counter writes. A Product loaded before another transaction allocated a number must not overwrite a newer counter during an unrelated edit; normal Product saves therefore exclude the server-managed counter column. One limitation remains: direct `QuerySet.update()` or `bulk_create()` on Engagement bypasses model save hooks. Production creation paths inspected for this feature use `save()` or `objects.create()`; a direct bulk insert would require its own allocation policy.

## Revision after implementation

The first design note covered allocation, formatting, and product moves. Self review exposed a stale Product instance that could reset the counter during a normal save; the implementation now excludes that column from ordinary Product saves and has a regression test. Migration verification exposed DefectDojo's audit event tables and triggers, which required a generated follow-up migration. A later performance review exposed an unnecessary Product comparison query on routine Engagement saves; original Product ID tracking removes it. The accepted Product row lock and model save boundary remained the right choice after these findings.
