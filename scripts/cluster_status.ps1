# Who is in the cluster right now? Run on the MASTER laptop.
#   .\scripts\cluster_status.ps1
# Shows the Spark workers (compute) and the HDFS DataNodes (storage), and whether
# every file has its 2 copies.
# Not "Stop": hdfs prints normal progress messages ("Connecting to namenode ...") to
# stderr, and Windows PowerShell 5.1 would turn those into errors. This script only reads.
$ErrorActionPreference = "Continue"
$root = Split-Path $PSScriptRoot -Parent
$compose = Join-Path $root "docker-compose.yml"
. (Join-Path $PSScriptRoot "lib\cluster_env.ps1")

Write-Host "=== Registry (who is where right now) ===" -ForegroundColor Cyan
$table = Get-Registry "localhost"
if ($table) {
    Write-Host ("  {0,-8} {1}" -f "master", $table.master)
    foreach ($name in $table.expected) {
        $ip = $table.nodes.$name
        Write-Host ("  {0,-8} {1}" -f $name, $(if ($ip) { $ip } else { "- (not registered)" }))
    }
}
else { Write-Host "  Not running (Phase 1 mode, or start it with .\scripts\cluster_up.ps1)." }
Write-Host ""

Write-Host "=== Spark workers (compute) ===" -ForegroundColor Cyan
try {
    $master = Invoke-RestMethod http://localhost:8080/json/ -TimeoutSec 5
    $master.workers | Where-Object state -ne "DEAD" |
        Select-Object @{n = "Worker"; e = { $_.host } }, @{n = "State"; e = { $_.state } }, @{n = "Cores"; e = { $_.cores } } |
        Format-Table -AutoSize | Out-Host
}
catch { Write-Host "Spark master not reachable on http://localhost:8080. Is the cluster up?" -ForegroundColor Red }

Write-Host "=== HDFS DataNodes (storage) ===" -ForegroundColor Cyan
# dfsadmin -report lists every DataNode with its name and last heartbeat.
$report = docker compose -f $compose exec -T namenode hdfs dfsadmin -report 2>$null
$nodes = @(); $section = ""; $current = $null
foreach ($line in $report) {
    if ($line -match '^(Live|Dead) datanodes') { $section = $Matches[1] }
    elseif ($line -match '^Hostname: (.+)$') { $current = [ordered]@{ DataNode = $Matches[1]; State = $section; Used = ""; LastContact = "" }; $nodes += $current }
    elseif ($current -and $line -match '^DFS Used: \d+ \((.+)\)') { $current.Used = $Matches[1] }
    elseif ($current -and $line -match '^Last contact: (.+)$') { $current.LastContact = $Matches[1] }
}
$nodes | ForEach-Object { [pscustomobject]$_ } | Format-Table -AutoSize | Out-Host

Write-Host "=== HDFS health (/sna) ===" -ForegroundColor Cyan
docker compose -f $compose exec -T namenode hdfs fsck /sna 2>$null |
    Select-String -Pattern "Status:|Total blocks|Under-replicated blocks|Missing blocks|Corrupt blocks" |
    ForEach-Object { Write-Host "  $($_.Line.Trim())" }
Write-Host "  (Under-replicated = some blocks have only 1 of their 2 copies: normal while only one PC stores data.)"
