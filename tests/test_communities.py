r"""communities: community profiles, modularity, Label Propagation.

Test graph: two triangles joined by one edge (undirected, 7 friendships, 14 edge rows)

    1           5
    | \       / |
    |  3 --- 4  |       triangles {1, 2, 3} and {4, 5, 6}, bridge 3-4
    | /       \ |
    2           6

Modularity of the partition {1,2,3} / {4,5,6}, worked out by hand:
    each community: 6 inner edge rows, degree sum 2+2+3 = 7
    Q = 2 * (6/14 - (7/14)^2) = 2 * (3/7 - 1/4) = 5/14 ~ 0.3571
"""
from spark_case import SparkTestCase

from sna.features import communities

TWO_TRIANGLES = [(1, 2), (2, 3), (1, 3), (4, 5), (5, 6), (4, 6), (3, 4)]
EDGE_ROWS = 14


class CommunityTableTest(SparkTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.g = cls.graph(TWO_TRIANGLES)

    def partition(self, mapping):
        """DataFrame id -> community from a {id: community} dict."""
        return self.spark.createDataFrame(list(mapping.items()), "id long, community long")

    def test_hand_partition(self):
        table = communities.community_table(
            self.g, self.partition({1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 2}), directed=False)
        rows = {r["community"]: r for r in table.collect()}
        for c, leader in ((1, 3), (2, 4)):                 # 3 and 4 have the most friends
            self.assertEqual(rows[c]["size"], 3)
            self.assertEqual(rows[c]["internal_connections"], 3)
            self.assertEqual(rows[c]["density"], 1.0)      # everyone knows everyone inside
            self.assertEqual(rows[c]["leader"], leader)
        self.assertAlmostEqual(communities.modularity(table, EDGE_ROWS), 5 / 14)

        s = communities.summarize(table, 5 / 14, n_vertices=6)
        self.assertEqual((s["communities"], s["largest_community"], s["singletons"]), (2, 3, 0))
        self.assertEqual(s["internal_connections"], 6)     # all but the bridge
        self.assertEqual(s["largest_share"], 0.5)

    def test_everyone_in_one_community_has_zero_modularity(self):
        table = communities.community_table(self.g, self.partition({i: 1 for i in range(1, 7)}), False)
        self.assertAlmostEqual(communities.modularity(table, EDGE_ROWS), 0.0)

    def test_everyone_alone_is_worse_than_random(self):
        table = communities.community_table(self.g, self.partition({i: i for i in range(1, 7)}), False)
        self.assertLess(communities.modularity(table, EDGE_ROWS), 0.0)

    def test_size_histogram(self):
        table = communities.community_table(
            self.g, self.partition({1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 2}), False)
        row = communities.size_histogram(table).first()
        self.assertEqual((row["bucket"], row["communities"], row["vertices"]), (0, 2, 6))   # 1-9 members


class LabelPropagationTest(SparkTestCase):
    def test_labels_never_cross_disconnected_groups(self):
        """LPA only passes labels along edges, so two separate triangles can never share one.
        (We don't assert the exact labels: LPA may break ties differently, see communities.py.)"""
        g = self.graph([(1, 2), (2, 3), (1, 3), (4, 5), (5, 6), (4, 6)])
        labels = {r["id"]: r["community"] for r in communities.label_propagation(g, 5).collect()}
        self.assertEqual(sorted(labels), [1, 2, 3, 4, 5, 6])          # every vertex labeled
        self.assertTrue({labels[1], labels[2], labels[3]}.isdisjoint({labels[4], labels[5], labels[6]}))
