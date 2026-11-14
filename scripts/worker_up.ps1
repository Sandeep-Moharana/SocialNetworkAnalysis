# Phase 2, on a FRIEND's PC: start this PC's Spark worker and join the master laptop.
#   .\scripts\worker_up.ps1              # names + IPs from .env (template: .env.worker.example)
#   .\scripts\worker_up.ps1 -Build       # rebuild the Spark image (only after docker/spark/ changed)
# Stop:   docker compose -f docker-compose.worker.yml down
# Guide:  docs/PHASE2_SETUP.md
param(
    [switch]$Build,
    [string]$EnvFile = ".env"     # another file only for testing
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "lib\cluster_env.ps1")
Push-Location $root
try {
    $envValues = Read-ClusterEnv $EnvFile ".env.worker.example" @("NODE_NAME", "MASTER_IP", "OTHER_FRIEND", "OTHER_FRIEND_IP")
    $master = $envValues.MASTER_IP

    # Check the network BEFORE starting: can this PC reach the Spark master?
    # Fails if: the master is not up yet, wrong MASTER_IP, master firewall, or Wi-Fi
    # that blocks devices from talking to each other (campus/cafe networks).
    Write-Host "Checking $master port 7077 (Spark master) ..."
    $ok = Test-NetConnection $master -Port 7077 -InformationLevel Quiet -WarningAction SilentlyContinue
    if (-not $ok) {
        Write-Host "Cannot reach the Spark master at ${master}:7077." -ForegroundColor Red
        Write-Host "Is the master running (scripts\cluster_up.ps1)? Is MASTER_IP right? Same Wi-Fi? See docs/PHASE2_SETUP.md, Troubleshooting."
        exit 1
    }

    $compose = @("compose", "-f", "docker-compose.worker.yml", "--env-file", $EnvFile)
    $upArgs = @("up", "-d")
    if ($Build) { $upArgs += "--build" }   # the first run builds automatically (image missing)
    docker @compose @upArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host ("`nworker-{0} started. It should show as ALIVE at http://{1}:8080 within ~10 s." -f $envValues.NODE_NAME, $master) -ForegroundColor Green
    Write-Host "This PC's IP (the master puts it in its .env):"
    Get-LanIPs | ForEach-Object { Write-Host "  $_" }
    Write-Host "Logs:  docker compose -f docker-compose.worker.yml logs -f"
}
finally { Pop-Location }
