#!/usr/bin/env bash

set -euo pipefail

# ==================================================
# WalkBuddy iOS Development Setup
#
# Designed for fresh Apple Silicon macOS machines
# without requiring Homebrew or sudo.
#
# Tested discovery environment:
#   macOS 26.x
#   Xcode 27.x
#   Apple Silicon (arm64)
# ==================================================

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

NVM_VERSION="v0.40.3"
NODE_VERSION="22"

OPENSSL_VERSION="3.3.2"
M4_VERSION="1.4.20"
AUTOCONF_VERSION="2.72"
LIBYAML_VERSION="0.2.5"

COCOAPODS_VERSION="1.17.0"

# Ruby 3.3 branch commit confirmed working during
# WalkBuddy macOS 26 / Xcode 27 testing.
RUBY_REPOSITORY="https://github.com/ruby/ruby.git"
RUBY_BRANCH="ruby_3_3"
RUBY_COMMIT="0c8ab2a"
RUBY_PREFIX="$HOME/.rubies/ruby-3.3-walkbuddy"

LOCAL_PREFIX="$HOME/.local"
OPENSSL_PREFIX="$LOCAL_PREFIX/openssl"

LOGIN_KEYCHAIN="$HOME/Library/Keychains/login.keychain-db"

TEMP_ROOT="${TMPDIR:-/tmp}/walkbuddy-ios-setup"

# --------------------------------------------------
# OUTPUT HELPERS
# --------------------------------------------------

section() {
    echo ""
    echo "============================================"
    echo " $1"
    echo "============================================"
    echo ""
}

info() {
    echo "[INFO] $1"
}

ok() {
    echo "[OK] $1"
}

warn() {
    echo "[WARNING] $1"
}

fail() {
    echo ""
    echo "[ERROR] $1"
    echo ""
    exit 1
}

# --------------------------------------------------
# START
# --------------------------------------------------

section "WalkBuddy iOS Development Setup"

echo "Repository frontend:"
echo "$SOURCE_ROOT"

# --------------------------------------------------
# macOS CHECK
# --------------------------------------------------

section "Checking macOS"

if [[ "$(uname -s)" != "Darwin" ]]; then
    fail "This setup script requires macOS."
fi

MACOS_VERSION="$(sw_vers -productVersion)"
ARCH="$(uname -m)"

echo "macOS: $MACOS_VERSION"
echo "Architecture: $ARCH"

if [[ "$ARCH" != "arm64" ]]; then
    warn "This script was tested on Apple Silicon (arm64)."
    warn "Current architecture is: $ARCH"
fi

# --------------------------------------------------
# XCODE
# --------------------------------------------------

section "Checking Xcode"

if ! command -v xcodebuild >/dev/null 2>&1; then
    fail "Xcode command-line tools are unavailable. Install/open Xcode first."
fi

XCODE_PATH="$(xcode-select -p 2>/dev/null || true)"

if [[ "$XCODE_PATH" != *"Xcode.app"* ]]; then
    warn "Active developer directory does not appear to be full Xcode:"
    echo "$XCODE_PATH"
    echo ""
    echo "If Xcode is installed in /Applications, run:"
    echo ""
    echo "  sudo xcode-select -s /Applications/Xcode.app/Contents/Developer"
    echo ""
    fail "Full Xcode must be selected before continuing."
fi

xcodebuild -version

ok "Xcode is available."

# --------------------------------------------------
# BASIC TOOLS
# --------------------------------------------------

section "Checking Development Tools"

for tool in curl git make clang perl; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        fail "Required development tool '$tool' was not found."
    fi

    echo "$tool: OK"
done

# --------------------------------------------------
# LOCAL DIRECTORIES
# --------------------------------------------------

mkdir -p "$LOCAL_PREFIX/bin"
mkdir -p "$HOME/.rubies"
mkdir -p "$TEMP_ROOT"

export PATH="$LOCAL_PREFIX/bin:$PATH"

# --------------------------------------------------
# NVM / NODE
# --------------------------------------------------

section "Checking Node.js"

export NVM_DIR="$HOME/.nvm"

if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
    info "NVM was not found."
    info "Installing NVM $NVM_VERSION..."

    curl -fsSL \
        "https://raw.githubusercontent.com/nvm-sh/nvm/${NVM_VERSION}/install.sh" \
        | bash
fi

if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
    fail "NVM installation failed."
fi

# shellcheck disable=SC1090
source "$NVM_DIR/nvm.sh"

if ! nvm version "$NODE_VERSION" >/dev/null 2>&1; then
    info "Installing Node.js $NODE_VERSION..."
    nvm install "$NODE_VERSION"
