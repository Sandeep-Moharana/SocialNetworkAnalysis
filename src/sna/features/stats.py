"""
Network statistics: the overall "shape" of the graph.

Built in two layers:
  1. vertex_stats(): one row per vertex with
         degree, triangles, local clustering coefficient, component
  2. small aggregations of that table:
         degree_distribution(), degree_histogram(), component_sizes(), summarize()

Terms used below:
  degree       number of connections of a vertex (undirected: number of friends)
  neighbors    distinct vertices connected to v, ignoring edge direction
  triangle     three vertices that are all connected to each other
  clustering   fraction of a vertex's friend pairs that are friends themselves
  component    a group of vertices that can all reach each other
"""
from typing import Dict

from graphframes import GraphFrame
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

def _neighbor_pairs():
    """Column expression: number of pairs among a vertex's neighbors, k * (k - 1) / 2.
    (A function, not a constant: Spark columns can only be built once Spark is running.)"""
    return F.col("neighbors") * (F.col("neighbors") - 1) / 2


# ---------------------------------------------------------------------------
# Layer 1: per-vertex statistics
# ---------------------------------------------------------------------------

def vertex_degrees(graph: GraphFrame, directed: bool) -> DataFrame:
    """id, in_degree, out_degree, degree.

    Undirected data is stored in both directions, so in = out = number of friends,
    and `degree` is that number. For directed data, degree = in + out.
    """
    degrees = (
        graph.vertices.select("id")
        .join(graph.inDegrees, "id", "left")
        .join(graph.outDegrees, "id", "left")
        .fillna(0, subset=["inDegree", "outDegree"])   # vertices with no edges get 0
    )
    total = (F.col("inDegree") + F.col("outDegree")) if directed else F.col("outDegree")
    return degrees.select(
        "id",
        F.col("inDegree").alias("in_degree"),
        F.col("outDegree").alias("out_degree"),
        total.alias("degree"),
    )


def neighbor_counts(graph: GraphFrame) -> DataFrame:
    """id, neighbors: distinct vertices connected to id, ignoring direction.

    For undirected data this equals the degree. For directed data, a mutual pair
    (a->b and b->a) counts as ONE neighbor, which is what clustering needs.
    """
    e = graph.edges.select("src", "dst")
    both_ways = e.union(e.select(F.col("dst").alias("src"), F.col("src").alias("dst"))).distinct()
    counts = both_ways.groupBy(F.col("src").alias("id")).agg(F.count("*").alias("neighbors"))
    return graph.vertices.select("id").join(counts, "id", "left").fillna(0, subset=["neighbors"])


def local_clustering(graph: GraphFrame) -> DataFrame:
    """id, neighbors, triangles, clustering.

    clustering(v) = triangles(v) / (k * (k - 1) / 2), with k = neighbors(v).
    Example: v has 4 friends -> 6 possible friend pairs. If 3 of those pairs are
    friends with each other, clustering = 3 / 6 = 0.5.
    Vertices with fewer than 2 neighbors have no pairs: clustering = 0 (NetworkX convention).
    """
    # triangleCount() ignores edge direction and returns the vertices plus a "count" column.
    triangles = graph.triangleCount().select("id", F.col("count").alias("triangles"))
    return (
        neighbor_counts(graph)
        .join(triangles, "id")
        .withColumn(
            "clustering",
            F.when(F.col("neighbors") >= 2, F.col("triangles") / _neighbor_pairs()).otherwise(0.0),
        )
    )


def components(graph: GraphFrame) -> DataFrame:
    """id, component: vertices with the same component id can reach each other.

    Direction is ignored ("weakly connected" components).

    algorithm="graphx": Spark's classic GraphX implementation. The default
    ("graphframes") saves every 2nd round to the checkpoint folder and DELETES older
    rounds. When a worker left mid-job (Phase 2 fault-tolerance test), Spark had to
    recompute lost data from such a deleted file and the job failed. GraphX recomputes
    lost pieces from their lineage instead. (Simply turning those checkpoints off is
    not an option: the query plan then grows every round and runs out of memory.)
    Same answer: each component is labelled with its smallest vertex id.
    """
    return graph.connectedComponents(algorithm="graphx").select("id", "component")


def vertex_stats(graph: GraphFrame, directed: bool) -> DataFrame:
    """All per-vertex statistics in one table:
    id, in_degree, out_degree, degree, neighbors, triangles, clustering, component."""
    return (
        vertex_degrees(graph, directed)
        .join(local_clustering(graph), "id")
        .join(components(graph), "id")
    )


# ---------------------------------------------------------------------------
# Layer 2: aggregations of the vertex_stats table
# ---------------------------------------------------------------------------

def degree_distribution(vstats: DataFrame) -> DataFrame:
    """degree, vertices: how many vertices have each exact degree."""
    return vstats.groupBy("degree").agg(F.count("*").alias("vertices")).orderBy("degree")


def degree_histogram(vstats: DataFrame) -> DataFrame:
    """bucket, vertices with power-of-two buckets: 1, 2-3, 4-7, 8-15, ...

    Social networks have a few huge hubs and many small vertices, so equal-width
    buckets would put almost everyone in the first one. bucket = floor(log2(degree)).
    Degree-0 vertices get bucket -1.
    """
    bucket = F.when(F.col("degree") == 0, F.lit(-1)).otherwise(F.floor(F.log2("degree")))
    return vstats.groupBy(bucket.alias("bucket")).agg(F.count("*").alias("vertices")).orderBy("bucket")


def component_sizes(vstats: DataFrame) -> DataFrame:
    """component, size: largest component first."""
    return vstats.groupBy("component").agg(F.count("*").alias("size")).orderBy(F.desc("size"))


def summarize(vstats: DataFrame, comp_sizes: DataFrame, directed: bool) -> Dict[str, object]:
    """Whole-graph numbers as a dict (easy to print, and to save as a one-row table)."""
    row = vstats.agg(
        F.count("*").alias("vertices"),
        F.sum("out_degree").alias("edge_rows"),          # every edge row has exactly one source
        F.min("degree").alias("min_degree"),
        F.expr("percentile_approx(degree, 0.5)").alias("median_degree"),
        F.avg("degree").alias("avg_degree"),
        F.max("degree").alias("max_degree"),
        F.sum("triangles").alias("triangle_corners"),     # each triangle is counted at all 3 corners
        F.sum(_neighbor_pairs()).alias("neighbor_pairs"),
        F.avg("clustering").alias("avg_clustering"),
    ).first()
    largest = comp_sizes.first()

    n, edge_rows = row["vertices"], row["edge_rows"]
    return {
        "vertices": n,
        # Undirected data stores each friendship twice.
        "connections": edge_rows if directed else edge_rows // 2,
        # Density = existing edges / possible edges. Possible ordered pairs = n(n-1); counting
        # edge ROWS makes the same formula right for both directed and undirected data.
        "density": edge_rows / (n * (n - 1)) if n > 1 else 0.0,
        "min_degree": row["min_degree"],
        "median_degree": row["median_degree"],
        "avg_degree": row["avg_degree"],
        "max_degree": row["max_degree"],
        "components": comp_sizes.count(),
        "largest_component": largest["size"],
        "triangles": row["triangle_corners"] // 3,
        "avg_clustering": row["avg_clustering"],
        # Transitivity (global clustering) = closed friend pairs / all friend pairs,
        # over the whole graph. Unlike avg_clustering, big hubs weigh more here.
        "transitivity": (row["triangle_corners"] / row["neighbor_pairs"]) if row["neighbor_pairs"] else 0.0,
    }
