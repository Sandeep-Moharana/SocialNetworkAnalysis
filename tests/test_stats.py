r"""stats: degrees, triangles, clustering, components, summary.

Test graph (undirected, 6 vertices, 5 friendships):

    1 --- 2          5 --- 6
     \   /
      \ /
       3 --- 4

  degree      1:2  2:2  3:3  4:1  5:1  6:1
  triangles   1, 2, 3 are in one triangle; 4, 5, 6 in none
  clustering  1: 1/1   2: 1/1   3: 1 closed pair of 3 = 1/3   4, 5, 6: 0 (fewer than 2 friends)
  components  {1, 2, 3, 4} and {5, 6}
"""
from spark_case import SparkTestCase, to_dict

from sna.features import stats

PAW_AND_PAIR = [(1, 2), (2, 3), (1, 3), (3, 4), (5, 6)]


class UndirectedStatsTest(SparkTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        vstats = stats.vertex_stats(cls.graph(PAW_AND_PAIR), directed=False).cache()
        cls.vstats_df = vstats
        cls.v = {r["id"]: r for r in vstats.collect()}
        cls.summary = stats.summarize(vstats, stats.component_sizes(vstats), directed=False)

    def test_degree(self):
        self.assertEqual({i: r["degree"] for i, r in self.v.items()}, {1: 2, 2: 2, 3: 3, 4: 1, 5: 1, 6: 1})

    def test_triangles(self):
        self.assertEqual({i: r["triangles"] for i, r in self.v.items()}, {1: 1, 2: 1, 3: 1, 4: 0, 5: 0, 6: 0})

    def test_clustering(self):
        expected = {1: 1.0, 2: 1.0, 3: 1 / 3, 4: 0.0, 5: 0.0, 6: 0.0}
        for i, value in expected.items():
            self.assertAlmostEqual(self.v[i]["clustering"], value, places=6, msg=f"vertex {i}")

    def test_components(self):
        c = {i: r["component"] for i, r in self.v.items()}
        self.assertEqual(len({c[1], c[2], c[3], c[4]}), 1)   # one group
        self.assertEqual(c[5], c[6])
        self.assertNotEqual(c[1], c[5])                       # two different groups

    def test_summary(self):
        s = self.summary
        self.assertEqual(s["vertices"], 6)
        self.assertEqual(s["connections"], 5)
        self.assertAlmostEqual(s["density"], 10 / 30)          # 10 edge rows / (6 * 5) ordered pairs
        self.assertEqual((s["min_degree"], s["max_degree"]), (1, 3))
        self.assertEqual(s["components"], 2)
        self.assertEqual(s["largest_component"], 4)
        self.assertEqual(s["triangles"], 1)
        self.assertAlmostEqual(s["avg_clustering"], (1 + 1 + 1 / 3) / 6)
        self.assertAlmostEqual(s["transitivity"], 3 / 5)       # 3 triangle corners / 5 friend pairs

    def test_degree_distribution_and_histogram(self):
        self.assertEqual(to_dict(stats.degree_distribution(self.vstats_df), "degree", "vertices"),
                         {1: 3, 2: 2, 3: 1})
        # buckets: 0 = degree 1, 1 = degrees 2-3
        self.assertEqual(to_dict(stats.degree_histogram(self.vstats_df), "bucket", "vertices"), {0: 3, 1: 3})


class DirectedStatsTest(SparkTestCase):
    """1 -> 2, 1 -> 3, 2 -> 3: degree = in + out."""

    def test_directed_degrees(self):
        d = {r["id"]: r for r in stats.vertex_degrees(self.graph([(1, 2), (1, 3), (2, 3)], directed=True),
                                                       directed=True).collect()}
        self.assertEqual({i: r["in_degree"] for i, r in d.items()}, {1: 0, 2: 1, 3: 2})
        self.assertEqual({i: r["out_degree"] for i, r in d.items()}, {1: 2, 2: 1, 3: 0})
        self.assertEqual({i: r["degree"] for i, r in d.items()}, {1: 2, 2: 2, 3: 2})

    def test_mutual_follow_is_one_neighbor(self):
        g = self.graph([(1, 2), (2, 1), (2, 3)], directed=True)
        self.assertEqual(to_dict(stats.neighbor_counts(g), "id", "neighbors"), {1: 1, 2: 2, 3: 1})
