# Databricks notebook source
# MAGIC %md
# MAGIC # Interactive reconciliation test
# MAGIC Run this attached to any cluster to test the reconciliation logic
# MAGIC directly - no bundle deploy, no GitLab, no job parameters.
# MAGIC Auth is ambient (the notebook runtime is already logged in).
# MAGIC
# MAGIC If `recon_framework` isn't installed on the cluster yet, run the
# MAGIC `%pip install` cell below first (point it at a built wheel, or at
# MAGIC this repo checked out on the workspace file system).

# COMMAND ----------

# MAGIC %pip install -e /Workspace/Repos/<you>/data-recon-framework
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

from recon_framework.catalog_utils import get_client, list_catalogs
from recon_framework.recon_engine import reconcile

w = get_client()
print(list_catalogs(w))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Widgets so you can change tables without editing code
# MAGIC (This is the notebook-native equivalent of "asking the user".)

# COMMAND ----------

dbutils.widgets.text("source_catalog", "")
dbutils.widgets.text("source_schema", "")
dbutils.widgets.text("source_table", "")
dbutils.widgets.text("target_catalog", "")
dbutils.widgets.text("target_schema", "")
dbutils.widgets.text("target_table", "")
dbutils.widgets.dropdown("compare_mode", "full_row", ["full_row", "key"])
dbutils.widgets.text("key_columns", "")

# COMMAND ----------

source_fqn = f"{dbutils.widgets.get('source_catalog')}.{dbutils.widgets.get('source_schema')}.{dbutils.widgets.get('source_table')}"
target_fqn = f"{dbutils.widgets.get('target_catalog')}.{dbutils.widgets.get('target_schema')}.{dbutils.widgets.get('target_table')}"
key_cols_raw = dbutils.widgets.get("key_columns")
key_columns = [c.strip() for c in key_cols_raw.split(",") if c.strip()] or None

result = reconcile(
    spark=spark,
    source_fqn=source_fqn,
    target_fqn=target_fqn,
    compare_mode=dbutils.widgets.get("compare_mode"),
    key_columns=key_columns,
)

print(result.as_dict())
