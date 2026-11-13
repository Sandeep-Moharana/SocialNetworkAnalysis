"""
Step 1.5: network statistics for a dataset.

    .\\scripts\\submit.ps1 jobs\\02_network_stats.py                  # facebook
    .\\scripts\\submit.ps1 jobs\\02_network_stats.py --dataset <name>

Writes to /sna/output/<dataset>/stats/:
    summary/               one row: sizes, density, degrees, components, triangles, clustering
    vertex_stats/          one row per vertex: degree, triangles, clustering, component
    degree_distribution/   degree -> number of vertices
    component_sizes/       component -> size
"""
from pyspark.sql import Row

from sna.cli import base_parser
from sna.config import load_config
from sna.features import stats
from sna.loaders import load_graph
from sna.session import get_spark
from sna.storage import write_result


def print_summary(dataset: str, directed: bool, s: dict) -> None:
    pct = 100 * s["largest_component"] / s["vertices"]
    print(f"\n=== Network statistics: {dataset} ({'directed' if directed else 'undirected'}) ===")
    print(f"Vertices               {s['vertices']:>12,}")
    print(f"Connections            {s['connections']:>12,}")
    print(f"Density                {s['density']:>12.6f}")
    print(f"Degree min / median    {s['min_degree']:>5,} / {s['median_degree']:,}")
    print(f"Degree avg / max       {s['avg_degree']:>8.2f} / {s['max_degree']:,}")
    print(f"Connected components   {s['components']:>12,}   (largest: {s['largest_component']:,} vertices, {pct:.1f}%)")
    print(f"Triangles              {s['triangles']:>12,}")
    print(f"Avg clustering coeff   {s['avg_clustering']:>12.4f}")
    print(f"Transitivity           {s['transitivity']:>12.4f}")


def print_histogram(rows) -> None:
    """Text bar chart of the power-of-two degree buckets."""
    print("\nDegree histogram (vertices per degree range):")
    biggest = max(r["vertices"] for r in rows)
    for r in rows:
        b = r["bucket"]
        label = "0" if b < 0 else f"{2 ** b}-{2 ** (b + 1) - 1}"
        bar = "#" * max(1, round(40 * r["vertices"] / biggest))
        print(f"  {label:>11} | {bar} {r['vertices']:,}")
    print()


def main():
    args = base_parser(description="Compute network statistics for a dataset.").parse_args()

    # load -> build graph
    cfg = load_config(args.config)
    ds = cfg.dataset(args.dataset)
    spark = get_spark(f"sna-02-network-stats-{args.dataset}", cfg)
    graph = load_graph(spark, cfg, args.dataset)

    # analyze
    # cache(): vertex_stats is used by several aggregations and written to HDFS.
    # Without caching, Spark would re-run triangle counting and connected
    # components for every one of them.
    vstats = stats.vertex_stats(graph, ds.directed).cache()
    deg_dist = stats.degree_distribution(vstats)
    comp_sizes = stats.component_sizes(vstats)
    summary = stats.summarize(vstats, comp_sizes, ds.directed)

    print_summary(args.dataset, ds.directed, summary)
    print_histogram(stats.degree_histogram(vstats).collect())

    # write
    out = "stats"
    write_result(spark.createDataFrame([Row(dataset=args.dataset, **summary)]), cfg, args.dataset, f"{out}/summary")
    write_result(vstats, cfg, args.dataset, f"{out}/vertex_stats")
    write_result(deg_dist, cfg, args.dataset, f"{out}/degree_distribution")
    write_result(comp_sizes, cfg, args.dataset, f"{out}/component_sizes")

    vstats.unpersist()
    spark.stop()


if __name__ == "__main__":
    main()
