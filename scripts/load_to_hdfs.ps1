# Copy data\raw\<name>\ from your laptop into HDFS at /sna/raw/<name>/.
#   .\scripts\load_to_hdfs.ps1                 # default: facebook
# Works through the namenode container, which sees the host's data\ folder at /data.
param([string]$Dataset = "facebook")
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$compose = Join-Path $root "docker-compose.yml"

if (-not (Test-Path (Join-Path $root "data\raw\$Dataset"))) {
    throw "No local data for '$Dataset'. Run .\scripts\download_dataset.ps1 -Dataset $Dataset first."
}

docker compose -f $compose exec namenode bash -c "hdfs dfs -mkdir -p /sna/raw/$Dataset && hdfs dfs -put -f /data/raw/$Dataset/* /sna/raw/$Dataset/ && hdfs dfs -ls -h /sna/raw/$Dataset"
exit $LASTEXITCODE
