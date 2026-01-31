import os
import requests
from tqdm import tqdm

# Configuration
MODEL_URL = "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf"
MODEL_DIR = "ML_side/models"
MODEL_FILENAME = "llama-3.2-1b-instruct-q4_k_m.gguf"
MODEL_PATH = os.path.join(MODEL_DIR, MODEL_FILENAME)

def download_file(url, filename):
    """Downloads a file with a progress bar."""
    response = requests.get(url, stream=True)
    total_size_in_bytes = int(response.headers.get('content-length', 0))
    block_size = 1024 # 1 Kibibyte
    progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)
    
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
    if not os.path.exists(MODEL_DIR):
        print(f"Creating directory: {MODEL_DIR}")
        os.makedirs(MODEL_DIR, exist_ok=True)

    if os.path.exists(MODEL_PATH):
        print(f"✅ Model already exists at: {MODEL_PATH}")
        return

    print(f"⬇️ Downloading Llama 3.2 1B Instruct (GGUF)...")
    print(f"   URL: {MODEL_URL}")
    
    try:
        success = download_file(MODEL_URL, MODEL_PATH)
        if success:
            print("\n✅ Download complete! You are ready to run the Two-Brain API.")
        else:
            print("\n❌ Download failed.")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    # Adjust path if run from inside ML_side
    if os.path.basename(os.getcwd()) == "ML_side":
        MODEL_DIR = "models"
        MODEL_PATH = os.path.join(MODEL_DIR, MODEL_FILENAME)
    
    main()