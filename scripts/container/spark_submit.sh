#!/usr/bin/env bash
# Runs INSIDE the spark-client container (called by scripts/submit.ps1).
#
# Our library lives in /app/src/sna. The driver could import it from the mounted
# folder, but executors on other machines (Phase 2) can't see that folder.
# So we zip the package and pass it with --py-files: Spark adds the zip to the
# Python path of the driver AND sends it to every executor.
set -euo pipefail

python3 -m zipfile -c /tmp/sna.zip /app/src/sna   # -> /tmp/sna.zip containing sna/...

exec /opt/spark/bin/spark-submit --py-files /tmp/sna.zip "$@"
