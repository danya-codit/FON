[CmdletBinding()]
param(
    [int]$Port = 8000,
    [string]$ImageTag = "fon-backend:production",
    [string]$ContainerName = "fon-backend-production",
    [string]$AllowedOrigins = "http://localhost:3000,http://127.0.0.1:3000"
)

$ErrorActionPreference = "Stop"
$dockerArgs = @(
    "run", "--rm", "--name", $ContainerName,
    "--publish", "${Port}:${Port}",
    "--env", "PORT=$Port",
    "--env", "STORAGE_BACKEND=mock",
    "--env", "ALLOWED_ORIGINS=$AllowedOrigins",
    $ImageTag
)

& docker @dockerArgs
