[CmdletBinding()]
param(
    [int]$Port = 8000,
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"
if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}
$apiUrl = "http://127.0.0.1:$Port"
$sampleImage = Join-Path $ProjectRoot "frontend\public\birdtech-logo.png"
$resultPath = Join-Path $env:TEMP "fon-production-result.png"

if (-not (Test-Path $sampleImage)) {
    throw "Test image not found: $sampleImage"
}

$health = Invoke-RestMethod "$apiUrl/api/health"
if ($health.status -ne "ok" -or -not $health.modelInstalled) {
    throw "Production health check failed: $($health | ConvertTo-Json -Compress)"
}

try {
    $curlArgs = @(
        "--silent", "--show-error", "--max-time", "300", "--output", $resultPath,
        "--write-out", "%{http_code}", "--form", "file=@$sampleImage;type=image/png",
        "$apiUrl/api/remove-background"
    )
    $status = & curl.exe @curlArgs
    if ($status -ne "200") {
        throw "Background removal returned HTTP $status"
    }

    $png = [System.IO.File]::ReadAllBytes($resultPath)
    if ($png.Length -lt 26 -or $png[25] -ne 6) {
        throw "The result is not an RGBA PNG."
    }
    Write-Host "Production backend test passed: PNG with alpha channel returned."
}
finally {
    Remove-Item -LiteralPath $resultPath -ErrorAction SilentlyContinue
}
