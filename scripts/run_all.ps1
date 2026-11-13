# Run the whole Phase 1 pipeline in order and time each job.
#   .\scripts\run_all.ps1                      # facebook
#   .\scripts\run_all.ps1 -Dataset <name>
# The timing table is our single-machine baseline: in Phase 2 we run the same
# script on the multi-PC cluster and compare.
# Note: 05_recommend uses its default user (0); pass other users by running it alone.
param([string]$Dataset = "facebook")
$submit = Join-Path $PSScriptRoot "submit.ps1"

$jobs = @(
    "jobs\01_build_graph.py",
    "jobs\02_network_stats.py",
    "jobs\03_influencers.py",
    "jobs\04_communities.py",
    "jobs\05_recommend.py"
)

$results = @()
foreach ($job in $jobs) {
    Write-Host "`n>>> $job --dataset $Dataset" -ForegroundColor Cyan
    $start = Get-Date
    & $submit $job --dataset $Dataset
    $code = $LASTEXITCODE
    $results += [pscustomobject]@{
        Job     = $job
        Seconds = [math]::Round(((Get-Date) - $start).TotalSeconds)
        Status  = $(if ($code -eq 0) { "ok" } else { "FAILED (exit $code)" })
    }
    if ($code -ne 0) { break }   # later jobs depend on earlier ones
}

Write-Host "`n=== Pipeline timing: $Dataset ===" -ForegroundColor Cyan
$results | Format-Table -AutoSize | Out-Host
Write-Host ("Total: {0} s" -f ($results | Measure-Object Seconds -Sum).Sum)
if ($results | Where-Object { $_.Status -ne "ok" }) { exit 1 }
