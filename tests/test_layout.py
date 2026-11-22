"""Graph layout for the dashboard (sna.layout): plain numpy, no Spark needed."""
import unittest

import numpy as np

from sna.layout import force_layout


class ForceLayoutTest(unittest.TestCase):
    # Two triangles joined by one bridge:   0-1-2 triangle, 3-4-5 triangle, bridge 2-3
    EDGES = np.array([(0, 1), (1, 2), (0, 2), (3, 4), (4, 5), (3, 5), (2, 3)])
    GROUPS = np.array([0, 0, 0, 1, 1, 1])

    def setUp(self):
        self.pos = force_layout(6, self.EDGES, self.GROUPS, iterations=80)

    def test_shape_and_finite(self):
        self.assertEqual(self.pos.shape, (6, 2))
        self.assertTrue(np.isfinite(self.pos).all())

    def test_friends_are_closer_than_strangers(self):
        d = lambda a, b: np.linalg.norm(self.pos[a] - self.pos[b])
        inside = np.mean([d(0, 1), d(1, 2), d(0, 2), d(3, 4), d(4, 5), d(3, 5)])
        across = np.mean([d(0, 4), d(0, 5), d(1, 4), d(1, 5)])   # not connected, other triangle
        self.assertLess(inside, across)

    def test_same_picture_every_run(self):
        again = force_layout(6, self.EDGES, self.GROUPS, iterations=80)
        np.testing.assert_allclose(self.pos, again)

    def test_no_vertices_points(self):
        self.assertEqual(force_layout(0, np.zeros((0, 2), dtype=int)).shape, (0, 2))


if __name__ == "__main__":
    unittest.main()
