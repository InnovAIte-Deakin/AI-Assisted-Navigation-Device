from typing import Dict, Optional
from slow_lane.memorybuffer import NavigationMemory 

# --- 1. Navigation & AI State ---
# Short-term memory for the user's journey (max 50 events)
memory = NavigationMemory(max_events=50)

# The LLM instance. This is None initially and gets populated by the startup event in main.py.
llm_brain = None 

# --- 2. Collaboration State (Ask-a-Friend) ---
# Stores active WebSocket sessions: session_id -> {ws connections, timestamps}
collaboration_sessions: Dict[str, Dict] = {}