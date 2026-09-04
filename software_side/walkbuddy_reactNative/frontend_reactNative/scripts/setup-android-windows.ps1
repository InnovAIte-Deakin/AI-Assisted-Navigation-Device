$ErrorActionPreference = "Stop"

# ==================================================
# CONFIGURATION
# ==================================================

$SourceRoot =
    (Resolve-Path "$PSScriptRoot\..").Path

$BuildRoot =
    Join-Path $env:USERPROFILE "WB-Native"


Write-Host ""
Write-Host "============================================"
Write-Host " WalkBuddy Android Development Setup"
Write-Host "============================================"
Write-Host ""

Write-Host "Repository frontend:"
Write-Host $SourceRoot

Write-Host ""
Write-Host "Short native build path:"
Write-Host $BuildRoot
Write-Host ""


# ==================================================
# REQUIREMENTS
# ==================================================

if (
    -not (
        Get-Command node -ErrorAction SilentlyContinue
    )
) {
    throw "Node.js is not installed or not available in PATH."
}

if (
    -not (
        Get-Command npm -ErrorAction SilentlyContinue
    )
) {
    throw "npm is not installed or not available in PATH."
}

Write-Host "Node:"
node --version

Write-Host "npm:"
npm --version


# ==================================================
# PREPARE SHORT BUILD DIRECTORY
# ==================================================

Write-Host ""
Write-Host "============================================"
Write-Host " Preparing short build directory"
Write-Host "============================================"
Write-Host ""

if (-not (Test-Path $BuildRoot)) {
    Write-Host "Creating native build directory..."

    New-Item `
        -ItemType Directory `
        -Path $BuildRoot `
        -Force `
        | Out-Null
}
else {
    Write-Host "Reusing existing native build directory:"
    Write-Host $BuildRoot
}

# ==================================================
# SYNC FRONTEND SOURCE
# ==================================================

Write-Host ""
Write-Host "Syncing WalkBuddy frontend changes..."

robocopy `
    "$SourceRoot" `
    "$BuildRoot" `
    /E `
    /XO `
    /XD `
        node_modules `
        android `
        .expo `
        .gradle `
        .cxx `
        build `
    /XF `
        *.log `
    /NFL `
    /NDL `
    /NJH `
    /NJS `
    /NP

$RobocopyExitCode = $LASTEXITCODE

if ($RobocopyExitCode -ge 8) {
    throw "Failed to sync project. Robocopy exit code: $RobocopyExitCode"
}

# ==================================================
# ENTER SHORT PHYSICAL PATH
# ==================================================

Set-Location $BuildRoot

Write-Host ""
Write-Host "Working from:"
Write-Host (Get-Location)


# ==================================================
# INSTALL DEPENDENCIES
# ==================================================

Write-Host ""
Write-Host "============================================"
Write-Host " Installing dependencies"
Write-Host "============================================"
Write-Host ""

npm install

if (
    $LASTEXITCODE -ne 0
) {
    throw "npm install failed."
}


# ==================================================
# AGORA
# ==================================================

Write-Host ""
Write-Host "Checking react-native-agora..."

npm list react-native-agora --depth=0 *> $null

if (
    $LASTEXITCODE -ne 0
) {
    Write-Host "Installing react-native-agora..."

    npm install react-native-agora

    if (
        $LASTEXITCODE -ne 0
    ) {
        throw "react-native-agora installation failed."
    }
}
else {
    Write-Host "react-native-agora already installed."
}


# ==================================================
# EXPO DEV CLIENT
# ==================================================

Write-Host ""
Write-Host "Checking expo-dev-client..."

npm list expo-dev-client --depth=0 *> $null

if (
    $LASTEXITCODE -ne 0
) {
    Write-Host "Installing expo-dev-client..."

    npx expo install expo-dev-client

    if (
        $LASTEXITCODE -ne 0
    ) {
        throw "expo-dev-client installation failed."
    }
}
else {
    Write-Host "expo-dev-client already installed."
}


# ==================================================
# PREBUILD
# ==================================================

Write-Host ""
Write-Host "============================================"
Write-Host " Running Expo prebuild"
Write-Host "============================================"
Write-Host ""

npx expo prebuild

if (
    $LASTEXITCODE -ne 0
) {
    throw "Expo prebuild failed."
}


# ==================================================
# ANDROID BUILD
# ==================================================

Write-Host ""
Write-Host "============================================"
Write-Host " Building Android development client"
Write-Host "============================================"
Write-Host ""

npx expo run:android

if (
    $LASTEXITCODE -ne 0
) {
    throw "Android development build failed."
}


# ==================================================
# COMPLETE
# ==================================================

Write-Host ""
Write-Host "============================================"
Write-Host " WalkBuddy Android setup completed"
Write-Host "============================================"
Write-Host ""

Write-Host "Native build directory:"
Write-Host $BuildRoot

Write-Host ""
Write-Host "Your original GitHub working copy was not modified."
Write-Host ""