fi

nvm use "$NODE_VERSION"

if ! command -v node >/dev/null 2>&1; then
    fail "Node.js is unavailable after loading NVM."
fi

if ! command -v npm >/dev/null 2>&1; then
    fail "npm is unavailable."
fi

if ! command -v npx >/dev/null 2>&1; then
    fail "npx is unavailable."
fi

echo "Node: $(node --version)"
echo "npm:  $(npm --version)"
echo "npx:  $(npx --version)"

# --------------------------------------------------
# PERSIST NVM
# --------------------------------------------------

section "Configuring Shell Environment"

NVM_PROFILE_BLOCK='
# WalkBuddy / NVM
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
'

LOCAL_PROFILE_BLOCK='
# WalkBuddy local development tools
export PATH="$HOME/.local/bin:$PATH"
export PATH="$HOME/.rubies/ruby-3.3-walkbuddy/bin:$PATH"
'

configure_profile() {
    local profile="$1"

    touch "$profile"

    if ! grep -Fq '# WalkBuddy / NVM' "$profile"; then
        printf "%s\n" "$NVM_PROFILE_BLOCK" >> "$profile"
        info "Added NVM configuration to $profile"
    else
        ok "NVM already configured in $profile"
    fi

    if ! grep -Fq '# WalkBuddy local development tools' "$profile"; then
        printf "%s\n" "$LOCAL_PROFILE_BLOCK" >> "$profile"
        info "Added WalkBuddy PATH configuration to $profile"
    else
        ok "WalkBuddy PATH already configured in $profile"
    fi
}

# Configure both common shells because managed Macs may launch
# bash even when the account's default shell is zsh.
configure_profile "$HOME/.zshrc"
configure_profile "$HOME/.bash_profile"

# --------------------------------------------------
# OPENSSL
# --------------------------------------------------

section "Checking OpenSSL"

OPENSSL_OK=false

if [[ -x "$OPENSSL_PREFIX/bin/openssl" ]]; then
    if "$OPENSSL_PREFIX/bin/openssl" version \
        | grep -q "OpenSSL $OPENSSL_VERSION"; then
        OPENSSL_OK=true
    fi
fi

if [[ "$OPENSSL_OK" == false ]]; then
    info "Building OpenSSL $OPENSSL_VERSION locally..."

    cd "$TEMP_ROOT"

    rm -rf "openssl-$OPENSSL_VERSION"
    rm -f "openssl-$OPENSSL_VERSION.tar.gz"

    curl -fLO \
        "https://www.openssl.org/source/openssl-${OPENSSL_VERSION}.tar.gz"

    tar -xzf "openssl-${OPENSSL_VERSION}.tar.gz"

    cd "openssl-${OPENSSL_VERSION}"

    ./Configure darwin64-arm64-cc \
        --prefix="$OPENSSL_PREFIX" \
        --openssldir="$OPENSSL_PREFIX"

    make -j"$(sysctl -n hw.logicalcpu)"
    make install_sw

    ok "OpenSSL installed."
else
    ok "OpenSSL $OPENSSL_VERSION already installed."
fi

export PATH="$OPENSSL_PREFIX/bin:$PATH"

"$OPENSSL_PREFIX/bin/openssl" version

# --------------------------------------------------
# CERTIFICATE AUTHORITY BUNDLE
# --------------------------------------------------

section "Configuring TLS Certificates"

SYSTEM_CA=""

for candidate in \
    "/etc/ssl/cert.pem" \
    "/private/etc/ssl/cert.pem"
do
    if [[ -f "$candidate" ]]; then
        SYSTEM_CA="$candidate"
        break
    fi
done

if [[ -z "$SYSTEM_CA" ]]; then
    fail "Could not locate the macOS CA certificate bundle."
fi

if [[ ! -s "$OPENSSL_PREFIX/cert.pem" ]]; then
    info "Installing CA bundle for local OpenSSL..."

    cp "$SYSTEM_CA" "$OPENSSL_PREFIX/cert.pem"
fi

if [[ ! -s "$OPENSSL_PREFIX/cert.pem" ]]; then
    fail "OpenSSL CA bundle could not be configured."
fi

export SSL_CERT_FILE="$OPENSSL_PREFIX/cert.pem"

ok "TLS CA bundle configured."

# --------------------------------------------------
# GNU M4
# --------------------------------------------------

section "Checking GNU M4"

M4_OK=false

if [[ -x "$LOCAL_PREFIX/bin/m4" ]]; then
    if "$LOCAL_PREFIX/bin/m4" --version 2>/dev/null \
        | grep -q "$M4_VERSION"; then
        M4_OK=true
    fi
