"""
Influencer detection: who are the most important vertices?

Two scores, answering two different questions:

  degree centrality   "How many people point at you?"
                      in_degree / (n - 1): friends (undirected) or followers (directed).
                      Fast and simple, but every connection counts the same.

  PageRank            "How many IMPORTANT people point at you?"
                      A connection from an influential user is worth more than one from
                      an unknown user. Imagine a random surfer who follows edges and,
                      with probability reset_probability, jumps to a random vertex.
                      PageRank is the share of time the surfer spends at each vertex.
                      GraphFrames scales scores so they average about 1.0:
                      a score of 10 means "10x as important as the average vertex".

Comparing the two rankings shows whether popular vertices are also the influential ones.
"""
from typing import Dict, Optional

from graphframes import GraphFrame
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, StructField, StructType

from sna.features.stats import vertex_degrees


def degree_centrality(graph: GraphFrame, directed: bool) -> DataFrame:
    """id, in_degree, degree_centrality (0..1: share of all other vertices pointing at id).

    in_degree works for both kinds of data: undirected friendships are stored in
    both directions, so in_degree = number of friends.
    """
    n = graph.vertices.count()
    return vertex_degrees(graph, directed).select(
        "id",
        "in_degree",
        (F.col("in_degree") / (n - 1) if n > 1 else F.lit(0.0)).alias("degree_centrality"),
    )


def pagerank(graph: GraphFrame, reset_probability: float = 0.15,
             tol: float = 1e-4, max_iter: Optional[int] = None) -> DataFrame:
    """id, pagerank.

    By default we iterate until no score changes by more than `tol` (converged).
    Pass max_iter for a fixed number of rounds instead: faster on huge graphs,
    but scores may not have settled (see the Alice/Bob case in jobs/00_smoke_test.py).
    """
    if max_iter is not None:
        result = graph.pageRank(resetProbability=reset_probability, maxIter=max_iter)
    else:
        result = graph.pageRank(resetProbability=reset_probability, tol=tol)
    return result.vertices.select("id", "pagerank")


def influence_scores(graph: GraphFrame, directed: bool, **pagerank_args) -> DataFrame:
    """id, in_degree, degree_centrality, pagerank: one row per vertex."""
    return degree_centrality(graph, directed).join(pagerank(graph, **pagerank_args), "id")


def top_k(scores: DataFrame, by: str, k: int) -> DataFrame:
    """The k highest-scoring vertices with a rank column (1 = best). Ties: smaller id first.

    We sort, keep k rows, and number them on the driver. k is small, so this is cheap,
    and it avoids a global window function, which would pull ALL vertices into one task.
    """
    rows = scores.orderBy(F.desc(by), F.asc("id")).limit(k).collect()
    schema = StructType([StructField("rank", IntegerType(), False)] + scores.schema.fields)
    return scores.sparkSession.createDataFrame(
        [(rank, *row) for rank, row in enumerate(rows, start=1)], schema
    )


def compare_rankings(scores: DataFrame, top_by_degree: DataFrame,
                     top_by_pagerank: DataFrame) -> Dict[str, object]:
    """How similar are the two rankings?

    overlap        vertices in both top-k lists
    only_degree    popular but less influential (many friends, less important ones)
    only_pagerank  influential beyond their friend count (few, but important, friends)
    correlation    Pearson correlation of in_degree and pagerank over ALL vertices
                   (1.0 = the two scores move together perfectly)
    """
    degree_ids = {r["id"] for r in top_by_degree.select("id").collect()}
    pagerank_ids = {r["id"] for r in top_by_pagerank.select("id").collect()}
    return {
        "overlap": len(degree_ids & pagerank_ids),
        "only_degree": sorted(degree_ids - pagerank_ids),
        "only_pagerank": sorted(pagerank_ids - degree_ids),
        "correlation": scores.stat.corr("in_degree", "pagerank"),
    }
