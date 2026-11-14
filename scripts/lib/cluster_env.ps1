# Shared helpers for the Phase 2 scripts. Dot-source it:  . (Join-Path $PSScriptRoot "lib\cluster_env.ps1")

# Read a .env file (KEY=value lines, # comments) into a hashtable.
# Fails with a hint if the file is missing or a required key is empty.
function Read-ClusterEnv {
    param([string]$Path, [string]$Template, [string[]]$Required)
    if (-not (Test-Path $Path)) {
        throw "Missing $Path. Create it from the template:  copy $Template .env   (then fill in names + IPs)"
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

# This PC's Wi-Fi / Ethernet IPv4 addresses: the ones to share with the others.
# Skips Docker/WSL virtual adapters (vEthernet) and self-assigned 169.254.x.x addresses.
function Get-LanIPs {
    Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.InterfaceAlias -match '^(Wi-Fi|Ethernet|WLAN)' -and $_.IPAddress -notlike '169.254.*' } |
        ForEach-Object { "$($_.IPAddress)  ($($_.InterfaceAlias))" }
}