fi

if [[ "$M4_OK" == false ]]; then
    info "Building GNU M4 $M4_VERSION..."

    cd "$TEMP_ROOT"

    rm -rf "m4-$M4_VERSION"
    rm -f "m4-$M4_VERSION.tar.gz"

    curl -fLO \
        "https://ftp.gnu.org/gnu/m4/m4-${M4_VERSION}.tar.gz"

    tar -xzf "m4-${M4_VERSION}.tar.gz"

    cd "m4-${M4_VERSION}"

    ./configure --prefix="$LOCAL_PREFIX"

    make -j"$(sysctl -n hw.logicalcpu)"
    make install

    ok "GNU M4 installed."
else
    ok "GNU M4 already installed."
fi

export PATH="$LOCAL_PREFIX/bin:$PATH"

# --------------------------------------------------
# AUTOCONF
# --------------------------------------------------

section "Checking Autoconf"

AUTOCONF_OK=false

if [[ -x "$LOCAL_PREFIX/bin/autoconf" ]]; then
    if "$LOCAL_PREFIX/bin/autoconf" --version 2>/dev/null \
        | head -n 1 \
        | grep -q "$AUTOCONF_VERSION"; then
        AUTOCONF_OK=true
    fi
fi

if [[ "$AUTOCONF_OK" == false ]]; then
    info "Building Autoconf $AUTOCONF_VERSION..."

    cd "$TEMP_ROOT"

    rm -rf "autoconf-$AUTOCONF_VERSION"
    rm -f "autoconf-$AUTOCONF_VERSION.tar.gz"

    curl -fLO \
        "https://ftp.gnu.org/gnu/autoconf/autoconf-${AUTOCONF_VERSION}.tar.gz"

    tar -xzf "autoconf-${AUTOCONF_VERSION}.tar.gz"

    cd "autoconf-${AUTOCONF_VERSION}"

    ./configure --prefix="$LOCAL_PREFIX"

    make
    make install

    ok "Autoconf installed."
else
    ok "Autoconf already installed."
fi

# --------------------------------------------------
# LIBYAML
# --------------------------------------------------

section "Checking libyaml"

LIBYAML_OK=false

if [[ -f "$LOCAL_PREFIX/include/yaml.h" ]] && \
   [[ -f "$LOCAL_PREFIX/lib/libyaml.dylib" ]]; then
    LIBYAML_OK=true
fi

if [[ "$LIBYAML_OK" == false ]]; then
    info "Building libyaml $LIBYAML_VERSION..."

    cd "$TEMP_ROOT"

    rm -rf "yaml-$LIBYAML_VERSION"
    rm -f "yaml-$LIBYAML_VERSION.tar.gz"

    curl -fL \
        "https://github.com/yaml/libyaml/releases/download/${LIBYAML_VERSION}/yaml-${LIBYAML_VERSION}.tar.gz" \
        -o "yaml-${LIBYAML_VERSION}.tar.gz"

    tar -xzf "yaml-${LIBYAML_VERSION}.tar.gz"

    cd "yaml-${LIBYAML_VERSION}"

    ./configure --prefix="$LOCAL_PREFIX"

    make -j"$(sysctl -n hw.logicalcpu)"
    make install

    ok "libyaml installed."
else
    ok "libyaml already installed."
fi

# --------------------------------------------------
# RUBY
# --------------------------------------------------

section "Checking Ruby"

RUBY_OK=false

if [[ -x "$RUBY_PREFIX/bin/ruby" ]]; then
    if "$RUBY_PREFIX/bin/ruby" -ropenssl -rpsych -e '
        exit 1 unless OpenSSL::OPENSSL_VERSION.include?("3.3.2")
        exit 1 unless defined?(Psych)
    ' >/dev/null 2>&1; then
        RUBY_OK=true
    fi
fi

if [[ "$RUBY_OK" == false ]]; then
    info "Building WalkBuddy-compatible Ruby..."
    info "Pinned Ruby commit: $RUBY_COMMIT"

    RUBY_SOURCE="$TEMP_ROOT/ruby-walkbuddy"

    rm -rf "$RUBY_SOURCE"

    git clone \
        --branch "$RUBY_BRANCH" \
        "$RUBY_REPOSITORY" \
        "$RUBY_SOURCE"

    cd "$RUBY_SOURCE"

    git checkout "$RUBY_COMMIT"

    info "Ruby source commit:"
    git log -1 --oneline

    ./autogen.sh

    export CPPFLAGS="-I$LOCAL_PREFIX/include"
    export LDFLAGS="-L$LOCAL_PREFIX/lib"
    export PKG_CONFIG_PATH="$LOCAL_PREFIX/lib/pkgconfig"

    ./configure \
        --prefix="$RUBY_PREFIX" \
        --with-openssl-dir="$OPENSSL_PREFIX" \
        --disable-install-doc

    make -j"$(sysctl -n hw.logicalcpu)"
    make install

    ok "Ruby installed."
