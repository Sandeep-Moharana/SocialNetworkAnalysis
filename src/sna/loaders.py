"""
Turn a raw edge-list file on HDFS into a GraphFrame.

    raw text ──parse──► edges(src, dst) ──clean──► edges + vertices(id) ──► GraphFrame
                                                         │
                                  saved once to <processed>/<dataset>/ as Parquet

The first run parses the text file and saves the cleaned tables. Later runs read
the Parquet directly, which is faster. Use rebuild=True after changing the cleaning rules.
"""
from graphframes import GraphFrame
from pyspark.errors import AnalysisException
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from sna.config import Config, DatasetConfig
from sna.storage import write_parquet


def read_edge_list(spark: SparkSession, path: str, ds: DatasetConfig) -> DataFrame:
    """Parse lines like '0 1' into rows (src=0, dst=1)."""
    lines = spark.read.text(path).select(F.trim("value").alias("line"))
    parts = F.split("line", ds.separator)
    return (
        lines
        .where(F.col("line") != "")                          # blank lines
        .where(~F.col("line").startswith(ds.comment_prefix))  # header comments
        # SNAP ids are integers. Anything that isn't becomes null and is dropped below.
        .select(parts[0].cast("long").alias("src"), parts[1].cast("long").alias("dst"))
        .dropna()
    )


def clean_edges(edges: DataFrame, directed: bool) -> DataFrame:
    """Remove self-loops and duplicates. For undirected data, store both directions."""
    edges = edges.where(F.col("src") != F.col("dst"))
    if not directed:
        # GraphFrames edges always have a direction. A friendship A–B becomes
        # A->B and B->A, so "friends of X" is just "edges where src = X".
        reversed_edges = edges.select(F.col("dst").alias("src"), F.col("src").alias("dst"))
        edges = edges.union(reversed_edges)
    return edges.distinct()


def vertices_from_edges(edges: DataFrame) -> DataFrame:
    """Every id that appears in an edge. (Users with no edges at all are not in an edge list.)"""
    return (
        edges.select(F.col("src").alias("id"))
        .union(edges.select(F.col("dst").alias("id")))
        .distinct()
    )


def load_graph(spark: SparkSession, cfg: Config, dataset: str, rebuild: bool = False) -> GraphFrame:
    ds = cfg.dataset(dataset)
    vertices_path = cfg.processed_path(dataset, "vertices")
    edges_path = cfg.processed_path(dataset, "edges")

    if not rebuild:
        try:
            graph = GraphFrame(spark.read.parquet(vertices_path), spark.read.parquet(edges_path))
            print(f"[load] using processed graph in {cfg.processed}/{dataset}/")
            return graph
        except AnalysisException:
            pass  # not built yet (path does not exist): fall through and build it

    raw_path = cfg.raw_path(dataset)
    print(f"[load] building graph from {raw_path}")
    edges = clean_edges(read_edge_list(spark, raw_path, ds), ds.directed)
    write_parquet(edges, edges_path)
    # Vertices are derived from the SAVED edges, so the raw text is parsed only once.
    write_parquet(vertices_from_edges(spark.read.parquet(edges_path)), vertices_path)
    print(f"[load] saved processed graph to {cfg.processed}/{dataset}/")

    return GraphFrame(spark.read.parquet(vertices_path), spark.read.parquet(edges_path))
