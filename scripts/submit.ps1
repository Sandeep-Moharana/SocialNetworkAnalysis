# Run a Spark job on the cluster.
#   .\scripts\submit.ps1 jobs\00_smoke_test.py [job args...]
# Cluster settings (master URL, GraphFrames package, memory) come from docker\spark-defaults.conf.
param(
    [Parameter(Mandatory = $true)][string]$Job,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$JobArgs
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$compose = Join-Path $root "docker-compose.yml"

# jobs\foo.py (Windows path on the host) -> /app/jobs/foo.py (Linux path in the container)
$containerPath = "/app/" + (($Job -replace '^\.[\\/]', '') -replace '\\', '/')

docker compose -f $compose exec spark-client /opt/spark/bin/spark-submit $containerPath @JobArgs
exit $LASTEXITCODE
