"""
Entry point invoked by the Databricks job's python_wheel_task
(entry_point: "reconcile" in resources/recon_job.yml).

Parameters arrive as named CLI args because Databricks passes
named_parameters as --key=value pairs to the wheel's console script.
Exits non-zero on FAIL so the Databricks job run - and therefore the
GitLab pipeline step that triggered it - fails visibly.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from pyspark.sql import SparkSession

from recon_framework.catalog_utils import get_client, validate_table_path
from recon_framework.recon_engine import reconcile as run_reconcile

logger = logging.getLogger("recon_framework")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Source vs target table reconciliation")
    p.add_argument("--source_catalog", required=True)
    p.add_argument("--source_schema", required=True)
    p.add_argument("--source_table", required=True)
    p.add_argument("--target_catalog", required=True)
    p.add_argument("--target_schema", required=True)
    p.add_argument("--target_table", required=True)
    p.add_argument("--compare_mode", default="full_row", choices=["full_row", "key"])
    p.add_argument(
        "--key_columns",
        default="",
        help="Comma-separated key column names, required when compare_mode=key",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    source_fqn = f"{args.source_catalog}.{args.source_schema}.{args.source_table}"
    target_fqn = f"{args.target_catalog}.{args.target_schema}.{args.target_table}"
    key_columns = [c.strip() for c in args.key_columns.split(",") if c.strip()]

    # Validate both tables actually exist and are reachable before
    # spending compute on a comparison that's doomed to error out.
    w = get_client()
    for label, catalog, schema, table in [
        ("source", args.source_catalog, args.source_schema, args.source_table),
        ("target", args.target_catalog, args.target_schema, args.target_table),
    ]:
        if not validate_table_path(catalog, schema, table, w):
            logger.error("%s table not found or not accessible: %s.%s.%s", label, catalog, schema, table)
            sys.exit(2)

    spark = SparkSession.builder.getOrCreate()

    result = run_reconcile(
        spark=spark,
        source_fqn=source_fqn,
        target_fqn=target_fqn,
        compare_mode=args.compare_mode,
        key_columns=key_columns or None,
    )

    print(json.dumps(result.as_dict(), indent=2))

    if result.status != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
