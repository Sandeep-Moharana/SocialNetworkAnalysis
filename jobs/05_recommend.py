"""
Step 1.8: friend recommendation ("people you may know") by mutual friends.

    .\\scripts\\submit.ps1 jobs\\05_recommend.py                       # user 0, top 10
    .\\scripts\\submit.ps1 jobs\\05_recommend.py --users 107 3980 --top-k 5

If step 1.7 has been run (jobs\\04_communities.py), each suggestion also shows
whether it comes from the user's own community: a quick sanity check.

Writes to /sna/output/<dataset>/recommendations/top_k/  (replaced on every run)
"""
from pyspark.errors import AnalysisException
from pyspark.sql import functions as F

from sna.cli import base_parser
from sna.config import load_config
from sna.features import recommend
from sna.loaders import load_graph
from sna.session import get_spark
from sna.storage import write_result


def parse_args():
    parser = base_parser(description="Recommend new friends by mutual friends.")
    parser.add_argument("--users", type=int, nargs="+", default=[0],
                        help="user id(s) to recommend for (default: 0)")
    parser.add_argument("--top-k", type=int, default=10, help="suggestions per user (default: 10)")
    return parser.parse_args()


def read_communities(spark, cfg, dataset):
    """Step 1.7's id -> community table, or None if that job hasn't been run."""
    path = cfg.output_path(dataset, "communities/assignments")
    try:
        return spark.read.parquet(path)
    except AnalysisException:
        print(f"[info] no communities at {path}: run jobs\\04_communities.py to enable the community check")
        return None


def print_user(user, friend_count, rows) -> None:
    print(f"\n--- User {user} ({friend_count:,} friends) ---")
    if not rows:
        print("  no suggestions (no friends-of-friends who aren't already friends)")
        return
    has_c = "same_community" in rows[0]
    print(f"  {'rank':>4}  {'suggest':>7}  {'mutual':>6}  {'adamic-adar':>11}  "
          f"{'same comm.' if has_c else '':<10}  because you both know")
    for r in rows:
        comm = ("yes" if r["same_community"] else "no") if has_c else ""
        sample = ", ".join(str(m) for m in r["mutual_sample"])
        more = ", ..." if r["mutual_friends"] > len(r["mutual_sample"]) else ""
        print(f"  {r['rank']:>4}  {r['candidate']:>7}  {r['mutual_friends']:>6}  "
              f"{r['adamic_adar']:>11.3f}  {comm:<10}  {sample}{more}")


def main():
    args = parse_args()

    # load -> build graph
    cfg = load_config(args.config)
    spark = get_spark(f"sna-05-recommend-{args.dataset}", cfg)
    graph = load_graph(spark, cfg, args.dataset)

    # Check the requested users exist, and count their friends for the printout.
    friend_counts = {
        r["src"]: r["count"]
        for r in graph.edges.where(F.col("src").isin(args.users)).groupBy("src").count().collect()
    }
    missing = [u for u in args.users if u not in friend_counts]
    if missing:
        print(f"[warn] not in the graph (or no connections): {missing}")
    users = [u for u in args.users if u in friend_counts]
    if not users:
        spark.stop()
        raise SystemExit("No valid users given.")

    # analyze
    recs = recommend.recommend(graph, users, args.top_k)
    recs = recommend.add_same_community(recs, read_communities(spark, cfg, args.dataset))
    recs = recs.orderBy("user", "rank").cache()   # printed AND written: compute once

    rows = recs.collect()   # small: top_k rows per user
    print(f"\n=== Friend recommendations: {args.dataset} (top {args.top_k}, ranked by mutual friends) ===")
    for u in users:
        print_user(u, friend_counts[u], [r.asDict() for r in rows if r["user"] == u])

    if rows and "same_community" in rows[0]:
        same = sum(1 for r in rows if r["same_community"])
        print(f"\n{same} of {len(rows)} suggestions ({100 * same / len(rows):.0f}%) are in the user's own community.")
    print()

    # write
    write_result(recs, cfg, args.dataset, "recommendations/top_k")
    recs.unpersist()
    spark.stop()


if __name__ == "__main__":
    main()
