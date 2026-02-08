import json
import logging
from llama_cpp import Llama
from typing import List, Dict
from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("brain.llm")

class SlowLaneBrain:
    # We keep the text, but we don't manually format the string anymore
    SYSTEM_INSTRUCTION = """You are an offline navigation assistant for a visually impaired user.
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
            verbose=False
        )

    def ask(self, events: List[Dict], question: str) -> str:
        # 1. Prepare Context
        lines = []
        for e in events[-20:]:
            dist = f"~{e['distance_m']:.1f}m" if e.get("distance_m") else "unknown distance"
            lines.append(f"- {e['label']} {e['direction']}, {dist} (conf {e['confidence']:.2f})")
        context_str = "\n".join(lines)
        
        # 2. Build Message History (Let the library handle the template)
        messages = [
            {"role": "system", "content": self.SYSTEM_INSTRUCTION},
            {"role": "user", "content": f"Context:\n{context_str}\n\nUser question: {question}"}
        ]

        with tracer.start_as_current_span("llm.inference") as span:
            # FIX: Use create_chat_completion
            output = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=256,
                temperature=0.1, # Low temp for JSON consistency
                response_format={"type": "json_object"} # Forces valid JSON (if supported by your GGUF version)
            )
            
            # Extract content from the chat structure
            raw_text = output["choices"][0]["message"]["content"].strip()
            span.set_attribute("output_chars", len(raw_text))

        try:
            # Clean markdown if the model adds it (e.g. ```json ... ```)
            clean_resp = raw_text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean_resp)
            
            # Return the most useful part
            return parsed.get("suggested_action") or parsed.get("summary") or clean_resp
            
        except Exception as e:
            logger.error(f"JSON Parse Error: {e} | Raw: {raw_text}")
            return raw_text