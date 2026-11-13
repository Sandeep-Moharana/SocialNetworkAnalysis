"""loaders: raw text -> clean edges -> vertices."""
import os
import tempfile

from spark_case import SparkTestCase

from sna.config import DatasetConfig
from sna.loaders import clean_edges, read_edge_list, vertices_from_edges


def pairs(df):
    return sorted((r["src"], r["dst"]) for r in df.collect())


class ReadEdgeListTest(SparkTestCase):
    def test_skips_comments_blank_and_bad_lines(self):
        content = (
            "# Directed graph\n"
            "# Nodes: 3 Edges: 3\n"
            "0 1\n"
            "\n"                    # blank line
            "1\t2\n"                # tab instead of space
            "   2    0   \n"        # extra spaces
            "not numbers\n"         # junk: dropped
        )
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "edges.txt")
            with open(path, "w") as f:
                f.write(content)
            ds = DatasetConfig(name="t", file="edges.txt", directed=True,
                               comment_prefix="#", separator=r"\s+")
            # file:// = local disk of the container (the tests don't use HDFS)
            result = pairs(read_edge_list(self.spark, "file://" + path, ds))
        self.assertEqual(result, [(0, 1), (1, 2), (2, 0)])


class CleanEdgesTest(SparkTestCase):
    def raw(self, p):
        return self.spark.createDataFrame(p, "src long, dst long")

    def test_undirected_stores_each_friendship_both_ways_once(self):
        # 1-2 is listed twice (once reversed); 3-3 is a self-loop.
        edges = clean_edges(self.raw([(1, 2), (2, 1), (2, 3), (3, 3)]), directed=False)
        self.assertEqual(pairs(edges), [(1, 2), (2, 1), (2, 3), (3, 2)])

    def test_directed_keeps_direction(self):
        edges = clean_edges(self.raw([(1, 2), (1, 2), (2, 3), (3, 3)]), directed=True)
        self.assertEqual(pairs(edges), [(1, 2), (2, 3)])

    def test_vertices_are_all_edge_ends(self):
        edges = clean_edges(self.raw([(1, 2), (2, 3)]), directed=True)
        self.assertEqual(sorted(r["id"] for r in vertices_from_edges(edges).collect()), [1, 2, 3])
