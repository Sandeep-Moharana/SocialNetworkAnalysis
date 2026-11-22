# Phase 2, on the MASTER laptop: start HDFS + Spark master + driver + ONE local
# worker, and let the friends' PCs join. No IPs to type:
#   1. detects this laptop's current IP (changes with every hotspot);
#   2. starts the registry (port 8099) and waits until the friends' PCs have
#      registered their current IPs (they run scripts\worker_up.ps1);
#   3. writes those IPs into .env and starts / refreshes the cluster.
#
#   .\scripts\cluster_up.ps1              # wait up to 3 min for the friends in .env
#   .\scripts\cluster_up.ps1 -NoWait      # start now with whoever has registered
#   .\scripts\cluster_up.ps1 -Build       # also rebuild our Spark image
# Someone joined late? Run it again (it refreshes the IPs; HDFS data is kept).
# Back to Phase 1 (one laptop, 2 local workers):  docker compose up -d
# Guide: docs/PHASE2_SETUP.md
param(
    [switch]$Build,
    [switch]$NoWait,
    [int]$WaitSeconds = 180,
    [string]$EnvFile = ".env"     # another file only for testing
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "lib\cluster_env.ps1")
Push-Location $root
try {
    $envValues = Read-ClusterEnv $EnvFile ".env.master.example" @("FRIEND_A", "FRIEND_B")
    $friends = @($envValues.FRIEND_A, $envValues.FRIEND_B)
    $compose = @("compose", "-f", "docker-compose.yml", "-f", "docker-compose.cluster.yml", "--env-file", $EnvFile)

    # 1. Our own IP on the hotspot.
    $me = Get-MyIPv4
    Set-EnvValue $EnvFile "MASTER_IP" $me.IP
    Write-Host "This laptop (master): $($me.IP)  [$($me.Adapter)]" -ForegroundColor Cyan

    # 2. Registry first, so the friends can find us while we wait.
    docker @compose up -d registry
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    if (-not (Wait-Until { [bool](Get-Registry "localhost") } { "starting the registry ..." } 30)) {
        throw "The registry did not start: docker compose -f docker-compose.yml -f docker-compose.cluster.yml logs registry"
    }

    $missing = { @($friends | Where-Object { -not (Get-Registry "localhost").nodes.$_ }) }
    if (-not $NoWait -and (& $missing).Count -gt 0) {
        Write-Host "Waiting for friends to run scripts\worker_up.ps1 (max $WaitSeconds s; Ctrl+C, then -NoWait, to start without them):"
        $all = Wait-Until { (& $missing).Count -eq 0 } { "still waiting for: $((& $missing) -join ', ')" } $WaitSeconds
        if (-not $all) { Write-Host "  Starting without: $((& $missing) -join ', '). Run this script again when they join." -ForegroundColor Yellow }
    }

    # 3. Write the friends' current IPs into .env (a friend not seen keeps its old value).
    $table = Get-Registry "localhost"
    foreach ($slot in "A", "B") {
        $ip = $table.nodes.($envValues["FRIEND_$slot"])
        if ($ip) { Set-EnvValue $EnvFile "FRIEND_${slot}_IP" $ip }
    }

    # 4. Start / refresh. Containers whose friend IPs changed are re-created;
    #    HDFS data is safe on its volumes.
    $upArgs = @("up", "-d")
    if ($Build) { $upArgs += "--build" }
    docker @compose @upArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    Write-Host "`nCluster members:" -ForegroundColor Cyan
    Write-Host ("  {0,-8} {1,-16} {2}" -f "master", $me.IP, "(this laptop)")
    foreach ($name in $friends) {
        $ip = $table.nodes.$name
        Write-Host ("  {0,-8} {1,-16} {2}" -f $name, $(if ($ip) { $ip } else { "-" }), $(if ($ip) { "registered" } else { "not joined" }))
    }
    Write-Host "`nCheck in ~30 s:  .\scripts\cluster_status.ps1"
}
finally { Pop-Location }
