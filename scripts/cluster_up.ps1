# Phase 2, on the MASTER laptop: start HDFS + Spark master + driver + ONE local
# worker, set up to accept workers from the friends' PCs.
#   .\scripts\cluster_up.ps1             # names + IPs from .env (template: .env.master.example)
#   .\scripts\cluster_up.ps1 -Build      # also rebuild our Spark image
# Back to Phase 1 (one laptop, 2 local workers):  docker compose up -d
# Guide: docs/PHASE2_SETUP.md
param(
    [switch]$Build,
    [string]$EnvFile = ".env"     # another file only for testing
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "lib\cluster_env.ps1")
Push-Location $root
try {
    $envValues = Read-ClusterEnv $EnvFile ".env.master.example" @("FRIEND_A", "FRIEND_A_IP", "FRIEND_B", "FRIEND_B_IP")

    # docker-compose.yml = the Phase 1 cluster; docker-compose.cluster.yml adds the
    # friends' names (extra_hosts) and switches spark-worker-2 off.
    $compose = @("compose", "-f", "docker-compose.yml", "-f", "docker-compose.cluster.yml", "--env-file", $EnvFile)
    $upArgs = @("up", "-d")
    if ($Build) { $upArgs += "--build" }
    docker @compose @upArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "`nMaster is up. Expecting workers:" -ForegroundColor Cyan
    Write-Host ("  worker-{0} at {1}" -f $envValues.FRIEND_A, $envValues.FRIEND_A_IP)
    Write-Host ("  worker-{0} at {1}" -f $envValues.FRIEND_B, $envValues.FRIEND_B_IP)
    Write-Host "`nYour IP (friends put it in MASTER_IP):" -ForegroundColor Cyan
    Get-LanIPs | ForEach-Object { Write-Host "  $_" }
    Write-Host "`nWorkers appear at http://localhost:8080 once friends run scripts\worker_up.ps1."
}
finally { Pop-Location }
