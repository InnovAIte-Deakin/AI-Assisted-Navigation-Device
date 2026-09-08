[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ModelPath,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$ManifestPath,

    [string]$Python = "python",
    [string]$BackendDirectory = "software_side/walkbuddy_reactNative/backend",
    [string]$Host = "0.0.0.0",
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [string]$AllowedOrigins,
    [switch]$RequireCuda,
    [switch]$Execute
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
$model = (Resolve-Path -LiteralPath $ModelPath).Path
$manifest = (Resolve-Path -LiteralPath $ManifestPath).Path
$backend = (Resolve-Path -LiteralPath (Join-Path $repoRoot $BackendDirectory)).Path
$readinessTool = Join-Path $repoRoot "ML_side/deployment/tools/check_candidate_readiness.py"

if ((Split-Path -Leaf $model) -ne "best.pt") {
    throw "Candidate model must be named best.pt because the backend appends best.pt to WALKBUDDY_MODEL_DIR."
}

$preflightArguments = @($readinessTool, "--manifest", $manifest, "--model", $model)
if ($RequireCuda) { $preflightArguments += "--require-cuda" }

Write-Host "Candidate backend launch preparation (read-only validation)"
Write-Host "Model: $model"
Write-Host "Model SHA is checked by deployment readiness; no artifact is copied or modified."
& $Python @preflightArguments
if ($LASTEXITCODE -ne 0) { throw "Deployment readiness failed; backend was not started." }

$env:WALKBUDDY_MODEL_DIR = Split-Path -Parent $model
$env:WALKBUDDY_ML_MOCK = "0"
if ($AllowedOrigins) { $env:WALKBUDDY_ALLOWED_ORIGINS = $AllowedOrigins }

$uvicornArguments = @("-m", "uvicorn", "main:app", "--host", $Host, "--port", "$Port")
Write-Host "Candidate model directory: $env:WALKBUDDY_MODEL_DIR"
Write-Host "ML mock mode: $env:WALKBUDDY_ML_MOCK"
Write-Host "Backend command preview: $Python $($uvicornArguments -join ' ')"
if (-not $Execute) {
    Write-Host "Dry run complete. Add -Execute to launch after reviewing the command."
    exit 0
}

Push-Location $backend
try {
    & $Python @uvicornArguments
}
finally {
    Pop-Location
}
