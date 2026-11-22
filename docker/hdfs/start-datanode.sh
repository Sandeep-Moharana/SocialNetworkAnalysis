#!/usr/bin/env bash
# Starts an HDFS DataNode with its blocks on a Docker VOLUME (/hdfs), so the data
# survives container re-creation. Used on the master laptop AND on friends' PCs.
set -euo pipefail

# A new Docker volume belongs to root; give it to the hadoop user (the image allows sudo).
sudo chown hadoop:users /hdfs

echo "[start-datanode] advertising as $(hdfs getconf -confKey dfs.datanode.hostname)," \
     "data port $(hdfs getconf -confKey dfs.datanode.address)"
exec hdfs datanode
