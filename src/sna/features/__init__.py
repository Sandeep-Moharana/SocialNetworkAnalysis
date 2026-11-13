"""
Analysis features. Each module takes a GraphFrame and returns DataFrames/values.

Rules for feature code (keeps it testable and cluster-independent):
  * no file paths, no hosts, no reading or writing: jobs do the I/O
  * assume the graph came from sna.loaders (no self-loops, no duplicate edges,
    undirected data stored in both directions)
"""
