"""
Create the SparkSession that every job uses.

Notice what is NOT here: master URL, HDFS address, memory. spark-submit reads those
from docker/spark-defaults.conf, so this code runs unchanged on 1 laptop or 3 PCs.
"""
from pyspark.sql import SparkSession

from sna.config import Config


def get_spark(app_name: str, cfg: Config) -> SparkSession:
    spark = SparkSession.builder.appName(app_name).getOrCreate()

    # Spark prints a lot of INFO lines; WARN keeps our own output readable.
    spark.sparkContext.setLogLevel("WARN")

    # Iterative graph algorithms (e.g. connectedComponents) save intermediate results
    # here so a lost executor doesn't force recomputing from the start.
    spark.sparkContext.setCheckpointDir(cfg.checkpoints)
    return spark
