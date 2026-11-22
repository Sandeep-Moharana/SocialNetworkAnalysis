# Run a Spark job on the cluster.
#   .\scripts\submit.ps1 jobs\00_smoke_test.py [job args...]
#   .\scripts\submit.ps1 jobs\02_network_stats.py -Conf spark.speculation=true   # extra Spark settings
# Cluster settings (master URL, GraphFrames package, memory) come from docker\spark-defaults.conf.
# -Conf is for experiments (e.g. Phase 2 tuning) without editing that file.
param(
    [Parameter(Mandatory = $true)][string]$Job,
    [string[]]$Conf = @(),
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$JobArgs
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$compose = Join-Path $root "docker-compose.yml"

# jobs\foo.py (Windows path on the host) -> /app/jobs/foo.py (Linux path in the container)
$containerPath = "/app/" + (($Job -replace '^\.[\\/]', '') -replace '\\', '/')

# spark-submit options must come BEFORE the job file: --conf key=value for each -Conf.
$sparkOptions = @()
foreach ($c in $Conf) { $sparkOptions += @("--conf", $c) }

# spark_submit.sh (inside the container) packages src/sna for the executors, then runs spark-submit.
docker compose -f $compose exec spark-client bash /app/scripts/container/spark_submit.sh @sparkOptions $containerPath @JobArgs
exit $LASTEXITCODE
