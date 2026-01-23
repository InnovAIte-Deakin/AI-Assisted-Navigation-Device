# Ollama Installation Guide - Sprint 2

## Overview
Ollama enables offline LLM operation for the navigation system, eliminating API costs and internet dependency.

---

## Installation Steps

### Step 1: Install Ollama (Linux/WSL)

Run this command in your terminal:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Note**: You'll need to enter your sudo password.

**Alternative Windows Installation**:
If on Windows (not WSL), download from: https://ollama.com/download

---

### Step 2: Verify Installation

```bash
ollama --version
```

Expected output: `ollama version 0.x.x`

---

### Step 3: Pull Required Models

We'll use multiple models for different scenarios:

#### Primary Model (Recommended - Fast & Efficient)
```bash
ollama pull llama3.2:3b
```
- Size: ~2GB
- RAM Required: 4GB
- Speed: ~200-500ms per query
- Best for: Real-time navigation guidance

#### Secondary Model (Better Reasoning)
```bash
ollama pull mistral:7b
```
- Size: ~4GB
- RAM Required: 8GB
- Speed: ~500-1000ms per query
- Best for: Complex navigation scenarios

#### Emergency Fallback (Lightest)
```bash
ollama pull llama3.2:1b
```
- Size: ~700MB
- RAM Required: 2GB
- Speed: ~100-300ms per query
- Best for: Low-resource devices

---

### Step 4: Test Ollama

```bash
ollama run llama3.2:3b "Navigate around a table in front of me in a library"
```

Expected: Natural language navigation guidance response

---

### Step 5: Start Ollama Service

For automatic startup:

```bash
ollama serve &
```

**Or** for persistent service:

```bash
# Add to ~/.bashrc or ~/.zshrc
echo 'ollama serve &' >> ~/.bashrc
```

---

## Verification Checklist

- [ ] Ollama installed (`ollama --version` works)
- [ ] llama3.2:3b model downloaded
- [ ] Test query responds successfully
- [ ] Ollama service running on localhost:11434

---

## Testing Integration with Navigation System

After installation, test the integration:

```bash
cd ML_side
python -c "
from src.llm_integration.llm_reasoning_engine import LLMNavigationReasoner

# Initialize with Ollama
reasoner = LLMNavigationReasoner(model_type='ollama', model_name='llama3.2:3b')

# Test navigation reasoning
detections = [
    {'class_name': 'table', 'confidence': 0.85, 'bbox': {'center_x': 320, 'center_y': 240}},
    {'class_name': 'chair', 'confidence': 0.78, 'bbox': {'center_x': 400, 'center_y': 280}}
]

spatial_context = {'obstacle_count': 2, 'scene_density': 'moderate'}

result = reasoner.reason_about_navigation(
    detections,
    spatial_context,
    'Navigate safely',
    'Library'
)

print('Navigation Guidance:', result['direction'])
print('Safety Level:', result['safety_level'])
"
```

---

## Troubleshooting

### Issue: "Cannot connect to Ollama"
**Solution**: Make sure Ollama service is running:
```bash
ollama serve &
```

### Issue: "Model not found"
**Solution**: Download the model:
```bash
ollama pull llama3.2:3b
```

### Issue: "Out of memory"
**Solution**:
- Use smaller model: `ollama pull llama3.2:1b`
- Or close other applications
- Verify RAM: `free -h`

### Issue: "Slow responses (>1s)"
**Solutions**:
- Switch to faster model: llama3.2:3b or llama3.2:1b
- Check CPU/GPU usage: `htop`
- Reduce `num_predict` in llm_config.yaml (currently 200)

---

## Performance Benchmarks

| Model | Size | RAM | Speed | Quality |
|-------|------|-----|-------|---------|
| llama3.2:1b | 700MB | 2GB | ~100-300ms | Good |
| llama3.2:3b | 2GB | 4GB | ~200-500ms | Better |
| mistral:7b | 4GB | 8GB | ~500-1000ms | Best |

**Recommendation**: Start with **llama3.2:3b** for best balance of speed and quality.

---

## Configuration

Ollama settings are in: `/ML_side/config/llm_config.yaml`

Key settings:
- `primary_model`: Main model to use
- `timeout`: Max wait time (default: 10s)
- `temperature`: 0.3 (deterministic, safe for navigation)

---

## Next Steps

After Ollama is installed and tested:

1. Update `llm_config.yaml` if needed
2. Run Sprint 2 tests: `python run_sprint2_tests.py`
3. Test hybrid mode (Ollama → OpenAI fallback)
4. Benchmark performance on your hardware

---

## Additional Resources

- Ollama Documentation: https://ollama.com/docs
- Model Library: https://ollama.com/library
- GitHub: https://github.com/ollama/ollama
