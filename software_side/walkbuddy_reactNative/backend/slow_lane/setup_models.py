import os
import requests
from tqdm import tqdm
from pathlib import Path

# --- CONFIGURATION ---
# 1. Get the directory where THIS script is living (backend/slow_lane)
CURRENT_SCRIPT_DIR = Path(__file__).resolve().parent

# 2. Calculate Project Root
#    Level 1 up: backend/
#    Level 2 up: walkbuddy_reactNative/ (Project Root)
PROJECT_ROOT = CURRENT_SCRIPT_DIR.parents[3] 

# 3. Target Directory: ML_side/models
#    This places the LLM in the main models folder, near your object_detection folder.
MODEL_DIR = PROJECT_ROOT / "ML_side" / "models"
MODEL_FILENAME = "llama-3.2-1b-instruct-q4_k_m.gguf"
MODEL_PATH = MODEL_DIR / MODEL_FILENAME

# URL to download
MODEL_URL = "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf"

def download_file(url, filename):
    """Downloads a file with a progress bar."""
    response = requests.get(url, stream=True)
    total_size_in_bytes = int(response.headers.get('content-length', 0))
    block_size = 1024 # 1 Kibibyte
    progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)
    
    # Ensure the directory exists
    filename.parent.mkdir(parents=True, exist_ok=True)
    
    with open(filename, 'wb') as file:
        for data in response.iter_content(block_size):
            progress_bar.update(len(data))
            file.write(data)
    progress_bar.close()
    
    if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
        print("ERROR, something went wrong")
        return False
    return True

def main():
    print(f"📍 Script Location: {CURRENT_SCRIPT_DIR}")
    print(f"📂 Target Model Directory: {MODEL_DIR}")
    
    # Check if the folder exists (create if not)
    if not MODEL_DIR.exists():
        print(f"Creating directory: {MODEL_DIR}")
        MODEL_DIR.mkdir(parents=True, exist_ok=True)

    if MODEL_PATH.exists():
        print(f"✅ Model already exists at: {MODEL_PATH}")
        return

    print(f"⬇️ Downloading Llama 3.2 1B Instruct (GGUF)...")
    print(f"   URL: {MODEL_URL}")
    
    try:
        success = download_file(MODEL_URL, MODEL_PATH)
        if success:
            print("\n✅ Download complete! Model is ready for main.py.")
        else:
            print("\n❌ Download failed.")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()