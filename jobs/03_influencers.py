"""
Step 1.6: influencer detection with degree centrality and PageRank.

    .\\scripts\\submit.ps1 jobs\\03_influencers.py                    # facebook, top 10
    .\\scripts\\submit.ps1 jobs\\03_influencers.py --top-k 20
    .\\scripts\\submit.ps1 jobs\\03_influencers.py --max-iter 10      # fixed rounds (big graphs)

Writes to /sna/output/<dataset>/influencers/:
    scores/          every vertex: in_degree, degree_centrality, pagerank
    top_degree/      top-k by degree centrality, with rank
    top_pagerank/    top-k by PageRank, with rank
"""
from sna.cli import base_parser
from sna.config import load_config
from sna.features import influencers
from sna.loaders import load_graph
from sna.session import get_spark
from sna.storage import write_result


def parse_args():
    parser = base_parser(description="Find the most influential vertices of a dataset.")
    parser.add_argument("--top-k", type=int, default=10, help="how many influencers to list (default: 10)")
    parser.add_argument("--reset-prob", type=float, default=0.15,
                        help="PageRank: chance of jumping to a random vertex (default: 0.15)")
    parser.add_argument("--tol", type=float, default=1e-4,
                        help="PageRank: stop when no score changes by more than this (default: 1e-4)")
    parser.add_argument("--max-iter", type=int, default=None,
                        help="PageRank: run exactly this many rounds instead of using --tol")
    return parser.parse_args()


def main():
    args = parse_args()

    # load -> build graph
    cfg = load_config(args.config)
    ds = cfg.dataset(args.dataset)
    spark = get_spark(f"sna-03-influencers-{args.dataset}", cfg)
    graph = load_graph(spark, cfg, args.dataset)

    # analyze
    # cache(): scores feed two top-k lists, a correlation, and a write.
    # Without it Spark would run PageRank again for each of them.
    scores = influencers.influence_scores(
        graph, ds.directed,
        reset_probability=args.reset_prob, tol=args.tol, max_iter=args.max_iter,
    ).cache()
    top_degree = influencers.top_k(scores, "degree_centrality", args.top_k)
    top_pagerank = influencers.top_k(scores, "pagerank", args.top_k)
    cmp = influencers.compare_rankings(scores, top_degree, top_pagerank)

    mode = f"{args.max_iter} rounds" if args.max_iter else f"until converged (tol={args.tol})"
    print(f"\n=== Influencers: {args.dataset}  (PageRank: reset={args.reset_prob}, {mode}) ===")
    print(f"\nTop {args.top_k} by degree centrality (most connections):")
    top_degree.show(truncate=False)
    print(f"Top {args.top_k} by PageRank (connected to important vertices):")
    top_pagerank.show(truncate=False)

    print(f"In both lists      : {cmp['overlap']} of {args.top_k}")
    print(f"Only by degree     : {cmp['only_degree'] or '-'}")
    print(f"Only by PageRank   : {cmp['only_pagerank'] or '-'}")
    print(f"Correlation (all vertices, in_degree vs pagerank): {cmp['correlation']:.3f}\n")

    # write
    out = "influencers"
    write_result(scores, cfg, args.dataset, f"{out}/scores")
    write_result(top_degree, cfg, args.dataset, f"{out}/top_degree")
    write_result(top_pagerank, cfg, args.dataset, f"{out}/top_pagerank")

    scores.unpersist()
    spark.stop()


if __name__ == "__main__":
    main()
