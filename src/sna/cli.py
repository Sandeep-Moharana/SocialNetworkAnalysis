"""Command-line arguments that every job shares, so all jobs are used the same way."""
import argparse


def base_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--dataset", default="facebook",
        help="dataset name, as in a [dataset.<name>] section of config/sna.ini (default: facebook)",
    )
    parser.add_argument(
        "--config", default=None,
        help="path to the .ini config (default: $SNA_CONFIG or config/sna.ini)",
    )
    return parser
