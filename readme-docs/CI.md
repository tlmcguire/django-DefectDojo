# Continuous Integration

This describes what actually runs against a pull request in this repository, and what to do
when one of those checks goes red. It's scoped to the workflows a contributor's PR triggers;
release automation (tagging, publishing images, merging `master` back into `dev`) is documented
separately in [RELEASING.md](RELEASING.md), and migration-history conflicts are covered in
[CONTRIBUTING.md](CONTRIBUTING.md#database-migrations).

All workflow definitions live in [`.github/workflows/`](../.github/workflows).

## What runs on a pull request

Everything is chained from [`unit-tests.yml`](../.github/workflows/unit-tests.yml), which is
the workflow whose `Unit Tests Complete` job is the actual required status check:

1. **`ruff` (lint)** - [`ruff.yml`](../.github/workflows/ruff.yml). Runs first and gates
   everything else: nothing downstream starts until `ruff check` passes.
2. **`changes`** - detects a docs-only PR (every changed file under `docs/`). If true, the
   heavy jobs below skip themselves, but `Unit Tests Complete` still reports success so a
   docs-only PR isn't blocked waiting on jobs that will never run.
3. **`build-docker-containers`** - [`build-docker-images-for-testing.yml`](../.github/workflows/build-docker-images-for-testing.yml).
   Builds the `django`, `nginx`, and `integration-tests` images (alpine and debian variants)
   and uploads them as artifacts for every job below to reuse, rather than each rebuilding.
   A pull request builds `linux/amd64` only; the merge queue and manual dispatch also build
   `linux/arm64`.
4. **`test-rest-framework`** - [`rest-framework-tests.yml`](../.github/workflows/rest-framework-tests.yml).
   The Django/DRF unit test suite (`unittests/`), run against a Postgres 18 container. It
   restores a cached, already-migrated database snapshot when the migration-relevant files
   haven't changed, since applying the full migration history from scratch takes about 100
   seconds.
   Runs twice on the merge queue: once with `DD_V3_FEATURE_LOCATIONS` off, once on.
5. **`test-user-interface`** - [`integration-tests.yml`](../.github/workflows/integration-tests.yml).
   Playwright-driven UI tests, split into a matrix of test-file groups sized by measured
   runtime (see the comments in that file) rather than by file count, so no one group
   dominates the wall clock.
6. **`test-k8s`** - [`k8s-tests.yml`](../.github/workflows/k8s-tests.yml). Deploys the built
   images into a Minikube cluster via the Helm chart, against both the newest and the oldest
   officially-supported Kubernetes versions.
7. **`test-performance`** - [`performance-tests.yml`](../.github/workflows/performance-tests.yml).
8. **`unit-tests-complete`** - the actual required check. It's `always()` so it still reports
   when an upstream job fails or is skipped, and treats a skipped dependency as a failure
   *unless* the PR is docs-only, in which case that specific skip is expected.

Alongside that chain, a few workflows run independently and aren't part of the required-check
gate:

- **[`shellcheck.yml`](../.github/workflows/shellcheck.yml)** - lints shell scripts.
- **[`migration-graph.yml`](../.github/workflows/migration-graph.yml)** - checks that
  `dojo/db_migrations/` has exactly one leaf migration (see Troubleshooting below).
- **[`validate_docs_build.yml`](../.github/workflows/validate_docs_build.yml)** - only runs
  when `docs/**` or `.github/workflows/*` changed; does a production Hugo build of the docs
  site and checks internal links with `lychee`.
- **[`detect-merge-conflicts.yaml`](../.github/workflows/detect-merge-conflicts.yaml)** - labels
  a PR `conflicts-detected` if it can't merge cleanly.
- **[`pr-labeler.yml`](../.github/workflows/pr-labeler.yml)** and
  **[`cancel-outdated-workflow-runs.yml`](../.github/workflows/cancel-outdated-workflow-runs.yml)** -
  housekeeping (auto-labeling, canceling superseded runs on force-push).

## The merge queue

`bugfix` (and the other protected branches) uses a GitHub merge queue rather than merging a PR
the moment its checks go green. When a PR enters the queue, GitHub builds a **speculative merge
commit** - the PR merged onto the current tip of the target branch - and re-runs the required
checks (`ruff-linting`, `Unit Tests Complete`) against *that* commit, not the PR's own branch
tip. This is the only point that actually tests the combination of your change with whatever
else has landed since you branched; two PRs can each be green individually and broken together,
and nothing before the queue would catch that.

Two consequences worth knowing:

- **A queued run can take longer than your PR's own run.** The PR-tier build is `linux/amd64`
  only and runs the light matrix; the queue re-runs the full matrix (`linux/arm64` included)
  against the speculative commit. Longer queue time isn't a hang, it's the queue actually
  testing more.
- **The queue can eject your PR** if the speculative-commit run fails, even though your PR's
  own checks were green. That means the combination broke, not necessarily your code in
  isolation - check the failing job's logs to see which side introduced the problem.

## Reproducing CI locally

Match the check that's failing before pushing another commit to find out:

- **Lint (`ruff`):**
  ```bash
  pip install -r requirements-lint.txt
  ruff check .
  # or, to fix what's auto-fixable:
  ruff check --fix .
  ```
- **A specific unit test** (needs `docker/setEnv.sh dev` and `docker compose up` running first):
  ```bash
  ./run-unittest.sh --test-case unittests.tools.test_stackhawk_parser.TestStackHawkParser
  ```
- **A specific integration/UI test file** (same dev-mode prerequisite):
  ```bash
  ./run-integration-test-dev.sh tests/finding_test.py
  ```
- **The full integration suite**, via `run-integration-tests.sh` - see `--help` on that script;
  it's the same entrypoint the `integration-tests.yml` matrix drives, just against one test
  case at a time.
- **The docs site build**, if you touched `docs/`:
  ```bash
  cd docs && npm ci && hugo --minify --gc --config config/production/hugo.toml
  ```
- **Shellcheck**, if you touched a `.sh` file:
  ```bash
  shellcheck -e SC1091 -e SC2086 path/to/script.sh
  ```

## Troubleshooting

**A required check sits at "Expected — waiting for status to be reported" forever.**
This means the workflow that produces that check context never triggered for your event. It's
the reason `unit-tests.yml` deliberately has no `paths`/`paths-ignore` filter on its
`pull_request` trigger - a required check that's also path-filtered can permanently starve a PR
whose files don't match the filter. If you hit this on a workflow you don't maintain the
trigger for, it's a CI configuration bug, not something to work around in your PR.

**`Unit Tests Complete` fails but every individual job you can see is green.**
Look at whether one of its dependencies was *skipped* rather than passed. That job treats a
skipped dependency as a failure unless your PR was detected as docs-only - if it wasn't, and
something upstream was skipped anyway (usually because an earlier required job in the chain,
like `ruff`, failed first), fix that earlier job.

**Migration Graph Check fails.**
This means `dojo/db_migrations/` has more than one leaf migration - i.e., two migrations exist
whose dependency graph forks instead of forming a single line. This usually happens when your
branch's migration and a migration that landed on the base branch after you branched both claim
the same parent. Resolve it the same way as a `max_migration.txt` conflict: see
[CONTRIBUTING.md § Database migrations](CONTRIBUTING.md#database-migrations) for the rename/
`rebase_migration` procedure. The check itself (`scripts/check_migration_leaves.py`) is
stdlib-only and fast to run locally: `python3 scripts/check_migration_leaves.py`.

**A Docker image build job fails or times out.**
`build-docker-images-for-testing.yml` has a 15-minute timeout per image. A transient failure is
usually a Docker Hub base-image pull timing out - re-running the job is often enough. If it
fails consistently, check whether `Dockerfile.django-<os>` or `Dockerfile.nginx-<os>` actually
builds locally first (`docker compose build`), since the CI build uses the same Dockerfiles.

**`k8s` job fails or hits its 30-minute timeout.**
That timeout is a deliberate hard ceiling (this job has hung for hours without one). Check the
step logs for where it actually stalled - Minikube bring-up and the Helm dependency/deploy steps
are the two slow points most likely to stick. A genuine chart or manifest problem will usually
fail well before the timeout; hitting the full 30 minutes points at infrastructure flakiness in
the runner, not your change.

**Integration test job fails and you need the logs.**
Each matrix entry is a test-file group (see the comment block in `integration-tests.yml` for how
the groups are sized). The job's name tells you which group failed; open that job's log and look
for the `Running: <file>` / `Success: <file>` markers the entrypoint prints, which tell you
exactly which file in the group was running when it broke. `run-integration-test-dev.sh` lets
you reproduce a single file locally without waiting on the whole group.

**Your PR is labeled `conflicts-detected`.**
Resolve the merge conflict against the target branch; the label and the failing check clear
automatically once the branch merges cleanly. `detect-merge-conflicts.yaml` runs with
`continue-on-error: true` because the underlying action has a high error rate, so a transient
red run here (with no `conflicts-detected` label applied) can usually be ignored.

**Rest Framework unit tests are slow / a migration change doesn't seem to take effect.**
The job restores a cached, pre-migrated database snapshot keyed on `requirements.txt`,
`dojo/db_migrations/**`, `dojo/models.py`, and a handful of other schema-relevant files (see the
`db-key` step in `rest-framework-tests.yml` for the exact list). If you change something
schema-relevant that isn't in that hash key, you'll see stale-migration behavior in CI that
doesn't reproduce locally - that's a cache-key bug worth reporting, not a flake to retry past.
