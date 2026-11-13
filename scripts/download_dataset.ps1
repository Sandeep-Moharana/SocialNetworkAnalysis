# Download a dataset into data\raw\<name>\ and unzip it.
#   .\scripts\download_dataset.ps1                 # default: facebook
#   .\scripts\download_dataset.ps1 -Dataset facebook
# To add a dataset, add one entry to $Datasets below.
param([string]$Dataset = "facebook")
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # the progress bar makes downloads very slow in PowerShell 5
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Datasets = @{
    # SNAP ego-Facebook: 4,039 nodes, 88,234 undirected edges. https://snap.stanford.edu/data/ego-Facebook.html
    facebook = @{ Url = "https://snap.stanford.edu/data/facebook_combined.txt.gz"; File = "facebook_combined.txt" }
}

if (-not $Datasets.ContainsKey($Dataset)) {
    throw "Unknown dataset '$Dataset'. Known: $($Datasets.Keys -join ', ')"
}
$d = $Datasets[$Dataset]
$root = Split-Path $PSScriptRoot -Parent
$outDir = Join-Path $root "data\raw\$Dataset"
$txt = Join-Path $outDir $d.File
$gz = "$txt.gz"

if (Test-Path $txt) { Write-Host "Already downloaded: $txt"; exit 0 }
New-Item -ItemType Directory -Force $outDir | Out-Null

Write-Host "Downloading $($d.Url) ..."
Invoke-WebRequest -Uri $d.Url -OutFile $gz -UseBasicParsing

Write-Host "Unzipping ..."
$in = [IO.File]::OpenRead($gz)
$unzip = New-Object IO.Compression.GZipStream($in, [IO.Compression.CompressionMode]::Decompress)
$out = [IO.File]::Create($txt)
try { $unzip.CopyTo($out) } finally { $out.Close(); $unzip.Close(); $in.Close() }
Remove-Item $gz

$lines = 0; foreach ($l in [IO.File]::ReadLines($txt)) { $lines++ }
Write-Host "Saved $txt ($lines lines)"
