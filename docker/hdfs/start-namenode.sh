#!/usr/bin/env bash
# Starts the HDFS NameNode with its metadata on a Docker VOLUME (/hdfs), so HDFS
# survives "docker compose down" and container re-creation (e.g. when switching
# between Phase 1 and Phase 2 mode).
#
# Runs as the image's 'hadoop' user, after the image has written the *-site.xml
# files from docker/hadoop.env.
set -euo pipefail

# A new Docker volume belongs to root; give it to the hadoop user (the image allows sudo).
sudo chown hadoop:users /hdfs

# Format only the very first time (no metadata yet). A FIXED cluster id means the
# DataNodes (also on friends' PCs) still match if the NameNode is ever re-formatted.
if [ ! -d /hdfs/name/current ]; then
    echo "[start-namenode] no metadata in /hdfs/name: formatting a new HDFS"
    hdfs namenode -format -nonInteractive -clusterid sna-cluster
fi

exec hdfs namenode
