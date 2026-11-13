"""config: paths come from the .ini file, never from code."""
import os
import tempfile
import unittest
from unittest import mock

from sna.config import load_config

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INI = """
[paths]
root        = /test
raw         = ${root}/raw
processed   = ${root}/processed
output      = ${root}/output
checkpoints = ${root}/checkpoints

[dataset.tiny]
file     = tiny.txt
directed = true
"""


class ConfigTest(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".ini")
        with os.fdopen(fd, "w") as f:
            f.write(INI)

    def tearDown(self):
        os.remove(self.path)

    def test_paths_are_built_from_root(self):
        cfg = load_config(self.path)
        self.assertEqual(cfg.raw, "/test/raw")
        self.assertEqual(cfg.raw_path("tiny"), "/test/raw/tiny/tiny.txt")
        self.assertEqual(cfg.processed_path("tiny", "edges"), "/test/processed/tiny/edges")
        self.assertEqual(cfg.output_path("tiny", "stats/summary"), "/test/output/tiny/stats/summary")

    def test_dataset_defaults(self):
        ds = load_config(self.path).dataset("tiny")
        self.assertTrue(ds.directed)
        self.assertEqual(ds.comment_prefix, "#")
        self.assertEqual(ds.separator, r"\s+")

    def test_unknown_dataset_lists_known_ones(self):
        with self.assertRaisesRegex(ValueError, "Known datasets: tiny"):
            load_config(self.path).dataset("nope")

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            load_config("/does/not/exist.ini")

    def test_env_var_selects_config(self):
        with mock.patch.dict(os.environ, {"SNA_CONFIG": self.path}):
            self.assertIn("tiny", load_config().datasets)

    def test_project_config_is_valid(self):
        """The real config/sna.ini loads, has the MVP dataset, and its paths have no host
        (so the same file works on any cluster: see docs/PLAN.md)."""
        cfg = load_config(os.path.join(REPO_DIR, "config", "sna.ini"))
        self.assertFalse(cfg.dataset("facebook").directed)
        for path in (cfg.raw, cfg.processed, cfg.output, cfg.checkpoints):
            self.assertTrue(path.startswith("/"), path)
            self.assertNotIn("://", path)


if __name__ == "__main__":
    unittest.main()
