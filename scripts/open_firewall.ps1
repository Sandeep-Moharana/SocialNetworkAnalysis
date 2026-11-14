# Phase 2: allow the other cluster PCs through Windows Firewall. Run as ADMINISTRATOR.
#   .\scripts\open_firewall.ps1 -Role master     # on your laptop
#   .\scripts\open_firewall.ps1 -Role worker     # on a friend's PC
#   .\scripts\open_firewall.ps1 -Remove          # remove the rule when you are done
# Re-run it when an IP in .env changes: it replaces the old rule.
#
# Safety: Spark and HDFS have no passwords here; whoever reaches these ports can
# run code on this PC. So the rule ONLY accepts the IPs listed in .env. That is why
# it can apply on any network profile: no need to mark campus Wi-Fi as "Private"
# (which would also make this PC visible for file sharing to everyone on it).
# Remove the rule when the project is done (-Remove).
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
    # Which ports the OTHER PCs connect to, and who those PCs are.
    # (Same port numbers as docker-compose*.yml and docker/spark-defaults.conf.)
    if ($Role -eq "master") {
        $e = Read-ClusterEnv $EnvFile ".env.master.example" @("FRIEND_A_IP", "FRIEND_B_IP")
        $peers = @($e.FRIEND_A_IP, $e.FRIEND_B_IP)
        # 7077 master, 7079 our executor, 7080/7081 driver, 8020/9866 HDFS; the rest are web UIs
        $ports = @(7077, 7079, 7080, 7081, 8020, 9866, 8080, 8081, 9870, 4040)
    }
    else {
        $e = Read-ClusterEnv $EnvFile ".env.worker.example" @("MASTER_IP", "OTHER_FRIEND_IP")
        $peers = @($e.MASTER_IP, $e.OTHER_FRIEND_IP)
        # 7078 worker (master starts executors), 7079 our executor, 8081 worker UI
        $ports = @(7078, 7079, 8081)
    }
    $peers = $peers | Sort-Object -Unique

    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP `
        -LocalPort $ports -RemoteAddress $peers -Profile Any | Out-Null
    Write-Host "Firewall rule '$ruleName': TCP $($ports -join ', ') open for $($peers -join ', ') only." -ForegroundColor Green
}
finally { Pop-Location }
