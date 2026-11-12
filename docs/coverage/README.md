# Test coverage for A7: Automated Testing

DefectDojo ships no coverage tooling, so this directory adds the minimum needed to measure it.

| File | Purpose |
|---|---|
| `.coveragerc` | coverage.py configuration: **branch coverage on**, `source = dojo`, migrations and settings omitted, subprocess/thread/multiprocessing tracking so Django's parallel test workers are counted |
| `run-coverage.sh <label>` | Runs the unit suite under coverage in the same three phases as `docker/entrypoint-unit-tests.sh` (parallel, `non-parallel`, `transactional`; `performance` excluded) and writes `<label>/report.txt` |
| `baseline/report.txt` | Per-file report **before** any A7 change |
| `after/report.txt` | Per-file report after the A7 tests, fix and refactor |
| `post-merge-unit/report.txt` | Current coverage after merging upstream, run in the unit-test Docker environment |

```bash
# with a migrated PostgreSQL test database and the DD_* variables from docker-compose.override.unit_tests.yml
docs/coverage/run-coverage.sh baseline
```

## Baseline (before A7)

**Tool:** coverage.py 7.17.2, measuring **line and branch coverage**. The headline figure coverage.py prints is the combined one: `(covered lines + covered branches) / (statements + branches)`.

| Measure | Covered / total | Percent |
|---|---|---|
| Lines | 51,202 / 66,907 | 76.5% |
| Branches | 14,038 / 22,974 | 61.1% |
| **Combined (reported total)** | 65,240 / 89,881 | **72.6%** |

**What ran:** 5,345 tests in the three phases (5,293 + 45 + 7), of which 537 were skipped by the suite itself (498 + 32 + 7; reasons not investigated).

**Environment, which differs from CI:** macOS arm64, Python 3.14.4 (the Docker image pins 3.14.6), a local PostgreSQL 18.4, `psycopg[binary]` in place of `psycopg[c]`, and `uwsgi` not installed (it does not build here and no test imports it). I did not run the Docker suite.

**Three tests did not pass at baseline, none caused by A7:**

- `unittests.test_jira_config_product...test_add_jira_instance_unknown_host` fails every time here. It points JIRA at a fake hostname and expects a particular error; in this sandbox the DNS failure surfaces differently.
- `unittests.authorization.test_authorization.TestUserHasPermissionInputForms` (error in `setUpClass`) and `unittests.test_v3_alias_authorized_users_api_authz...test_asset_edit_cannot_add_authorized_users` failed only in the parallel run and **passed when re-run serially**, so they depend on test order or shared state.

## Do I believe the number?

Partly. 72.6% says 72.6% of the code *ran* while the suite ran; it says nothing about whether any test looked at a result. Two things in the data show the gap:

- `dojo/importers/auto_create_context.py` is **90% line-covered**, yet no test targets it. It is reached only as a side effect of REST API import tests that check the HTTP status, so its error paths (a product that conflicts with the supplied product type, an engagement that does not belong to the product) are the exact lines that never run.
- The finding-group helpers in `dojo/finding/helper.py` (`group_findings_by` and the functions it calls) have **no executed lines at all**, although grouping is used by the bulk-edit screen and by JIRA grouped pushes.

The line figure is also much higher than the branch figure (76.5% vs 61.1%): a line that ran once is "covered" even if only one side of its `if` was ever taken.

## After A7

Same tool, config and environment as the baseline.

| Measure | Before | After |
|---|---|---|
| Lines | 51,202 / 66,907 (76.5%) | 51,273 / 66,905 (76.6%) |
| Branches | 14,038 / 22,974 (61.1%) | 14,072 / 22,974 (61.3%) |
| **Combined (reported total)** | **72.6%** | **72.7%** |

The refactor removed two statements, which is why the line total went from 66,907 to 66,905.

| File | Before | After | Missed statements |
|---|---|---|---|
| `dojo/finding/helper.py` | 76.9% | 83.6% | 177 to 115 |
| `dojo/importers/auto_create_context.py` | 90.4% | 98.8% | 9 to 1 |
| `dojo/importers/base_importer.py` | 80.9% | 81.6% | 81 to 78 |

**What ran:** 5,435 tests (5,383 + 45 + 7), 537 skipped by the suite. One test failed, `test_add_jira_instance_unknown_host`, the same DNS-dependent test that fails at baseline. The two order-dependent failures from the baseline run did not recur.

**What this does and does not say.** The project went up 0.1 percentage points because 86 tests aimed at three components cannot move a 66,907-statement codebase much; the per-file rows are the honest measure. The one line left uncovered in `auto_create_context.py` is the re-check for an engagement created by a concurrent request (`return existing`), which cannot be reached without two racing threads. A higher number would not mean the tests are good: after writing them I checked that by breaking the production code eight different ways and confirming the new tests failed each time. That check is small and manual, not a mutation-testing tool.

## Post-merge verification (November 11, 2026)

The upstream sync changed both application code and the test suite. The original A7 before/after figures above remain a comparison on the original revision; they must not be compared as if they were a before/after pair with this run.

The three A7 characterization modules were updated for upstream's case-insensitive severity normalization and its revised product-type conflict message. All 86 tests in those modules passed. The full three-phase suite ran in the `unit_tests` Docker configuration with coverage.py 7.17.2 and Python 3.14.8: 8,718 tests in phase 1, 45 in phase 2, and 7 in phase 3. All three phases passed; 554 tests were skipped by the suite.

| Measure | Covered / total | Percent |
|---|---:|---:|
| Lines | 69,800 / 84,878 | 82.2% |
| Branches | 20,463 / 29,698 | 68.9% |
| **Combined (reported total)** | **90,263 / 114,576** | **78.8%** |

This is an execution measure, not proof that every covered path has a useful assertion. The full per-file output is in `post-merge-unit/report.txt`.
