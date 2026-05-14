"""
Hybrid LLM Navigation Reasoning Engine
Chain: Ollama (offline) → OpenAI (cloud) → Rule-based (fallback)

Each tier is tried in order. If a tier fails or times out, the next is used.
This ensures the system works with no internet, limited API quota, or both.
"""

import json
import time
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────

OLLAMA_ENDPOINT  = "http://localhost:11434/api/generate"
OLLAMA_MODEL     = "llama3.2:3b"
OLLAMA_TIMEOUT   = 30

OPENAI_MODEL     = "gpt-4o-mini"
OPENAI_TIMEOUT   = 15

# ── Prompt template ────────────────────────────────────────────────────────────

NAVIGATION_PROMPT = """You are a navigation assistant for a visually impaired person.
Objects detected (sorted by priority):
{detections}

Spatial context: {spatial}
Location: {location}
User intent: {intent}

Give a single, short navigation instruction (1-2 sentences, plain English, no bullet points).
Focus on the highest-priority object. Be direct and specific about direction."""


def _build_prompt(detections: List[Dict], spatial: Dict, location: str, intent: str) -> str:
    det_lines = []
    for d in detections[:5]:
        name = d.get("class_name", "unknown")
        conf = d.get("confidence", 0)
        pos  = d.get("frame_position", d.get("position", "unknown"))
        lbl  = d.get("priority_label", "")
        det_lines.append(f"  - {name} [{lbl}] confidence={conf:.0%} position={pos}")

    return NAVIGATION_PROMPT.format(
        detections="\n".join(det_lines) if det_lines else "  - None",
        spatial=f"{spatial.get('scene_density', 'unknown')} scene, {spatial.get('object_count', 0)} objects",
        location=location,
        intent=intent,
    )


# ── Tier 1: Ollama (offline) ───────────────────────────────────────────────────

def _query_ollama(prompt: str) -> Optional[str]:
    try:
        import requests
        payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
        r = requests.post(OLLAMA_ENDPOINT, json=payload, timeout=OLLAMA_TIMEOUT)
        if r.status_code == 200:
            text = r.json().get("response", "").strip()
            if text:
                logger.info("LLM: Ollama responded")
                return text
    except Exception as e:
        logger.warning(f"Ollama unavailable: {e}")
    return None


# ── Tier 2: OpenAI (cloud) ─────────────────────────────────────────────────────

def _query_openai(prompt: str) -> Optional[str]:
    try:
        import openai
        import os
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set — skipping OpenAI tier")
            return None
        client = openai.OpenAI(api_key=api_key, timeout=OPENAI_TIMEOUT)
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
        )
        text = resp.choices[0].message.content.strip()
        if text:
            logger.info("LLM: OpenAI responded")
            return text
    except Exception as e:
        logger.warning(f"OpenAI unavailable: {e}")
    return None


# ── Tier 3: Rule-based fallback ────────────────────────────────────────────────

def _rule_based_fallback(detections: List[Dict], spatial: Dict) -> str:
    if not detections:
        return "Path appears clear. Continue forward carefully."

    top = detections[0]
    name = top.get("class_name", "object")
    pos  = top.get("frame_position", top.get("position", "ahead"))
    p    = top.get("priority", 1)

    if p == 5:
        return f"Stop immediately. {name.capitalize()} detected {pos}. Do not proceed until safe."
    elif p == 4:
        return f"Caution — {name} {pos}. Slow down and navigate carefully around it."
    elif p == 3:
        if pos == "center":
            return f"{name.capitalize()} ahead. Move to the side to continue."
        return f"{name.capitalize()} on your {pos}. Continue with awareness."
    else:
        return f"Minor obstacle detected ({name}). Path is mostly clear — proceed with care."


# ── Public interface ───────────────────────────────────────────────────────────

class LLMNavigationReasoner:
    """
    Hybrid LLM reasoning engine.
    Tries Ollama first, falls back to OpenAI, then rule-based.
    Mode can be forced via the `mode` parameter.
    """

    MODES = ("hybrid", "ollama", "openai", "rule-based")

    def __init__(self, mode: str = "hybrid", model_type: str = None):
        # model_type kept for backward compatibility with navigation_pipeline.py
        self.mode = mode if mode in self.MODES else "hybrid"
        logger.info(f"LLMNavigationReasoner initialised in '{self.mode}' mode")

    def reason_about_navigation(
        self,
        detections:  List[Dict],
        spatial:     Dict,
        user_intent: str = "Navigate safely",
        location:    str = "Library",
    ) -> Dict:

        start   = time.time()
        prompt  = _build_prompt(detections, spatial, location, user_intent)
        tier_used = "unknown"
        response  = None

        if self.mode in ("hybrid", "ollama"):
            response = _query_ollama(prompt)
            if response:
                tier_used = "ollama"

        if response is None and self.mode in ("hybrid", "openai"):
            response = _query_openai(prompt)
            if response:
                tier_used = "openai"

        if response is None:
            response  = _rule_based_fallback(detections, spatial)
            tier_used = "rule-based"

        elapsed_ms = (time.time() - start) * 1000
        top        = detections[0] if detections else {}

        return {
            "direction":    response,
            "obstacles":    ", ".join(d.get("class_name","") for d in detections
                                      if d.get("frame_position","") in ("center","ahead")) or "None",
            "landmarks":    ", ".join(d.get("class_name","") for d in detections
                                      if d.get("confidence", 0) > 0.7) or "None",
            "safety_level": self._safety_level(top.get("priority", 1)),
            "llm_tier":     tier_used,
            "latency_ms":   round(elapsed_ms, 1),
        }

    @staticmethod
    def _safety_level(priority: int) -> str:
        if priority >= 4:
            return "High"
        elif priority >= 3:
            return "Medium"
        return "Low"
