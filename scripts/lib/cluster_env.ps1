# Shared helpers for the Phase 2 scripts. Dot-source it:  . (Join-Path $PSScriptRoot "lib\cluster_env.ps1")

$RegistryPort = 8099    # scripts/container/registry.py on the master laptop

# Read a .env file (KEY=value lines, # comments) into a hashtable.
# Fails with a hint if the file is missing or a required key is empty.
function Read-ClusterEnv {
    param([string]$Path, [string]$Template, [string[]]$Required)
    if (-not (Test-Path $Path)) {
        throw "Missing $Path. Create it from the template:  copy $Template .env   (then fill in the names)"
    }
    $values = @{}
    foreach ($line in Get-Content $Path) {
        $line = $line.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { continue }
        $key, $value = $line -split "=", 2
        $values[$key.Trim()] = "$value".Trim()
    }
    foreach ($key in $Required) {
        if (-not $values[$key]) { throw "$key is missing or empty in $Path (see $Template)" }
    }
    return $values
}

# Set KEY=value in a .env file: replace the line if the key exists, else append it.
# Comments and other lines stay as they are.
function Set-EnvValue {
    param([string]$Path, [string]$Key, [string]$Value)
    $lines = @()
    if (Test-Path $Path) { $lines = @(Get-Content $Path) }
    $found = $false
    $lines = @($lines | ForEach-Object {
            if ($_ -match "^\s*$([regex]::Escape($Key))\s*=") { $found = $true; "$Key=$Value" } else { $_ }
        })
    if (-not $found) { $lines += "$Key=$Value" }
    Set-Content -Path $Path -Value $lines -Encoding ascii
}

# This PC's current IPv4 on the network it uses for the internet (the hotspot):
# the adapter that has a default gateway. Skips Docker/WSL virtual adapters.
function Get-MyIPv4 {
    $configs = @(Get-NetIPConfiguration -ErrorAction SilentlyContinue | Where-Object {
            $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up" -and $_.InterfaceAlias -notmatch "vEthernet|WSL|Docker"
        } | Sort-Object { if ($_.InterfaceAlias -match "^(Wi-?Fi|WLAN)") { 0 } else { 1 } })
    if ($configs.Count -eq 0) { throw "No connected network found. Connect this PC to the hotspot / Wi-Fi first." }
    $addr = @($configs[0].IPv4Address)[0]
    return [pscustomobject]@{ IP = $addr.IPAddress; Prefix = $addr.PrefixLength; Adapter = $configs[0].InterfaceAlias }
}

# Can we open a TCP connection to host:port within the timeout?
function Test-Port {
    param([string]$HostName, [int]$Port, [int]$TimeoutMs = 1500)
    $client = New-Object System.Net.Sockets.TcpClient
    try { return $client.ConnectAsync($HostName, $Port).Wait($TimeoutMs) -and $client.Connected }
    catch { return $false }
    finally { $client.Dispose() }
}

# Ask the registry at host for the table of who is where (null if it is not our registry).
function Get-Registry {
    param([string]$HostName, [string]$Query = "hosts")
    try {
        $r = Invoke-RestMethod "http://${HostName}:$RegistryPort/$Query" -TimeoutSec 4
        if ($r.service -eq "sna-registry") { return $r }
    }
    catch {}
    return $null
}

# Find the master laptop: try every address of this PC's /24 network (phone hotspots
# use /24) on the registry port at the same time; about 1 second in total.
function Find-Registry {
    param([string]$MyIP, [string[]]$Candidates, [int]$TimeoutMs = 1200)
    if (-not $Candidates) {
        $base = ($MyIP -split "\.")[0..2] -join "."
        $Candidates = 1..254 | ForEach-Object { "$base.$_" } | Where-Object { $_ -ne $MyIP }
    }
    $attempts = foreach ($ip in $Candidates) {
        $client = New-Object System.Net.Sockets.TcpClient
        [pscustomobject]@{ IP = $ip; Client = $client; Task = $client.ConnectAsync($ip, $RegistryPort) }
    }
    Start-Sleep -Milliseconds $TimeoutMs
    $open = @($attempts | Where-Object { $_.Task.Status -eq "RanToCompletion" -and $_.Client.Connected } | ForEach-Object { $_.IP })
    $attempts | ForEach-Object { $_.Client.Dispose() }
    foreach ($ip in $open) { if (Get-Registry $ip) { return $ip } }   # open port AND our registry
    return $null
}

# Wait until the script block returns $true, printing a message whenever it changes.
function Wait-Until {
    param([scriptblock]$Condition, [scriptblock]$Status, [int]$TimeoutSec)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $last = ""
    while ($true) {
        if (& $Condition) { return $true }
        if ((Get-Date) -gt $deadline) { return $false }
        $now = & $Status
        if ($now -ne $last) { Write-Host "  $now"; $last = $now }
        Start-Sleep -Seconds 3
    }
}

# This PC's Wi-Fi / Ethernet IPv4 addresses (for display).
function Get-LanIPs {
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.InterfaceAlias -match '^(Wi-Fi|Ethernet|WLAN)' -and $_.IPAddress -notlike '169.254.*' } |
        ForEach-Object { "$($_.IPAddress)  ($($_.InterfaceAlias))" }
}
