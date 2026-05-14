import sys
import os

# Add deployment folder to path so test_api.py can import api.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "deployment")))
