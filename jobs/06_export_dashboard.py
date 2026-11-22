"""
Export every result for the dashboard (ui/index.html).

    .\\scripts\\run_all.ps1                                   # first: jobs 01-05 (results in HDFS)
    .\\scripts\\submit.ps1 jobs\\06_export_dashboard.py       # then this
    start ui\\index.html                                      # open in a browser (works offline)

What it does:
  1. reads the results of jobs 02-04 from HDFS (stats, influencers, communities);
  2. computes friend recommendations for EVERY user (the same Spark code as job 05,
     which by default does one user), so the page can show any user;
  3. computes a 2-D layout of the graph (sna.layout, numpy on the driver);
  4. writes ONE file, ui/data/dashboard.js:   window.SNA_DATA = {...};
     A .js file, not .json, so the page also works when opened as a plain file
     (browsers block reading .json files from disk, but allow <script src>).

The page itself (ui/) never talks to Spark or HDFS: re-run this job after re-running
the analyses, and reload the page.
"""
import json
import os
from datetime import datetime, timezone

import numpy as np
from pyspark.errors import AnalysisException
from pyspark.sql import functions as F

from sna.cli import base_parser
from sna.config import load_config
from sna.features import recommend
from sna.layout import force_layout
from sna.loaders import load_graph
from sna.session import get_spark


def parse_args():
    parser = base_parser(description="Export all results to ui/data/dashboard.js for the dashboard.")
    parser.add_argument("--top-k", type=int, default=10, help="recommendations per user (default: 10)")
    parser.add_argument("--layout-rounds", type=int, default=120, help="layout rounds (default: 120)")
    parser.add_argument("--out", default="ui/data/dashboard.js", help="output file (default: ui/data/dashboard.js)")
    return parser.parse_args()


def read_result(spark, cfg, dataset, result):
    """A result table from HDFS, with a clear message if its job hasn't run yet."""
    path = cfg.output_path(dataset, result)
    try:
        return spark.read.parquet(path)
    except AnalysisException:
        raise SystemExit(f"Missing {path}. Run the analyses first: .\\scripts\\run_all.ps1")


def one_row(df) -> dict:
    """A one-row summary table as a plain dict (numbers rounded for the page)."""
    row = df.first().asDict()
    return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in row.items()}


def main():
    args = parse_args()
    cfg = load_config(args.config)
    spark = get_spark(f"sna-06-export-{args.dataset}", cfg)
    graph = load_graph(spark, cfg, args.dataset)
    r = lambda name: read_result(spark, cfg, args.dataset, name)

    # 1. One row per user: everything jobs 02-04 computed about them.
    users = (
        r("stats/vertex_stats").select("id", "degree", "triangles", "clustering")
        .join(r("influencers/scores").select("id", "pagerank"), "id")
        .join(r("communities/assignments"), "id")
        .orderBy("id")
        .collect()                                    # small: one row per user
    )
    ids = [u["id"] for u in users]
    index = {uid: i for i, uid in enumerate(ids)}     # user id -> position in the arrays
    print(f"[export] {len(ids):,} users")

    # Each friendship once (edges are stored in both directions), as array positions.
    pairs = graph.edges.where(F.col("src") < F.col("dst")).select("src", "dst").collect()
    edges = np.array([(index[p["src"]], index[p["dst"]]) for p in pairs], dtype=np.int64)
    print(f"[export] {len(edges):,} friendships")

    # 2. Recommendations for every user (Spark, distributed: the heavy part).
    recs = recommend.add_same_community(
        recommend.recommend(graph, ids, args.top_k), r("communities/assignments"))
    rec_lists = [[] for _ in ids]
    for row in recs.collect():                        # top_k rows per user
        rec_lists[index[row["user"]]].append(
            [row["rank"], row["candidate"], row["mutual_friends"], round(row["adamic_adar"], 3),
             1 if row["same_community"] else 0, row["mutual_sample"]])
    for lst in rec_lists:
        lst.sort()
    print(f"[export] recommendations for {sum(1 for l in rec_lists if l):,} users")

    # 3. Layout (driver, numpy).
    community = np.array([u["community"] for u in users])
    print(f"[export] computing the graph layout ({args.layout_rounds} rounds) ...")
    pos = force_layout(len(ids), edges, community, iterations=args.layout_rounds)

    # 4. One JS file. Columns as arrays ("column-wise"): much smaller than one object per user.
    data = {
        "dataset": args.dataset,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "stats": one_row(r("stats/summary")),
        "community_summary": one_row(r("communities/summary")),
        "communities": [row.asDict() for row in
                        r("communities/profiles")
                        .select("community", "size", "internal_connections", "density", "leader", "leader_degree")
                        .orderBy(F.desc("size"), "community").collect()],
        "users": {
            "id": ids,
            "x": [round(float(x), 2) for x in pos[:, 0]],
            "y": [round(float(y), 2) for y in pos[:, 1]],
            "degree": [u["degree"] for u in users],
            "triangles": [u["triangles"] for u in users],
            "clustering": [round(u["clustering"], 4) for u in users],
            "pagerank": [round(u["pagerank"], 4) for u in users],
            "community": [int(c) for c in community],
        },
        "edges": edges.flatten().tolist(),            # [a0, b0, a1, b1, ...] array positions
        # recs[i] = list of [rank, candidate id, mutual friends, adamic-adar, same community 0/1, sample]
        "recs": rec_lists,
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("// Generated by jobs/06_export_dashboard.py. Do not edit: re-run the job.\n")
        f.write("window.SNA_DATA = ")
        json.dump(data, f, separators=(",", ":"))
        f.write(";\n")
    print(f"[export] wrote {args.out} ({os.path.getsize(args.out) / 1e6:.1f} MB). Open ui/index.html")

    spark.stop()


if __name__ == "__main__":
    main()
