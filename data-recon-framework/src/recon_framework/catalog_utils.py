"""
Workspace connection and catalog/schema/table discovery helpers.

Auth is never hardcoded here. The Databricks SDK's WorkspaceClient()
resolves credentials automatically, in this order:
  1. DATABRICKS_HOST / DATABRICKS_CLIENT_ID / DATABRICKS_CLIENT_SECRET
     (OAuth machine-to-machine, service principal) - used in CI/CD
  2. DATABRICKS_HOST / DATABRICKS_TOKEN (PAT) - used for quick local testing
  3. The Databricks CLI's configured profile (~/.databrickscfg)
  4. When running INSIDE a Databricks notebook/job, the runtime's own
     ambient auth - no env vars needed at all.
"""

from __future__ import annotations

import logging

from databricks.sdk import WorkspaceClient

logger = logging.getLogger("recon_framework")


def get_client() -> WorkspaceClient:
    """Return an authenticated WorkspaceClient using whichever auth
    method is available in the current environment."""
    w = WorkspaceClient()
    # Cheap call to fail fast with a clear error if auth is broken,
    # rather than failing later mid-reconciliation.
    me = w.current_user.me()
    logger.info("Authenticated to workspace as %s", me.user_name)
    return w


def list_catalogs(w: WorkspaceClient | None = None) -> list[str]:
    """Return the names of every catalog visible to the current identity."""
    w = w or get_client()
    catalogs = [c.name for c in w.catalogs.list()]
    logger.info("Found %d catalog(s): %s", len(catalogs), ", ".join(catalogs))
    return catalogs


def list_schemas(catalog: str, w: WorkspaceClient | None = None) -> list[str]:
    w = w or get_client()
    return [s.name for s in w.schemas.list(catalog_name=catalog)]


def list_tables(catalog: str, schema: str, w: WorkspaceClient | None = None) -> list[str]:
    w = w or get_client()
    return [t.name for t in w.tables.list(catalog_name=catalog, schema_name=schema)]


def validate_table_path(
    catalog: str, schema: str, table: str, w: WorkspaceClient | None = None
) -> bool:
    """Return True if catalog.schema.table exists and is reachable."""
    w = w or get_client()
    full_name = f"{catalog}.{schema}.{table}"
    try:
        w.tables.get(full_name=full_name)
        return True
    except Exception as exc:  # noqa: BLE001 - we want to log and return False, not crash
        logger.warning("Could not validate %s: %s", full_name, exc)
        return False


def entrypoint_list_catalogs() -> None:
    """Job entry point: `list_catalogs` in resources/recon_job.yml.

    Purely diagnostic - confirms auth works and logs what's visible,
    so a broken connection fails on this task rather than obscurely
    inside the reconciliation task.
    """
    logging.basicConfig(level=logging.INFO)
    w = get_client()
    catalogs = list_catalogs(w)
    print(f"Visible catalogs ({len(catalogs)}): {catalogs}")
