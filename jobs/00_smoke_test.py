"""
Smoke test: proves the whole stack works end to end before we write real features.

Checks that:
  1. The driver (spark-client) connects to the standalone master.
  2. Executors on the worker containers run tasks.
  3. GraphFrames is on the classpath and PageRank works.
  4. Spark can write to and read back from HDFS.

Run from the repo root on your laptop:
    .\\scripts\\submit.ps1 jobs\\00_smoke_test.py
"""
import socket

from pyspark.sql import SparkSession
from graphframes import GraphFrame

spark = SparkSession.builder.appName("sna-00-smoke-test").getOrCreate()
spark.sparkContext.setLogLevel("WARN")

# --- 1 + 2: is the work really distributed? ---------------------------------
# Run 8 small tasks and ask each one which machine (container) it ran on.
hosts = (
    spark.sparkContext.parallelize(range(8), 8)
    .map(lambda _: socket.gethostname())
    .distinct()
    .collect()
)
print(f"\n[1] Tasks ran on executors: {sorted(hosts)}")

# --- 3: GraphFrames on a tiny graph we can check by hand ---------------------
# Edges point "follower -> followed". Alice is followed by everyone else,
# so she must have the highest in-degree and the highest PageRank.
vertices = spark.createDataFrame(
    [("a", "Alice"), ("b", "Bob"), ("c", "Carol"), ("d", "Dave")], ["id", "name"]
)
edges = spark.createDataFrame(
    [("b", "a"), ("c", "a"), ("d", "a"), ("a", "b"), ("c", "b")], ["src", "dst"]
)
g = GraphFrame(vertices, edges)

print("[2] In-degrees:")
g.inDegrees.orderBy("inDegree", ascending=False).show()

# Use tol (run until scores change by less than tol), not a fixed maxIter:
# Alice and Bob follow each other, so rank flows back and forth between them and
# with too few iterations their order flips each round. Converged answer, by hand:
# Alice ~1.884, Bob ~1.815, Carol = Dave = 0.15 (nobody follows them).
ranks = g.pageRank(resetProbability=0.15, tol=0.0001).vertices
print("[3] PageRank:")
ranks.select("id", "name", "pagerank").orderBy("pagerank", ascending=False).show()

top = ranks.orderBy("pagerank", ascending=False).first()
assert top["id"] == "a", f"Expected Alice to rank first, got {top['name']}"

# --- 4: HDFS round trip -------------------------------------------------------
path = "/sna/tmp/smoke_test"          # resolved against hdfs://namenode:8020
ranks.write.mode("overwrite").parquet(path)
count = spark.read.parquet(path).count()
assert count == 4, f"Expected 4 rows back from HDFS, got {count}"
print(f"[4] Wrote and read back {count} rows at hdfs://namenode:8020{path}")

print("\nSMOKE TEST PASSED\n")
spark.stop()