else
    ok "WalkBuddy Ruby already installed."
fi

export PATH="$RUBY_PREFIX/bin:$LOCAL_PREFIX/bin:$OPENSSL_PREFIX/bin:$PATH"

echo ""
ruby --version
ruby -ropenssl -e 'puts "OpenSSL: #{OpenSSL::OPENSSL_VERSION}"'
ruby -rpsych -e 'puts "Psych: #{Psych::VERSION}"'

# --------------------------------------------------
# COCOAPODS
# --------------------------------------------------

section "Checking CocoaPods"

PODS_OK=false

if command -v pod >/dev/null 2>&1; then
    if pod --version 2>/dev/null | grep -q "^${COCOAPODS_VERSION}$"; then
        PODS_OK=true
    fi
fi

if [[ "$PODS_OK" == false ]]; then
    info "Installing CocoaPods $COCOAPODS_VERSION..."

    gem install cocoapods -v "$COCOAPODS_VERSION" --no-document

    ok "CocoaPods installed."
else
    ok "CocoaPods $COCOAPODS_VERSION already installed."
fi

echo "CocoaPods: $(pod --version)"

# --------------------------------------------------
# RETURN TO PROJECT
# --------------------------------------------------

cd "$SOURCE_ROOT"

# --------------------------------------------------
# FRONTEND DEPENDENCIES
# --------------------------------------------------

section "Installing WalkBuddy Dependencies"

if [[ ! -f "$SOURCE_ROOT/package.json" ]]; then
    fail "package.json was not found in $SOURCE_ROOT"
fi

npm install

ok "Frontend dependencies installed."

# --------------------------------------------------
# VERIFY REQUIRED NATIVE PACKAGES
# --------------------------------------------------

section "Checking WalkBuddy Native Packages"

if ! npm list react-native-agora --depth=0 >/dev/null 2>&1; then
    fail "react-native-agora is not installed in the frontend project."
fi

if ! npm list expo-dev-client --depth=0 >/dev/null 2>&1; then
    fail "expo-dev-client is not installed in the frontend project."
fi

echo "react-native-agora:"
npm list react-native-agora --depth=0 || true

echo ""
echo "expo-dev-client:"
npm list expo-dev-client --depth=0 || true

# --------------------------------------------------
# AGORA SESSION SERVER
# --------------------------------------------------

section "Checking Agora Session Server"

SESSION_SERVER="$SOURCE_ROOT/agora_session_server"

if [[ ! -d "$SESSION_SERVER" ]]; then
    fail "Agora session server directory was not found."
fi

if [[ ! -f "$SESSION_SERVER/package.json" ]]; then
    fail "Agora session server package.json was not found."
fi

(
    cd "$SESSION_SERVER"
    npm install
)

ok "Agora session server dependencies installed."

# --------------------------------------------------
# ENV CHECK
# --------------------------------------------------

if [[ ! -f "$SESSION_SERVER/.env" ]]; then
    echo ""
    warn "agora_session_server/.env was not found."
    warn "The native iOS build can still be created."
    warn "Agora calls will not work until the local .env is configured."
    echo ""
    echo "Do NOT commit Agora credentials to Git."
    echo ""
else
    ok "Agora session server .env exists."
fi

# --------------------------------------------------
# IOS PREBUILD
# --------------------------------------------------

section "Generating iOS Native Project"

cd "$SOURCE_ROOT"

if [[ ! -d "$SOURCE_ROOT/ios" ]]; then
    info "iOS native project does not exist."
    info "Running Expo prebuild..."

    npx expo prebuild --platform ios

    ok "iOS native project generated."
else
    ok "iOS native project already exists."
fi

# --------------------------------------------------
# POD INSTALL
# --------------------------------------------------

section "Installing iOS Pods"

if [[ ! -f "$SOURCE_ROOT/ios/Podfile" ]]; then
    fail "iOS Podfile was not generated."
fi

cd "$SOURCE_ROOT/ios"

pod install --repo-update

ok "iOS Pods installed."

cd "$SOURCE_ROOT"

# --------------------------------------------------
# SIGNING IDENTITY
# --------------------------------------------------

