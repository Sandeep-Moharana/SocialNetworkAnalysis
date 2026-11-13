"""
Load the application settings from config/sna.ini.

Our code never contains HDFS paths or dataset details: it asks the Config object.
To add a dataset, add a [dataset.<name>] section to the .ini file; no code changes.
"""
import configparser
import os
from dataclasses import dataclass
from typing import Dict, Optional

# Relative to the repo root, which is the working directory (/app) inside spark-client.
DEFAULT_CONFIG_PATH = "config/sna.ini"
# Set this environment variable to use another config file (e.g. a cluster-specific one).
CONFIG_ENV_VAR = "SNA_CONFIG"


@dataclass(frozen=True)
class DatasetConfig:
    name: str
    file: str             # file name inside <raw>/<name>/
    directed: bool        # False: each line is a two-way friendship
    comment_prefix: str   # skip lines starting with this
    separator: str        # regex between src and dst on a line


@dataclass(frozen=True)
class Config:
    # HDFS folders (no host part: resolved against fs.defaultFS from spark-defaults.conf)
    raw: str
    processed: str
    output: str
    checkpoints: str
    datasets: Dict[str, DatasetConfig]

    def dataset(self, name: str) -> DatasetConfig:
        if name not in self.datasets:
            known = ", ".join(sorted(self.datasets)) or "none"
            raise ValueError(f"Unknown dataset '{name}'. Known datasets: {known}")
        return self.datasets[name]

    # The three path helpers below define the HDFS layout described in docs/PLAN.md.
    def raw_path(self, dataset: str) -> str:
        return f"{self.raw}/{dataset}/{self.dataset(dataset).file}"

    def processed_path(self, dataset: str, table: str) -> str:
        return f"{self.processed}/{dataset}/{table}"

    def output_path(self, dataset: str, result: str) -> str:
        return f"{self.output}/{dataset}/{result}"


def load_config(path: Optional[str] = None) -> Config:
    """Read the .ini file. Priority: `path` argument > $SNA_CONFIG > config/sna.ini."""
    path = path or os.environ.get(CONFIG_ENV_VAR) or DEFAULT_CONFIG_PATH
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Config file not found: {path} (working dir: {os.getcwd()})")

    # ExtendedInterpolation lets the file say  raw = ${root}/raw
    parser = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
    parser.read(path)

    datasets = {}
    for section in parser.sections():
        if not section.startswith("dataset."):
            continue
        name = section[len("dataset."):]
        s = parser[section]
        datasets[name] = DatasetConfig(
            name=name,
            file=s["file"],
            directed=s.getboolean("directed"),
            comment_prefix=s.get("comment_prefix", "#"),
            separator=s.get("separator", r"\s+"),
        )

    paths = parser["paths"]
    return Config(
        raw=paths["raw"],
        processed=paths["processed"],
        output=paths["output"],
        checkpoints=paths["checkpoints"],
        datasets=datasets,
    )
