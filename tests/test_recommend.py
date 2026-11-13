"""recommend: friends-of-friends ranked by mutual friends.

Small graph (undirected):

    1 --- 2 --- 4
    |           |
    3 ----------+
    |
    5

  User 1's friends: 2, 3.   Not yet friends: 4 (via 2 and 3), 5 (via 3).
    4: mutual 2 = [2, 3]   adamic-adar = 1/ln(deg 2) + 1/ln(deg 3) = 1/ln2 + 1/ln3
    5: mutual 1 = [3]      adamic-adar = 1/ln3
"""
import math
import random
from collections import defaultdict

from spark_case import SparkTestCase

from sna.features import recommend
from sna.features.recommend import AA_DECIMALS

SMALL = [(1, 2), (1, 3), (2, 4), (3, 4), (3, 5)]


def brute_force(pairs, user, k):
    """The same scoring in plain Python, as an independent check."""
    adj = defaultdict(set)
    for a, b in pairs:
        if a != b:
            adj[a].add(b)
            adj[b].add(a)
    score = defaultdict(lambda: [0, 0.0])
    for friend in adj[user]:
        for c in adj[friend]:
            if c != user and c not in adj[user]:
                score[c][0] += 1
                score[c][1] += 1 / math.log(len(adj[friend]))
    # Same rule as recommend(): Adamic-Adar rounded, so equal scores tie and the id decides.
    best = sorted(score.items(), key=lambda kv: (-kv[1][0], -round(kv[1][1], AA_DECIMALS), kv[0]))[:k]
    return [(c, m, round(aa, AA_DECIMALS)) for c, (m, aa) in best]


class RecommendTest(SparkTestCase):
    def recs(self, pairs, users, k=10, directed=False):
        rows = recommend.recommend(self.graph(pairs, directed), users, k).collect()
        return sorted(rows, key=lambda r: (r["user"], r["rank"]))

    def test_hand_example(self):
        rows = self.recs(SMALL, [1])
        self.assertEqual([(r["rank"], r["candidate"], r["mutual_friends"], r["mutual_sample"]) for r in rows],
                         [(1, 4, 2, [2, 3]), (2, 5, 1, [3])])
        self.assertAlmostEqual(rows[0]["adamic_adar"], 1 / math.log(2) + 1 / math.log(3))
        self.assertAlmostEqual(rows[1]["adamic_adar"], 1 / math.log(3))

    def test_top_k_limit(self):
        self.assertEqual([r["candidate"] for r in self.recs(SMALL, [1], k=1)], [4])

    def test_matches_brute_force_on_random_graph(self):
        rnd = random.Random(7)   # fixed seed: same "random" graph every run
        pairs = [(rnd.randrange(30), rnd.randrange(30)) for _ in range(90)]
        users = list(range(10))
        rows = self.recs(pairs, users, k=5)
        for u in users:
            spark_result = [(r["candidate"], r["mutual_friends"], r["adamic_adar"])
                            for r in rows if r["user"] == u]
            self.assertEqual(spark_result, brute_force(pairs, u, 5), msg=f"user {u}")

    def test_never_suggests_self_or_existing_friends(self):
        rnd = random.Random(3)
        pairs = [(rnd.randrange(20), rnd.randrange(20)) for _ in range(50)]
        friends = defaultdict(set)
        for a, b in pairs:
            friends[a].add(b)
            friends[b].add(a)
        for r in self.recs(pairs, list(range(20))):
            self.assertNotEqual(r["candidate"], r["user"])
            self.assertNotIn(r["candidate"], friends[r["user"]])

    def test_directed_means_who_to_follow(self):
        """1 follows 2, 2 follows 3 -> suggest 3 to 1. Nobody is suggested to 3 (follows no one)."""
        rows = self.recs([(1, 2), (2, 3)], [1, 3], directed=True)
        self.assertEqual([(r["user"], r["candidate"]) for r in rows], [(1, 3)])

    def test_same_community_flag(self):
        recs = recommend.recommend(self.graph(SMALL), [1], 10)
        assignments = self.spark.createDataFrame([(1, 10), (2, 10), (3, 10), (4, 10), (5, 20)],
                                                 "id long, community long")
        flags = {r["candidate"]: r["same_community"]
                 for r in recommend.add_same_community(recs, assignments).collect()}
        self.assertEqual(flags, {4: True, 5: False})
        # Without step 1.7's output, recommendations are returned unchanged.
        self.assertEqual(recommend.add_same_community(recs, None).columns, recs.columns)
