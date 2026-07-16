[CmdletBinding()]
param(
    [string]$ImageTag = "fon-backend:production"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$modelDir = Join-Path $projectRoot "models\BiRefNet"

if (-not (Test-Path (Join-Path $modelDir "config.json"))) {
    throw "BiRefNet config was not found: $modelDir"
}
if (-not (Get-ChildItem -Path $modelDir -Filter "*.safetensors" -File -ErrorAction SilentlyContinue)) {
    throw "BiRefNet weights (*.safetensors) were not found: $modelDir"
}

docker build --file (Join-Path $projectRoot "backend\Dockerfile.production") --tag $ImageTag $projectRoot
if ($LASTEXITCODE -ne 0) {
    throw "Production backend image build failed."
}

Write-Host "Production image built: $ImageTag"
