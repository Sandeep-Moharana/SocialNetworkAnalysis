"""
Step 1.4: load a dataset from HDFS into a GraphFrame and report its size.

The first run parses the raw file and saves the cleaned graph to
/sna/processed/<dataset>/. Later runs (and later jobs) reuse it.

    .\\scripts\\submit.ps1 jobs\\01_build_graph.py                  # facebook
    .\\scripts\\submit.ps1 jobs\\01_build_graph.py --rebuild        # re-parse the raw file
    .\\scripts\\submit.ps1 jobs\\01_build_graph.py --dataset <name>
"""
from sna.cli import base_parser
from sna.config import load_config
from sna.loaders import load_graph
from sna.session import get_spark
from sna.storage import write_result


def main():
    parser = base_parser(description="Build the graph for a dataset and print its size.")
    parser.add_argument("--rebuild", action="store_true",
                        help="ignore the processed graph and re-parse the raw file")
    args = parser.parse_args()

    # load -> build graph
    cfg = load_config(args.config)
    ds = cfg.dataset(args.dataset)
    spark = get_spark(f"sna-01-build-graph-{args.dataset}", cfg)
    graph = load_graph(spark, cfg, args.dataset, rebuild=args.rebuild)

    # analyze (just sizes for now; real statistics come in step 1.5)
    n_vertices = graph.vertices.count()
    n_edge_rows = graph.edges.count()
    # Undirected data stores each friendship twice (A->B and B->A).
    n_connections = n_edge_rows if ds.directed else n_edge_rows // 2

    print(f"\nDataset     : {args.dataset} ({'directed' if ds.directed else 'undirected'})")
    print(f"Vertices    : {n_vertices:,}")
    print(f"Connections : {n_connections:,}")
    print(f"Edge rows   : {n_edge_rows:,}  (rows in the GraphFrame edges table)\n")
    print("Sample edges:")
    graph.edges.orderBy("src", "dst").show(5)

    # write
    summary = spark.createDataFrame(
        [(args.dataset, ds.directed, n_vertices, n_connections, n_edge_rows)],
        ["dataset", "directed", "vertices", "connections", "edge_rows"],
    )
    write_result(summary, cfg, args.dataset, "graph_summary")
    spark.stop()


if __name__ == "__main__":
    main()
