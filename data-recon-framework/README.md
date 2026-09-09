# data-recon-framework

Compares a source `catalog.schema.table` against a target
`catalog.schema.table` in Databricks Unity Catalog and reports
PASS/FAIL. Deployable as a Databricks Job via Databricks Asset
Bundles, triggerable from GitLab CI.

## How it works

1. `catalog_utils.py` authenticates to the workspace and lists/validates
   catalogs, schemas, and tables.
2. `recon_engine.py` runs the actual comparison — either a full-row
   `exceptAll` (every column must match) or a key-based anti-join
   (only a business key must exist in both).
3. `main.py` is the job entry point: parses parameters, validates both
   tables exist, runs the reconciliation, prints a JSON result, and
   exits non-zero on FAIL so the Databricks job — and the GitLab
   pipeline stage that triggered it — fails visibly.

## Two ways to run this

**While developing/debugging:** open `notebooks/interactive_test.py`
in the Databricks workspace, attach it to a cluster, fill in the
widgets, run the cells. No bundle, no GitLab, immediate feedback.

**In production:** GitLab CI deploys this as a Databricks Job (via
`databricks bundle deploy`) and triggers it (`databricks bundle run`)
with parameters. GitLab never runs Spark itself — it just tells
Databricks to run the job on its own cluster and waits for the
result.

## One-time setup

1. **Create a Databricks service principal** (account console), grant
   it `USE CATALOG` / `USE SCHEMA` / `SELECT` on whatever catalogs
   this will reconcile, and generate an OAuth secret for it.
2. **In GitLab**, go to Settings > CI/CD > Variables and add, masked +
   protected:
   - `DATABRICKS_HOST`
   - `DATABRICKS_CLIENT_ID`
   - `DATABRICKS_CLIENT_SECRET`
3. **Edit `databricks.yml`**: replace `<your-workspace-instance>` and
   `<your-service-principal-application-id>` with real values.
4. **Install the Databricks CLI locally** if you want to test bundle
   commands before pushing:
   ```
   curl -fsSL https://raw.githubusercontent.com/databricks/setup-cli/main/install.sh | sh
   databricks bundle validate --target dev
   databricks bundle deploy --target dev
   ```

## Running a reconciliation from GitLab

Go to CI/CD > Pipelines > Run pipeline, and add these as pipeline
variables for that run:

| Variable | Example |
|---|---|
| `SOURCE_CATALOG` | `legacy_catalog` |
| `SOURCE_SCHEMA` | `sales` |
| `SOURCE_TABLE` | `orders` |
| `TARGET_CATALOG` | `uc_catalog` |
| `TARGET_SCHEMA` | `sales` |
| `TARGET_TABLE` | `orders` |
| `COMPARE_MODE` | `full_row` or `key` |
| `KEY_COLUMNS` | `order_id` (only needed if COMPARE_MODE=key) |

The pipeline runs unit tests, deploys the bundle, then triggers the
job with those parameters. Pipeline goes green on PASS, red on FAIL.

## Running locally against a real workspace (no notebook, no GitLab)

```
export DATABRICKS_HOST=https://<workspace>.cloud.databricks.com
export DATABRICKS_TOKEN=<a personal access token, for local testing only>
pip install -e ".[dev]"
python -m recon_framework.main \
  --source_catalog legacy_catalog --source_schema sales --source_table orders \
  --target_catalog uc_catalog --target_schema sales --target_table orders \
  --compare_mode full_row
```

Note: this still needs a Spark session, so it only works if run
somewhere with pyspark configured against a cluster (e.g. via
Databricks Connect), or if you're only exercising `catalog_utils.py`.
The notebook path is the simplest way to test against a real cluster
interactively.

## Unit tests (no Databricks connection needed)

```
pip install -e ".[dev]"
pytest tests/ -v
```

These run against a local `pyspark` session with in-memory
DataFrames — no workspace, no credentials, no network.

## Choosing full_row vs key compare_mode

- `full_row` (default): every column must match exactly. Use when
  source and target are meant to be identical (e.g. straight copy or
  migration).
- `key`: only a business key must be present in both. Use when the
  target legitimately has extra/derived columns, or you only care
  that no source records were dropped.

## Repo layout

```
databricks.yml              Asset Bundle config (targets, workspace, wheel build)
resources/recon_job.yml     Job definition: parameters, tasks, cluster
src/recon_framework/        The actual package
  catalog_utils.py          Auth + catalog/schema/table discovery
  recon_engine.py           Comparison logic (full_row / key modes)
  main.py                   Job entry point, arg parsing, exit codes
pyproject.toml              Packaging + console-script entry points
notebooks/interactive_test.py   Manual testing notebook (widgets, no CI)
tests/test_recon_engine.py  Local pytest suite
config/recon_targets.yml    Optional: batch of table pairs (not wired in yet)
.gitlab-ci.yml               test -> deploy -> run pipeline
```
