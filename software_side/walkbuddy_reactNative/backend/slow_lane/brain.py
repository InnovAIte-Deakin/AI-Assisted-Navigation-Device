import json
import logging
from llama_cpp import Llama
from typing import List, Dict

logger = logging.getLogger(__name__)

class SlowLaneBrain:
    SYSTEM_PROMPT = """You are an offline navigation assistant for a visually impaired user.
Hard rules:
- Use ONLY the provided context.
- Do NOT invent objects, hazards, distances, or relationships.
- Output MUST be valid JSON only.
- Be safety-first and concise.

Return JSON with EXACTLY these keys:
{
  "summary": "<1–2 short sentences based only on context>",
  "hazards": [{"label": "string", "direction": "ahead/left/right", "action": "avoid/slow/stop", "reason": "string"}],
  "suggested_action": "<1 short sentence based only on context>"
}"""

    def __init__(self, model_path: str):
        self.llm = Llama(
            model_path=model_path,
            n_ctx=2048,
            n_threads=8,
            temperature=0.0,
            verbose=False
        )

    def _build_prompt(self, context_text: str, user_question: str) -> str:
        return f"{self.SYSTEM_PROMPT}\n\nContext:\n{context_text}\n\nUser question: {user_question}\n\nJSON:"

    def ask(self, events: List[Dict], question: str) -> str:
        # Transform structured memory events into text context
        lines = []
        for e in events[-20:]:  # Last 20 events for context
            dist = f"~{e['distance_m']:.1f}m" if e.get("distance_m") else "unknown distance"
            lines.append(f"- {e['label']} {e['direction']}, {dist} (conf {e['confidence']:.2f})")
        
        context_str = "\n".join(lines)
        prompt = self._build_prompt(context_str, question)

        output = self.llm(prompt, max_tokens=256, stop=["\n\n"])
        raw_text = output["choices"][0]["text"].strip()

        try:
            # Clean markdown and parse JSON
            clean_resp = raw_text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean_resp)
            return parsed.get("suggested_action") or parsed.get("summary") or clean_resp
        except Exception as e:
            logger.error(f"JSON Parse Error: {e}")
            return raw_text