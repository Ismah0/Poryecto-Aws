# ==============================================================================
# DocuShield Automated Deployment Script (PowerShell / Windows)
# ==============================================================================
[CmdletBinding()]
param (
    [switch]$Deploy,
    [switch]$Status,
    [switch]$Local,
    [string]$Region = "us-east-1"
)

Write-Host "=== DocuShield: Despliegue Automatizado de Infraestructura AWS (PowerShell) ===" -ForegroundColor Cyan

$pyCmd = "python"
if (-not (Get-Command $pyCmd -ErrorAction SilentlyContinue)) {
    $pyCmd = "py"
}

$argsList = @("infra/deploy.py")
if ($Deploy) { $argsList += "--deploy" }
if ($Status) { $argsList += "--status" }
if ($Local)  { $argsList += "--local" }
if ($Region) { $argsList += "--region", $Region }

if (-not $Deploy -and -not $Status -and -not $Local) {
    $argsList += "--deploy"
}

& $pyCmd $argsList
