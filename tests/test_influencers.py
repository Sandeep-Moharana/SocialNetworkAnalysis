"""influencers: degree centrality, PageRank, top-k.

The smoke-test graph (directed, "follower -> followed"):
    Bob, Carol, Dave -> Alice;   Alice -> Bob;   Carol -> Bob
    ids: Alice=1, Bob=2, Carol=3, Dave=4

Converged PageRank worked out by hand (reset 0.15, GraphFrames scale = sum N):
    Carol = Dave = 0.15        (nobody follows them)
    Alice = 0.15 + 0.85 * (Bob + Carol/2 + Dave)   ~ 1.8845
    Bob   = 0.15 + 0.85 * (Alice + Carol/2)        ~ 1.8154
"""
from spark_case import SparkTestCase, to_dict

from sna.features import influencers

FOLLOWS = [(2, 1), (3, 1), (4, 1), (1, 2), (3, 2)]


class InfluencersTest(SparkTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.g = cls.graph(FOLLOWS, directed=True)
        cls.scores = influencers.influence_scores(cls.g, directed=True).cache()

    def test_pagerank_matches_hand_calculation(self):
        pr = to_dict(self.scores, "id", "pagerank")
        self.assertAlmostEqual(pr[1], 1.8845, places=2)
        self.assertAlmostEqual(pr[2], 1.8154, places=2)
        self.assertAlmostEqual(pr[3], 0.15, places=3)
        self.assertAlmostEqual(pr[4], 0.15, places=3)
        self.assertAlmostEqual(sum(pr.values()), 4.0, places=3)   # scores average 1.0

    def test_fixed_iterations_option(self):
        pr = influencers.pagerank(self.g, max_iter=3)
        self.assertEqual(pr.count(), 4)

    def test_degree_centrality(self):
        dc = to_dict(self.scores, "id", "degree_centrality")
        self.assertEqual(dc, {1: 1.0, 2: 2 / 3, 3: 0.0, 4: 0.0})   # in_degree / (n - 1)

    def test_top_k_ranks_and_breaks_ties_by_id(self):
        top = influencers.top_k(self.scores, "degree_centrality", 4).collect()
        self.assertEqual([r["rank"] for r in top], [1, 2, 3, 4])
        self.assertEqual([r["id"] for r in top], [1, 2, 3, 4])      # 3 and 4 tie at 0: smaller id first
        self.assertEqual(len(influencers.top_k(self.scores, "pagerank", 2).collect()), 2)

    def test_compare_rankings(self):
        cmp = influencers.compare_rankings(
            self.scores,
            influencers.top_k(self.scores, "degree_centrality", 2),
            influencers.top_k(self.scores, "pagerank", 2),
        )
        self.assertEqual(cmp["overlap"], 2)                          # both lists are {Alice, Bob}
        self.assertEqual((cmp["only_degree"], cmp["only_pagerank"]), ([], []))

    def test_star_center_is_top_influencer(self):
        """Undirected star: 0 is friends with 1..4, nobody else is connected."""
        scores = influencers.influence_scores(self.graph([(0, i) for i in range(1, 5)]), directed=False)
        self.assertEqual(influencers.top_k(scores, "pagerank", 1).first()["id"], 0)
        self.assertEqual(to_dict(scores, "id", "degree_centrality")[0], 1.0)   # knows everyone
