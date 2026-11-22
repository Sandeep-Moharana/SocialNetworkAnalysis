#!/usr/bin/env bash
# Starts an HDFS DataNode with its blocks on a Docker VOLUME (/hdfs), so the data
# survives container re-creation. Used on the master laptop AND on friends' PCs.
set -euo pipefail

# A new Docker volume belongs to root; give it to the hadoop user, ONCE, with sudo.
# Only when needed: on newer Docker versions sudo fails in this (CentOS 7) image with
# "sudo: PAM account management error". Then do it once as root, from the project folder:
#   docker compose -f docker-compose.worker.yml --profile storage run --rm --no-deps --user root --entrypoint chown datanode hadoop:users /hdfs
# (on the master: docker compose run --rm --no-deps --user root --entrypoint chown datanode hadoop:users /hdfs)
[ -w /hdfs ] || sudo chown hadoop:users /hdfs

echo "[start-datanode] advertising as $(hdfs getconf -confKey dfs.datanode.hostname)," \
     "data port $(hdfs getconf -confKey dfs.datanode.address)"
exec hdfs datanode
