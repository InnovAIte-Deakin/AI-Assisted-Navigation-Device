[CmdletBinding()]
param(
    [string]$ModelPath,
    [string]$ManifestPath,
    [string]$Python,
    [string]$BackendDirectory = "software_side/walkbuddy_reactNative/backend",
    [Alias("Host")]
    [string]$BindHost = "0.0.0.0",
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [string]$AllowedOrigins,
    [switch]$RequireCuda,
    [switch]$Execute
)

$ErrorActionPreference = "Stop"

function Resolve-BackendPythonInterpreter {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$BackendDirectory,
        [string]$ExplicitPython,
        [switch]$ExplicitPythonSupplied
    )

    if ($ExplicitPythonSupplied) {
        return [PSCustomObject]@{
            Invocation = $ExplicitPython
            Source = "explicit -Python argument"
        }
    }

    $venvDirectory = Join-Path $BackendDirectory ".venv"
    $venvCandidates = @(
        (Join-Path $venvDirectory "Scripts/python.exe"),
        (Join-Path $venvDirectory "bin/python")
    )
    foreach ($candidate in $venvCandidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return [PSCustomObject]@{
                Invocation = (Resolve-Path -LiteralPath $candidate).Path
                Source = "backend virtual environment"
            }
        }
    }

    try {
        $normalPython = Get-Command python -CommandType Application -ErrorAction Stop | Select-Object -First 1
    }
    catch {
        throw "No Python interpreter was found. Create the backend virtual environment or pass -Python explicitly."
    }
    return [PSCustomObject]@{
        Invocation = $normalPython.Source
        Source = "normal python command"
    }
}

function Assert-CoreBackendPythonEnvironment {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Interpreter,
        [Parameter(Mandatory = $true)]
        [string]$Source,
        [Parameter(Mandatory = $true)]
        [string]$EnvironmentDoctor
    )

    try {
        & $Interpreter $EnvironmentDoctor "--core-backend-probe"
    }
    catch {
        throw "Selected Python environment is not suitable for the WalkBuddy Candidate backend. Selected source: $Source. Selected interpreter: $Interpreter. Reason: it could not run the core backend package probe. Use the backend virtual environment or pass -Python explicitly."
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Selected Python environment is not suitable for the WalkBuddy Candidate backend. Selected source: $Source. Selected interpreter: $Interpreter. Reason: the core backend package probe did not pass. Use the backend virtual environment or pass -Python explicitly."
    }
}

function Start-CandidateBackend {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [ValidateNotNullOrEmpty()]
        [string]$ModelPath,
        [Parameter(Mandatory = $true)]
        [ValidateNotNullOrEmpty()]
        [string]$ManifestPath,
        [string]$Python,
        [string]$BackendDirectory = "software_side/walkbuddy_reactNative/backend",
        [Alias("Host")]
        [string]$BindHost = "0.0.0.0",
        [ValidateRange(1, 65535)]
        [int]$Port = 8000,
        [string]$AllowedOrigins,
        [switch]$RequireCuda,
        [switch]$Execute
    )

    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../../..")).Path
    $model = (Resolve-Path -LiteralPath $ModelPath).Path
    $manifest = (Resolve-Path -LiteralPath $ManifestPath).Path
    $backend = (Resolve-Path -LiteralPath (Join-Path $repoRoot $BackendDirectory)).Path
    $readinessTool = Join-Path $repoRoot "ML_side/deployment/tools/check_candidate_readiness.py"
    $environmentDoctor = Join-Path $repoRoot "ML_side/deployment/tools/environment_doctor.py"
    $pythonSelection = Resolve-BackendPythonInterpreter `
        -BackendDirectory $backend `
        -ExplicitPython $Python `
        -ExplicitPythonSupplied:$($PSBoundParameters.ContainsKey("Python"))

    if ((Split-Path -Leaf $model) -ne "best.pt") {
        throw "Candidate model must be named best.pt because the backend appends best.pt to WALKBUDDY_MODEL_DIR."
    }

    Write-Host "Candidate backend launch preparation (read-only validation)"
    Write-Host "Model: $model"
    Write-Host "Model SHA is checked by deployment readiness; no artifact is copied or modified."
    Write-Host "Python interpreter source: $($pythonSelection.Source)"
    Write-Host "Python interpreter: $($pythonSelection.Invocation)"
    Assert-CoreBackendPythonEnvironment `
        -Interpreter $pythonSelection.Invocation `
        -Source $pythonSelection.Source `
        -EnvironmentDoctor $environmentDoctor

    $preflightArguments = @($readinessTool, "--manifest", $manifest, "--model", $model)
    if ($RequireCuda) { $preflightArguments += "--require-cuda" }
    & $pythonSelection.Invocation @preflightArguments
    if ($LASTEXITCODE -ne 0) { throw "Deployment readiness failed; backend was not started." }

    $env:WALKBUDDY_MODEL_DIR = Split-Path -Parent $model
    $env:WALKBUDDY_ML_MOCK = "0"
    $manifestData = Get-Content -Raw -LiteralPath $manifest | ConvertFrom-Json
    $env:WALKBUDDY_EXPECTED_MODEL_SHA256 = [string]$manifestData.expected_sha256
    if ($AllowedOrigins) { $env:WALKBUDDY_ALLOWED_ORIGINS = $AllowedOrigins }

    $uvicornArguments = @("-m", "uvicorn", "main:app", "--host", $BindHost, "--port", "$Port")
    Write-Host "Candidate model directory: $env:WALKBUDDY_MODEL_DIR"
    Write-Host "ML mock mode: $env:WALKBUDDY_ML_MOCK"
    Write-Host "Expected model SHA is bound from the validated deployment manifest."
    Write-Host "Backend command preview: $($pythonSelection.Invocation) $($uvicornArguments -join ' ')"
    if (-not $Execute) {
        Write-Host "Dry run complete. Add -Execute to launch after reviewing the command."
        return
    }

    Push-Location $backend
    try {
        & $pythonSelection.Invocation @uvicornArguments
    }
    finally {
        Pop-Location
    }
}

if ($MyInvocation.InvocationName -ne ".") {
    Start-CandidateBackend @PSBoundParameters
}
