"""
Community detection: which groups of vertices belong together?

Algorithm: Label Propagation (LPA)
    1. Every vertex starts with its own label (its id).
    2. Each round, every vertex takes the label that is most common among its neighbors.
    3. Densely connected groups quickly agree on one label, and that label is a community.
  Fast (each round is one pass over the edges) and needs no "number of communities"
  up front. Known limits, which is why we always report modularity next to it:
    * it does not always settle; more rounds usually help (ego-Facebook:
      5 rounds Q=0.789, 10 rounds Q=0.808, 20 rounds Q=0.813)
    * on tiny or very symmetric graphs, ties can make everything one community
      (two triangles joined by one edge end up as ONE group)

Quality: modularity Q
    Q = (share of edges inside communities) - (share expected if edges were random)
  For each community c, with E = number of edge rows:
    Q_c = intra_edge_rows_c / E  -  (out_degree_sum_c * in_degree_sum_c) / E^2
  This is the directed formula. On undirected data stored both ways it equals the
  classic undirected modularity, so one formula covers both kinds of data.
  Rule of thumb: Q > 0.3 means clear community structure. The maximum is 1.
"""
from typing import Dict

from graphframes import GraphFrame
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from sna.features.stats import vertex_degrees


def label_propagation(graph: GraphFrame, max_iter: int = 10) -> DataFrame:
    """id, community: the community label of each vertex."""
    return graph.labelPropagation(maxIter=max_iter).select("id", F.col("label").alias("community"))


def community_table(graph: GraphFrame, assignments: DataFrame, directed: bool) -> DataFrame:
    """One row per community, largest first:

    community               label from LPA
    size                    number of members
    internal_connections    connections with both ends inside the community
    density                 internal connections / possible ones (1.0 = everyone knows everyone)
    leader, leader_degree   best-connected member (most connections overall)
    intra_edge_rows, out_degree_sum, in_degree_sum   inputs for modularity()
    """
    members = vertex_degrees(graph, directed).join(assignments, "id")

    # Tag each edge with the community of both ends; keep the ones inside one community.
    a = assignments
    intra = (
        graph.edges
        .join(a.select(F.col("id").alias("src"), F.col("community").alias("src_c")), "src")
        .join(a.select(F.col("id").alias("dst"), F.col("community").alias("dst_c")), "dst")
        .where(F.col("src_c") == F.col("dst_c"))
        .groupBy(F.col("src_c").alias("community"))
        .agg(F.count("*").alias("intra_edge_rows"))
    )

    per_community = members.groupBy("community").agg(
        F.count("*").alias("size"),
        F.sum("out_degree").alias("out_degree_sum"),
        F.sum("in_degree").alias("in_degree_sum"),
        F.max_by("id", "degree").alias("leader"),
        F.max("degree").alias("leader_degree"),
    )

    # Undirected data stores each friendship twice, so 2 edge rows = 1 connection.
    rows_per_connection = 1 if directed else 2
    possible_rows = F.col("size") * (F.col("size") - 1)   # ordered pairs of members
    return (
        per_community
        .join(intra, "community", "left")                 # communities with no inner edges -> null
        .fillna(0, subset=["intra_edge_rows"])
        .withColumn("internal_connections", (F.col("intra_edge_rows") / rows_per_connection).cast("long"))
        .withColumn("density", F.when(F.col("size") > 1, F.col("intra_edge_rows") / possible_rows)
                                .otherwise(0.0))
        .select("community", "size", "internal_connections", "density", "leader", "leader_degree",
                "intra_edge_rows", "out_degree_sum", "in_degree_sum")
        .orderBy(F.desc("size"), "community")
    )


def modularity(table: DataFrame, edge_rows: int) -> float:
    """Modularity Q of a partition (formula in the module docstring)."""
    if edge_rows == 0:
        return 0.0
    e = float(edge_rows)
    q = table.agg(
        F.sum(F.col("intra_edge_rows") / e - (F.col("out_degree_sum") * F.col("in_degree_sum")) / (e * e))
    ).first()[0]
    return float(q)


def size_histogram(table: DataFrame) -> DataFrame:
    """bucket, communities, vertices for size ranges 1-9, 10-99, 100-999, ...
    bucket = number of digits - 1 = floor(log10(size))."""
    return (
        table.groupBy(F.floor(F.log10("size")).alias("bucket"))
        .agg(F.count("*").alias("communities"), F.sum("size").alias("vertices"))
        .orderBy("bucket")
    )


def summarize(table: DataFrame, q: float, n_vertices: int) -> Dict[str, object]:
    """Whole-partition numbers as a dict."""
    row = table.agg(
        F.count("*").alias("communities"),
        F.max("size").alias("largest"),
        F.expr("percentile_approx(size, 0.5)").alias("median_size"),
        F.sum(F.when(F.col("size") == 1, 1).otherwise(0)).alias("singletons"),
        F.sum("internal_connections").alias("internal_connections"),
    ).first()
    return {
        "communities": row["communities"],
        "largest_community": row["largest"],
        "median_size": row["median_size"],
        "singletons": row["singletons"],                      # vertices alone in their community
        "largest_share": row["largest"] / n_vertices if n_vertices else 0.0,
        "internal_connections": row["internal_connections"],
        "modularity": q,
    }
