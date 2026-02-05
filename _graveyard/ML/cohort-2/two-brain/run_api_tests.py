import requests
import time
from PIL import Image
import numpy as np
import io
import sys

# URL of the local API
BASE_URL = "http://localhost:8000"

def create_dummy_image():
    # Create a simple red image (640x480)
    # in real life this would be a camera frame
    img_array = np.zeros((480, 640, 3), dtype=np.uint8)
    img_array.fill(100) # greyish
    # Add a "box" or some noise to potentially trigger something? 
    # Validating pure black/grey image is fine, YOLO will just detect nothing.
    img = Image.fromarray(img_array)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def test_detect():
    print("Testing /detect endpoint...")
    img_bytes = create_dummy_image()
    files = {'file': ('test.jpg', img_bytes, 'image/jpeg')}
    
    try:
        response = requests.post(f"{BASE_URL}/detect", files=files)
        if response.status_code == 200:
            print(f"SUCCESS: {response.json()}")
        else:
            print(f"FAILED: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"ERROR: {e}")

def test_two_brain():
    print("\nTesting /two_brain endpoint...")
    img_bytes = create_dummy_image()
    files = {'file': ('test.jpg', img_bytes, 'image/jpeg')}
    data = {'question': 'What is in front of me?'}
    
    try:
        response = requests.post(f"{BASE_URL}/two_brain", files=files, data=data)
        if response.status_code == 200:
            print(f"SUCCESS: {response.json()}")
        else:
            print(f"FAILED: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"ERROR: {e}")

def wait_for_server():
    print("Waiting for server to start...")
    for _ in range(30):
        try:
            requests.get(f"{BASE_URL}/docs")
            print("Server is up!")
            return True
        except:
            time.sleep(1)
            print(".", end="", flush=True)
    return False

if __name__ == "__main__":
    if wait_for_server():
        test_detect()
        test_two_brain()
    else:
        print("Server did not start in time.")
