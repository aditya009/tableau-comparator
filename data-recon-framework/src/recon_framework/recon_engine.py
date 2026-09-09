"""
Core reconciliation logic: is the source table's data present in the
target table?

Two comparison modes are supported:

- "full_row" (default): every column must match exactly. Uses
  DataFrame.exceptAll, a set-based comparison that is fast even on
  large tables and needs no join key. Best when source and target
  are expected to be byte-for-byte identical (e.g. a straight copy
  or migration).

- "key": only a business key needs to exist in both tables; other
  column values are not compared. Uses a left-anti join on the
  given key columns. Best when target may have additional derived
  columns, or when you only care that no source records were lost.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict

from pyspark.sql import DataFrame, SparkSession

logger = logging.getLogger("recon_framework")

SAMPLE_LIMIT = 20  # cap how many mismatched rows we log/print


@dataclass
class ReconResult:
    source: str
    target: str
    compare_mode: str
    source_row_count: int
    target_row_count: int
    missing_in_target: int
    status: str  # "PASS" or "FAIL"

    def as_dict(self) -> dict:
        return asdict(self)


def _full_row_compare(src: DataFrame, tgt: DataFrame) -> DataFrame:
    """Rows present in src that have no exact match in tgt (all columns)."""
    return src.exceptAll(tgt)


def _key_compare(src: DataFrame, tgt: DataFrame, key_columns: list[str]) -> DataFrame:
    """Rows in src whose key has no matching row in tgt at all."""
    return src.join(tgt, on=key_columns, how="left_anti")


def reconcile(
    spark: SparkSession,
    source_fqn: str,
    target_fqn: str,
    compare_mode: str = "full_row",
    key_columns: list[str] | None = None,
) -> ReconResult:
    """Run the reconciliation and return a ReconResult.

    source_fqn / target_fqn are full three-level names, e.g.
    "prod_catalog.sales.orders".
    """
    logger.info(
        "Reconciling %s -> %s (mode=%s)", source_fqn, target_fqn, compare_mode
    )

    src = spark.table(source_fqn)
    tgt = spark.table(target_fqn)

    if compare_mode == "full_row":
        missing_df = _full_row_compare(src, tgt)
    elif compare_mode == "key":
        if not key_columns:
            raise ValueError("compare_mode='key' requires at least one key column")
        missing_df = _key_compare(src, tgt, key_columns)
    else:
        raise ValueError(f"Unknown compare_mode: {compare_mode!r}")

    missing_count = missing_df.count()

    if missing_count > 0:
        logger.warning(
            "%d row(s) in %s not found in %s (showing up to %d)",
            missing_count,
            source_fqn,
            target_fqn,
            SAMPLE_LIMIT,
        )
        missing_df.limit(SAMPLE_LIMIT).show(truncate=False)

    result = ReconResult(
        source=source_fqn,
        target=target_fqn,
        compare_mode=compare_mode,
        source_row_count=src.count(),
        target_row_count=tgt.count(),
        missing_in_target=missing_count,
        status="PASS" if missing_count == 0 else "FAIL",
    )

    logger.info("Result: %s", result.as_dict())
    return result
