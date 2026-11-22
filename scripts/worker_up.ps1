# Phase 2, on a FRIEND's PC: join the master laptop. No IPs to type:
#   1. detects this PC's current IP (changes with every hotspot);
#   2. finds the master laptop on the hotspot (its registry, port 8099);
#   3. registers "I am <NODE_NAME> at <my IP>" and waits for the other friend;
#   4. writes everyone's current IPs into .env and starts the containers.
#
#   .\scripts\worker_up.ps1                    # Spark worker + HDFS DataNode
#   .\scripts\worker_up.ps1 -NoStorage         # Spark worker only
#   .\scripts\worker_up.ps1 -MasterIP 10.1.2.3 # skip the search (e.g. on a big campus network)
#   .\scripts\worker_up.ps1 -CheckOnly         # only find + register, start nothing
#   .\scripts\worker_up.ps1 -Build             # rebuild the Spark image (after docker/spark/ changed)
# Stop:   docker compose -f docker-compose.worker.yml --profile storage stop
# Guide:  docs/PHASE2_SETUP.md
param(
    [switch]$Build,
    [switch]$NoStorage,
    [switch]$CheckOnly,
    [string]$MasterIP,
    [int]$WaitSeconds = 180,
    [string]$EnvFile = ".env"     # another file only for testing
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "lib\cluster_env.ps1")
Push-Location $root
try {
    $envValues = Read-ClusterEnv $EnvFile ".env.worker.example" @("NODE_NAME", "DATANODE_PORT")
    $name = $envValues.NODE_NAME

    # 1. Our own IP on the hotspot.
    $me = Get-MyIPv4
    Write-Host "This PC ($name): $($me.IP)  [$($me.Adapter)]" -ForegroundColor Cyan

    # 2. Find the master: given IP > last session's IP (if still valid) > search the hotspot.
    $master = $null
    if ($MasterIP) { $master = $MasterIP }
    elseif ($envValues.MASTER_IP -and (Get-Registry $envValues.MASTER_IP)) { $master = $envValues.MASTER_IP }
    else {
        Write-Host "Searching the hotspot ($(($me.IP -split '\.')[0..2] -join '.').1-254) for the master laptop ..."
        $master = Find-Registry $me.IP
    }
    if (-not $master -or -not (Get-Registry $master)) {
        Write-Host "Master laptop not found." -ForegroundColor Red
        Write-Host "  - Is .\scripts\cluster_up.ps1 running on the master laptop?"
        Write-Host "  - Same hotspot? Firewall opened once on the master (open_firewall.ps1 -Role master)?"
        Write-Host "  - Or give its IP:  .\scripts\worker_up.ps1 -MasterIP <master's IP>"
        exit 1
    }

    # 3. Register and wait for the other friend(s) the master expects.
    $table = Get-Registry $master "register?name=$name&ip=$($me.IP)"
    Write-Host "Registered with the master at $master." -ForegroundColor Green
    if ($table.expected -notcontains $name) {
        Write-Host "Warning: the master expects '$($table.expected -join "', '")', not '$name'. Check NODE_NAME in .env." -ForegroundColor Yellow
    }
    $others = @($table.expected | Where-Object { $_ -ne $name })
    $missing = { @($others | Where-Object { -not (Get-Registry $master).nodes.$_ }) }
    if ((& $missing).Count -gt 0) {
        Write-Host "Waiting for the other friend (max $WaitSeconds s):"
        $all = Wait-Until { (& $missing).Count -eq 0 } { "still waiting for: $((& $missing) -join ', ')" } $WaitSeconds
        if (-not $all) { Write-Host "  Starting without: $((& $missing) -join ', '). Run this script again when they join." -ForegroundColor Yellow }
    }
    $table = Get-Registry $master

    # 4. Write the current IPs into .env (the compose file reads them from there).
    $masterIpForDocker = if ($table.master) { $table.master } else { $master }
    $other = if ($others.Count -gt 0) { $others[0] } else { "nobody" }
    $otherIp = $table.nodes.$other
    if (-not $otherIp) { $otherIp = "127.0.0.1" }     # not joined: harmless placeholder
    Set-EnvValue $EnvFile "MASTER_IP" $masterIpForDocker
    Set-EnvValue $EnvFile "OTHER_FRIEND" $other
    Set-EnvValue $EnvFile "OTHER_FRIEND_IP" $otherIp
    Write-Host "Cluster: master $masterIpForDocker, $name $($me.IP), $other $(if ($otherIp -ne '127.0.0.1') { $otherIp } else { '(not joined)' })"
    if ($CheckOnly) { Write-Host "CheckOnly: .env updated, nothing started."; exit 0 }

    # 5. The master starts its cluster after its own wait: give it time to open port 7077.
    if (-not (Wait-Until { Test-Port $masterIpForDocker 7077 } { "waiting for the Spark master to start ..." } 120)) {
        Write-Host "Spark master at ${masterIpForDocker}:7077 not reachable. Starting anyway; the worker keeps retrying." -ForegroundColor Yellow
    }

    $compose = @("compose", "-f", "docker-compose.worker.yml", "--env-file", $EnvFile)
    if (-not $NoStorage) { $compose += @("--profile", "storage") }
    $upArgs = @("up", "-d")
    if ($Build) { $upArgs += "--build" }   # the first run builds automatically (image missing)
    docker @compose @upArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $what = if ($NoStorage) { "worker-$name" } else { "worker-$name + datanode-$name" }
    Write-Host "`n$what started. The master can check with .\scripts\cluster_status.ps1" -ForegroundColor Green
    Write-Host "Logs:  docker compose -f docker-compose.worker.yml --profile storage logs -f"
}
finally { Pop-Location }