section "Checking Apple Code Signing"

IDENTITY_OUTPUT="$(security find-identity -v -p codesigning 2>/dev/null || true)"

echo "$IDENTITY_OUTPUT"

if echo "$IDENTITY_OUTPUT" | grep -q "0 valid identities found"; then

    echo ""
    echo "============================================"
    echo " Apple signing setup required"
    echo "============================================"
    echo ""
    echo "The software setup is complete, but macOS does"
    echo "not currently have an Apple Development signing"
    echo "identity."
    echo ""
    echo "Complete this one-time setup:"
    echo ""
    echo "1. Open the generated workspace:"
    echo ""
    echo "   open ios/*.xcworkspace"
    echo ""
    echo "2. In Xcode:"
    echo "   Xcode -> Settings -> Accounts"
    echo ""
    echo "3. Sign in with your Apple Account."
    echo ""
    echo "4. Select the frontendReactNative target."
    echo ""
    echo "5. Open Signing & Capabilities."
    echo ""
    echo "6. Enable:"
    echo "      Automatically manage signing"
    echo ""
    echo "7. Select your Development Team / Personal Team."
    echo ""
    echo "8. Allow Xcode to create an Apple Development"
    echo "   certificate if required."
    echo ""
    echo "Then rerun:"
    echo ""
    echo "   bash scripts/setup-ios-macos.sh"
    echo ""

    exit 2
fi

SIGNING_HASH="$(
    echo "$IDENTITY_OUTPUT" \
        | sed -n 's/^[[:space:]]*[0-9]*) \([A-F0-9]\{40\}\) "Apple Development:.*$/\1/p' \
        | head -n 1
)"

if [[ -z "$SIGNING_HASH" ]]; then
    fail "A signing identity exists, but an Apple Development identity could not be selected."
fi

ok "Apple Development signing identity found."

# --------------------------------------------------
# CODESIGN PRIVATE KEY TEST
# --------------------------------------------------

section "Testing Code Signing Access"

SIGN_TEST="/tmp/WalkBuddySignTest.app"

rm -rf "$SIGN_TEST"

mkdir -p "$SIGN_TEST/Contents/MacOS"

cat > "$SIGN_TEST/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>WalkBuddySignTest</string>

    <key>CFBundleIdentifier</key>
    <string>com.walkbuddy.signtest</string>

    <key>CFBundleName</key>
    <string>WalkBuddySignTest</string>

    <key>CFBundlePackageType</key>
    <string>APPL</string>
</dict>
</plist>
EOF

printf '#!/bin/sh\nexit 0\n' \
    > "$SIGN_TEST/Contents/MacOS/WalkBuddySignTest"

chmod +x "$SIGN_TEST/Contents/MacOS/WalkBuddySignTest"

if codesign \
    --force \
    --sign "$SIGNING_HASH" \
    "$SIGN_TEST"
then

    codesign --verify --verbose=2 "$SIGN_TEST"

    ok "Code signing private-key access works."

else

    echo ""
    echo "============================================"
    echo " Keychain permission required"
    echo "============================================"
    echo ""
    echo "The Apple Development certificate exists, but"
    echo "codesign could not use its private key."
    echo ""
    echo "Run this command:"
    echo ""
    echo "security set-key-partition-list \\"
    echo "  -S apple-tool:,apple:,codesign: \\"
    echo "  -s \\"
    echo "  \"$LOGIN_KEYCHAIN\""
    echo ""
    echo "macOS will request your login Keychain password."
    echo ""
    echo "IMPORTANT:"
    echo "Do not paste or store your password in this script."
    echo ""
    echo "After the command completes, rerun:"
    echo ""
    echo "  bash scripts/setup-ios-macos.sh"
    echo ""

    exit 3
fi

rm -rf "$SIGN_TEST"

# --------------------------------------------------
# READY FOR NATIVE BUILD
# --------------------------------------------------

section "WalkBuddy iOS Environment Ready"

echo "macOS:      $MACOS_VERSION"
echo "Architecture: $ARCH"
echo "Node:       $(node --version)"
echo "npm:        $(npm --version)"
echo "Ruby:       $(ruby --version)"
echo "CocoaPods:  $(pod --version)"
echo ""
echo "Apple signing: READY"
echo "Code signing:  READY"
echo ""

# --------------------------------------------------
# PHYSICAL DEVICE BUILD
# --------------------------------------------------

echo "The environment is ready to build WalkBuddy."
echo ""
echo "Connect and unlock the iPhone."
echo ""
echo "Starting Expo iOS device build..."
echo ""
