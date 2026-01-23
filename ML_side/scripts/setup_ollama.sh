#!/bin/bash
# Ollama Setup Script for Sprint 2
# Run this after manually installing Ollama

set -e  # Exit on error

echo "🚀 Ollama Setup for AI Navigation System - Sprint 2"
echo "=================================================="

# Check if Ollama is installed
echo ""
echo "Step 1: Checking Ollama installation..."
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama is not installed!"
    echo ""
    echo "Please install Ollama first:"
    echo "  curl -fsSL https://ollama.com/install.sh | sh"
    echo ""
    echo "Or download from: https://ollama.com/download"
    exit 1
fi

echo "✅ Ollama is installed: $(ollama --version)"

# Check if Ollama service is running
echo ""
echo "Step 2: Checking Ollama service..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama service is not running"
    echo "Starting Ollama service..."
    ollama serve > /dev/null 2>&1 &
    sleep 3

    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "✅ Ollama service started successfully"
    else
        echo "❌ Failed to start Ollama service"
        echo "Please run manually: ollama serve &"
        exit 1
    fi
else
    echo "✅ Ollama service is running"
fi

# Download required models
echo ""
echo "Step 3: Downloading required models..."

echo ""
echo "  Downloading llama3.2:3b (primary model, ~2GB)..."
if ollama list | grep -q "llama3.2:3b"; then
    echo "  ✅ llama3.2:3b already downloaded"
else
    ollama pull llama3.2:3b
    echo "  ✅ llama3.2:3b downloaded successfully"
fi

echo ""
echo "  Downloading llama3.2:1b (fallback model, ~700MB)..."
if ollama list | grep -q "llama3.2:1b"; then
    echo "  ✅ llama3.2:1b already downloaded"
else
    ollama pull llama3.2:1b
    echo "  ✅ llama3.2:1b downloaded successfully"
fi

# Optional: Download mistral (larger, better reasoning)
echo ""
read -p "  Download mistral:7b (4GB, better reasoning)? [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if ollama list | grep -q "mistral:7b"; then
        echo "  ✅ mistral:7b already downloaded"
    else
        ollama pull mistral:7b
        echo "  ✅ mistral:7b downloaded successfully"
    fi
else
    echo "  ⏭️  Skipping mistral:7b (optional)"
fi

# Test Ollama with a simple query
echo ""
echo "Step 4: Testing Ollama integration..."
echo ""
echo "  Sending test query to llama3.2:3b..."
TEST_RESPONSE=$(ollama run llama3.2:3b "You are a navigation assistant. In one sentence, guide a user around a table blocking their path." --format json 2>/dev/null || echo "error")

if [ "$TEST_RESPONSE" != "error" ]; then
    echo "  ✅ Test query successful!"
    echo "  Response: ${TEST_RESPONSE:0:100}..."
else
    echo "  ⚠️  Test query had issues, but Ollama is installed"
fi

# List downloaded models
echo ""
echo "Step 5: Summary of installed models..."
ollama list

# Final instructions
echo ""
echo "=================================================="
echo "✅ Ollama Setup Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "  1. Test integration: python -m pytest tests/test_offline_llm.py"
echo "  2. Update llm_config.yaml if needed"
echo "  3. Run demo: python demo.py --llm-mode ollama"
echo ""
echo "Configuration file: config/llm_config.yaml"
echo ""
echo "Installed models:"
ollama list | tail -n +2 | awk '{print "  - " $1 " (" $2 ")"}'
echo ""
echo "For troubleshooting, see: docs/ollama_installation_guide.md"
echo ""
