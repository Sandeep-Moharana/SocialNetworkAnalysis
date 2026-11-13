"""
sna: reusable code for the Social Network Analysis jobs.

    config    reads config/sna.ini (HDFS paths, dataset formats)
    session   creates the SparkSession
    loaders   raw edge list on HDFS -> GraphFrame
    storage   writes DataFrames to HDFS
    cli       command-line arguments shared by all jobs

Jobs in jobs/ only put these pieces together: load -> build graph -> analyze -> write.
"""
