# Phase 2: let the other cluster PCs through Windows Firewall. Run ONCE per PC,
# as ADMINISTRATOR:
#   .\scripts\open_firewall.ps1 -Role master     # on the master laptop
#   .\scripts\open_firewall.ps1 -Role worker     # on a friend's PC (needs DATANODE_PORT in .env)
#   .\scripts\open_firewall.ps1 -Remove          # remove the rule when the project is done
#
# The rule accepts "LocalSubnet": any device on the network this PC is connected to
# right now. So it keeps working when the hotspot hands out new IPs (no re-run needed).
#
# Safety: Spark and HDFS have no passwords here; whoever reaches these ports can run
# code on this PC. On your own phone hotspot, "LocalSubnet" is just your team. On a
# big shared network (campus, cafe) it is everyone there: use your hotspot for the
# cluster, and run -Remove when the project is done.
param(
    [ValidateSet("master", "worker")][string]$Role,
    [switch]$Remove,
    [string]$EnvFile = ".env"
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $PSScriptRoot "lib\cluster_env.ps1")
$ruleName = "SNA cluster (Phase 2)"

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw "Run this in PowerShell opened with 'Run as administrator'." }

Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
if ($Remove) { Write-Host "Removed firewall rule '$ruleName'."; exit 0 }
if (-not $Role) { throw "Pass -Role master or -Role worker." }

Push-Location $root
try {
    # Which ports the OTHER PCs connect to (same numbers as docker-compose*.yml
    # and docker/spark-defaults.conf).
    if ($Role -eq "master") {
        # 8099 registry, 7077 Spark master, 7079 our executor, 7080/7081 driver,
        # 8020 NameNode, 9866/9867 our DataNode; the rest are web UIs
        $ports = @(8099, 7077, 7079, 7080, 7081, 8020, 9866, 9867, 8080, 8081, 9870, 4040)
    }
    else {
        $e = Read-ClusterEnv $EnvFile ".env.worker.example" @("DATANODE_PORT")
        # 7078 worker (master starts executors), 7079 our executor, 8081 worker UI,
        # then our DataNode: data port, IPC, web UI
        $ipc = if ($e.DATANODE_IPC_PORT) { $e.DATANODE_IPC_PORT } else { 9867 }
        $http = if ($e.DATANODE_HTTP_PORT) { $e.DATANODE_HTTP_PORT } else { 9864 }
        $ports = @(7078, 7079, 8081, [int]$e.DATANODE_PORT, [int]$ipc, [int]$http)
    }

    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP `
        -LocalPort $ports -RemoteAddress LocalSubnet -Profile Any | Out-Null
    Write-Host "Firewall rule '$ruleName': TCP $($ports -join ', ') open for devices on the same network (LocalSubnet)." -ForegroundColor Green
    Write-Host "No need to run this again when IPs change."
}
finally { Pop-Location }
