"""
Write DataFrames to HDFS. One place to change if we ever switch format (e.g. CSV for Gephi).

We use Parquet: columnar, compressed, and it stores column types, so reading it back
is much faster than re-parsing text.
"""
from pyspark.sql import DataFrame

from sna.config import Config


def write_parquet(df: DataFrame, path: str) -> None:
    # "overwrite" makes jobs re-runnable: running a job twice gives the same result.
    df.write.mode("overwrite").parquet(path)


def write_result(df: DataFrame, cfg: Config, dataset: str, result: str) -> str:
    """Save an analysis result to <output>/<dataset>/<result>/ and return the path."""
    path = cfg.output_path(dataset, result)
    write_parquet(df, path)
    print(f"[write] {result} -> {path}")
    return path
