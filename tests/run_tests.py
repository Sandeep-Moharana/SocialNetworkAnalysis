"""
Run all unit tests inside the spark-client container.

    .\\scripts\\test.ps1            (same as: .\\scripts\\submit.ps1 tests\\run_tests.py)

The tests use Spark in LOCAL mode (master local[2]): everything runs inside the
spark-client container, without the workers or HDFS. That keeps them fast, and a
failing test points at our code, not at the cluster. The cluster itself is checked
by jobs/00_smoke_test.py.

Each test builds a tiny graph whose correct answer can be worked out by hand.
"""
import os
import sys
import unittest

from pyspark.sql import SparkSession

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    # .master() set in code overrides spark.master from spark-defaults.conf.
    spark = SparkSession.builder.master("local[2]").appName("sna-tests").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    # Local folder (file://), so connectedComponents works without HDFS.
    spark.sparkContext.setCheckpointDir("file:///tmp/sna-test-checkpoints")
    print(f"Spark master: {spark.sparkContext.master}\n")

    # Every tests/test_*.py file is picked up automatically.
    suite = unittest.defaultTestLoader.discover(TESTS_DIR, pattern="test_*.py", top_level_dir=TESTS_DIR)
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    spark.stop()
    sys.exit(0 if result.wasSuccessful() else 1)   # non-zero exit = test.ps1 reports failure


if __name__ == "__main__":
    main()
