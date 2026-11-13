"""Shared test helpers: the Spark session and a tiny-graph builder."""
import unittest

from graphframes import GraphFrame
from pyspark.sql import SparkSession

from sna.loaders import clean_edges, vertices_from_edges


def make_graph(spark, pairs, directed=False):
    """GraphFrame from [(src, dst), ...], cleaned exactly like a real dataset
    (self-loops and duplicates removed, undirected pairs stored both ways)."""
    raw = spark.createDataFrame(pairs, "src long, dst long")
    edges = clean_edges(raw, directed)
    return GraphFrame(vertices_from_edges(edges), edges)


def to_dict(df, key, value):
    """{key: value} from two columns of a (small) DataFrame."""
    return {r[key]: r[value] for r in df.collect()}


class SparkTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # run_tests.py already started Spark; getOrCreate() returns that same session.
        cls.spark = SparkSession.builder.getOrCreate()

    @classmethod
    def graph(cls, pairs, directed=False):
        return make_graph(cls.spark, pairs, directed)
