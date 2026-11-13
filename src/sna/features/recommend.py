"""
Friend recommendation: "people you may know".

Idea (triadic closure): if you and C have many friends in common, you probably
know C or would like to. So for a user U:

    U ──► friend B ──► candidate C        C is a friend of a friend
                                          skip C if C == U or C is already U's friend

    mutual_friends(U, C) = number of different B's on such paths   <- main score
    adamic_adar(U, C)    = sum over those B of 1 / ln(neighbors(B)) <- tie-breaker
        A mutual friend with 5 friends says more than one with 1,000
        (a mega-hub knows everyone, so sharing them means little).
        B always has >= 2 neighbors (U and C), so ln(...) >= ln(2) > 0.

On directed data the same code means "who to follow": people followed by
people you follow, whom you don't follow yet.

We start from the chosen users only, so the work grows with their
friends-of-friends, not with the whole graph.
"""
from typing import List, Optional

from graphframes import GraphFrame
from pyspark.sql import DataFrame, Window
from pyspark.sql import functions as F

from sna.features.stats import neighbor_counts

# How many mutual friends to list as the "because you both know ..." explanation.
EXPLAIN_MUTUALS = 5
# Adamic-Adar is rounded to this many decimals so equal scores really tie (see recommend()).
AA_DECIMALS = 9


def friends_of_friends(graph: GraphFrame, users: List[int]) -> DataFrame:
    """user, friend, candidate: every path user -> friend -> candidate that
    leads to someone the user is not connected to yet."""
    e = graph.edges.select("src", "dst")

    # 1. The chosen users' friends.
    friends = e.where(F.col("src").isin(users)).select(
        F.col("src").alias("user"), F.col("dst").alias("friend"))

    # 2. Their friends' friends.
    paths = friends.join(
        e.select(F.col("src").alias("friend"), F.col("dst").alias("candidate")), "friend")

    # 3. Not the user themself, and not someone they already know.
    #    left_anti join = keep rows that have NO match in the other table.
    already = friends.select("user", F.col("friend").alias("candidate"))
    return (
        paths.where(F.col("user") != F.col("candidate"))
        .join(already, ["user", "candidate"], "left_anti")
    )


def recommend(graph: GraphFrame, users: List[int], k: int = 10) -> DataFrame:
    """Top-k suggestions per user:
    user, rank, candidate, mutual_friends, adamic_adar, mutual_sample."""
    neighbors = neighbor_counts(graph).select(F.col("id").alias("friend"), "neighbors")

    scored = (
        friends_of_friends(graph, users)
        .join(neighbors, "friend")
        .groupBy("user", "candidate")
        .agg(
            F.count("*").alias("mutual_friends"),
            # F.log = natural log. Rounded because floating-point sums depend on the ORDER
            # of the additions, which depends on how data is split over machines. Without
            # rounding, two equal scores could differ in the 16th decimal and their order
            # would change between runs/clusters. Rounded, equal scores tie and the id decides.
            F.round(F.sum(1.0 / F.log("neighbors")), AA_DECIMALS).alias("adamic_adar"),
            F.slice(F.sort_array(F.collect_list("friend")), 1, EXPLAIN_MUTUALS).alias("mutual_sample"),
        )
    )

    # Rank inside each user's own candidates (partitionBy user: one small group per
    # user, not one global sort). Ties: Adamic-Adar, then smaller id, so results repeat.
    by_score = Window.partitionBy("user").orderBy(
        F.desc("mutual_friends"), F.desc("adamic_adar"), F.asc("candidate"))
    return (
        scored.withColumn("rank", F.row_number().over(by_score))
        .where(F.col("rank") <= k)
        .select("user", "rank", "candidate", "mutual_friends", "adamic_adar", "mutual_sample")
    )


def add_same_community(recs: DataFrame, assignments: Optional[DataFrame]) -> DataFrame:
    """Add same_community (true/false) using step 1.7's id -> community table.
    Returns recs unchanged if no assignments are given."""
    if assignments is None:
        return recs
    user_c = assignments.select(F.col("id").alias("user"), F.col("community").alias("user_c"))
    cand_c = assignments.select(F.col("id").alias("candidate"), F.col("community").alias("cand_c"))
    return (
        recs.join(user_c, "user", "left").join(cand_c, "candidate", "left")
        .withColumn("same_community", F.col("user_c") == F.col("cand_c"))
        .drop("user_c", "cand_c")
        .select(*recs.columns, "same_community")
    )
