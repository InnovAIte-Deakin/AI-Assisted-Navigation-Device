"""
Quick Ollama Integration Demo
Run this to see Ollama working with navigation scenarios
"""

import requests
import json
import time

def test_ollama_connection():
    """Test if Ollama is running"""
    print("=" * 60)
    print("OLLAMA INTEGRATION TEST - Sprint 2")
    print("=" * 60)
    print()

    print("Step 1: Testing Ollama connection...")
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama service is running!")
            models = response.json().get('models', [])
            print(f"✅ Found {len(models)} installed models:")
            for model in models:
                print(f"   - {model['name']} ({model['size'] / 1e9:.1f} GB)")
        else:
            print("❌ Ollama is not responding correctly")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to Ollama: {e}")
        print("   Make sure Ollama is running: ollama serve &")
        return False

    print()
    return True

def query_ollama(prompt, model="llama3.2:3b"):
    """Send a query to Ollama"""
    url = "http://localhost:11434/api/generate"

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 200
        }
    }

    print(f"Querying {model}...")
    start_time = time.time()

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()

        elapsed = time.time() - start_time
        result = response.json()

        return {
            'response': result.get('response', ''),
            'elapsed': elapsed,
            'model': model
        }
    except Exception as e:
        return {
            'error': str(e),
            'elapsed': time.time() - start_time
        }

def test_navigation_scenarios():
    """Test multiple navigation scenarios"""
    print("Step 2: Testing navigation scenarios...")
    print()

    scenarios = [
        {
            'name': 'Scenario 1: Table in Center',
            'prompt': 'You are a navigation assistant for visually impaired users in a library. A table is detected in the center of the path blocking straight movement. Provide clear, concise guidance in one sentence on how to navigate around it.'
        },
        {
            'name': 'Scenario 2: Chair on Left',
            'prompt': 'You are a navigation assistant. A chair is detected on the left side of the path. Guide the user safely in one sentence.'
        },
        {
            'name': 'Scenario 3: Stairs Ahead',
            'prompt': 'You are a navigation assistant. Stairs are detected straight ahead. The user needs to go upstairs. Provide guidance in one sentence.'
        }
    ]

    for i, scenario in enumerate(scenarios, 1):
        print(f"{scenario['name']}")
        print("-" * 60)

        result = query_ollama(scenario['prompt'])

        if 'error' in result:
            print(f"❌ Error: {result['error']}")
        else:
            print(f"✅ Response ({result['elapsed']:.2f}s):")
            print(f"   {result['response']}")

        print()

def test_model_comparison():
    """Compare different models"""
    print("Step 3: Comparing model speeds...")
    print()

    test_prompt = "You are a navigation assistant. A book is on a table to your right. Guide the user in one sentence."

    models = ["llama3.2:1b", "llama3.2:3b"]

    for model in models:
        print(f"Testing {model}...")
        result = query_ollama(test_prompt, model=model)

        if 'error' in result:
            print(f"   ❌ Not available: {result['error']}")
        else:
            print(f"   ✅ Response time: {result['elapsed']:.2f}s")
            print(f"   Response: {result['response'][:100]}...")
        print()

def main():
    """Run all tests"""
    # Test connection
    if not test_ollama_connection():
        return

    # Test navigation scenarios
    test_navigation_scenarios()

    # Compare models
    test_model_comparison()

    print("=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Train 15-class YOLO model with your dataset")
    print("  2. Update llm_reasoning_engine.py for hybrid mode")
    print("  3. Run full integration tests")
    print()
    print("Configuration files:")
    print("  - config/llm_config.yaml")
    print("  - config/system_config.yaml")
    print("  - config/data_config.yaml")
    print()

if __name__ == "__main__":
    main()
