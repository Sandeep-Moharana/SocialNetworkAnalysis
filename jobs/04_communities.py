"""
Step 1.7: community detection with Label Propagation, scored with modularity.

    .\\scripts\\submit.ps1 jobs\\04_communities.py                  # facebook, 10 LPA rounds
    .\\scripts\\submit.ps1 jobs\\04_communities.py --max-iter 20    # labels settle more

Writes to /sna/output/<dataset>/communities/:
    assignments/   id -> community
    profiles/      one row per community: size, internal connections, density, leader
    summary/       one row: number of communities, sizes, modularity
"""
from pyspark.sql import Row

from sna.cli import base_parser
from sna.config import load_config
from sna.features import communities
from sna.loaders import load_graph
from sna.session import get_spark
from sna.storage import write_result


def parse_args():
    parser = base_parser(description="Detect communities with Label Propagation.")
    parser.add_argument("--max-iter", type=int, default=10,
                        help="LPA rounds (default: 10). More rounds = labels settle more, but cost more")
    parser.add_argument("--show", type=int, default=10, help="how many communities to print (default: 10)")
    return parser.parse_args()


def print_summary(dataset: str, max_iter: int, connections: int, s: dict) -> None:
    inside = 100 * s["internal_connections"] / connections if connections else 0.0
    print(f"\n=== Communities: {dataset}  (Label Propagation, {max_iter} rounds) ===")
    print(f"Communities            {s['communities']:>10,}")
    print(f"Largest community      {s['largest_community']:>10,}   ({100 * s['largest_share']:.1f}% of vertices)")
    print(f"Median size            {s['median_size']:>10,}")
    print(f"Singletons             {s['singletons']:>10,}   (vertices alone in their community)")
    print(f"Connections inside     {inside:>9.1f}%   (both ends in the same community)")
    print(f"Modularity Q           {s['modularity']:>10.4f}   (> 0.3 = clear community structure)")


def print_histogram(rows) -> None:
    print("\nCommunity sizes:")
    for r in rows:
        low = 10 ** r["bucket"]
        label = f"{low}-{10 * low - 1}"
        print(f"  {label:>11} members: {r['communities']:>6,} communities, {r['vertices']:>9,} vertices")
    print()


def main():
    args = parse_args()

    # load -> build graph
    cfg = load_config(args.config)
    ds = cfg.dataset(args.dataset)
    spark = get_spark(f"sna-04-communities-{args.dataset}", cfg)
    graph = load_graph(spark, cfg, args.dataset)

    # analyze
    # cache(): LPA is the expensive part. Its result feeds the profiles, the
    # modularity and a write, so we compute it once.
    assignments = communities.label_propagation(graph, args.max_iter).cache()
    table = communities.community_table(graph, assignments, ds.directed).cache()

    edge_rows = graph.edges.count()
    connections = edge_rows if ds.directed else edge_rows // 2
    q = communities.modularity(table, edge_rows)
    summary = communities.summarize(table, q, graph.vertices.count())

    print_summary(args.dataset, args.max_iter, connections, summary)
    print_histogram(communities.size_histogram(table).collect())
    print(f"Largest {args.show} communities:")
    table.select("community", "size", "internal_connections", "density", "leader", "leader_degree") \
         .show(args.show, truncate=False)

    # write
    out = "communities"
    write_result(assignments, cfg, args.dataset, f"{out}/assignments")
    write_result(table, cfg, args.dataset, f"{out}/profiles")
    write_result(spark.createDataFrame([Row(dataset=args.dataset, max_iter=args.max_iter, **summary)]),
                 cfg, args.dataset, f"{out}/summary")

    table.unpersist()
    assignments.unpersist()
    spark.stop()


if __name__ == "__main__":
    main()
