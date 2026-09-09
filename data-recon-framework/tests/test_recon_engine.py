import pytest
from pyspark.sql import SparkSession

from recon_framework.recon_engine import reconcile


@pytest.fixture(scope="module")
def spark():
    s = (
        SparkSession.builder.master("local[2]")
        .appName("recon-tests")
        .getOrCreate()
    )
    yield s
    s.stop()


def test_full_row_pass_when_identical(spark):
    src = spark.createDataFrame([(1, "a"), (2, "b")], ["id", "val"])
    tgt = spark.createDataFrame([(1, "a"), (2, "b")], ["id", "val"])
    src.createOrReplaceTempView("src_t")
    tgt.createOrReplaceTempView("tgt_t")

    result = reconcile(spark, "src_t", "tgt_t", compare_mode="full_row")
    assert result.status == "PASS"
    assert result.missing_in_target == 0


def test_full_row_fail_when_row_missing(spark):
    src = spark.createDataFrame([(1, "a"), (2, "b")], ["id", "val"])
    tgt = spark.createDataFrame([(1, "a")], ["id", "val"])
    src.createOrReplaceTempView("src_t2")
    tgt.createOrReplaceTempView("tgt_t2")

    result = reconcile(spark, "src_t2", "tgt_t2", compare_mode="full_row")
    assert result.status == "FAIL"
    assert result.missing_in_target == 1


def test_key_mode_ignores_non_key_column_differences(spark):
    src = spark.createDataFrame([(1, "a"), (2, "b")], ["id", "val"])
    tgt = spark.createDataFrame([(1, "different"), (2, "b")], ["id", "val"])
    src.createOrReplaceTempView("src_t3")
    tgt.createOrReplaceTempView("tgt_t3")

    result = reconcile(
        spark, "src_t3", "tgt_t3", compare_mode="key", key_columns=["id"]
    )
    assert result.status == "PASS"
    assert result.missing_in_target == 0


def test_key_mode_fails_when_key_missing(spark):
    src = spark.createDataFrame([(1, "a"), (2, "b")], ["id", "val"])
    tgt = spark.createDataFrame([(1, "a")], ["id", "val"])
    src.createOrReplaceTempView("src_t4")
    tgt.createOrReplaceTempView("tgt_t4")

    result = reconcile(
        spark, "src_t4", "tgt_t4", compare_mode="key", key_columns=["id"]
    )
    assert result.status == "FAIL"
    assert result.missing_in_target == 1
