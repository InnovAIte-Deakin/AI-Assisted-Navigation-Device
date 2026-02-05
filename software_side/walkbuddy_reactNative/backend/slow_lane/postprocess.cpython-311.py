import json
import re
from typing import Any, Dict, Set


def labels_in_context(context_text: str) -> Set[str]:
    labels = set()
    for line in context_text.splitlines():
        line = line.strip().lstrip("-").strip()
        if not line:
            continue
        m = re.match(r"^([a-zA-Z0-9_ -]+?)\s+(ahead|on the left|on the right)", line)
        if m:
            labels.add(m.group(1).lower())
    return labels


def safe_json_parse(text: str) -> Dict[str, Any]:
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return {
            "summary": "I don't have enough information.",
            "hazards": [],
            "suggested_action": "I don't have enough information.",
        }


def filter_hallucinations(parsed: Dict[str, Any], allowed_labels: Set[str]) -> Dict[str, Any]:
    hazards = parsed.get("hazards", [])
    clean = []
    for h in hazards:
        label = str(h.get("label", "")).lower()
        if label in allowed_labels:
            clean.append(h)
    parsed["hazards"] = clean
    return parsed


def replace_placeholders(parsed: Dict[str, Any]) -> Dict[str, Any]:
    bad = {
        "1 short sentence based only on context",
        "1 short sentence of safest movement based only on context",
    }
    if parsed.get("suggested_action", "").strip() in bad:
        parsed["suggested_action"] = "I don't have enough information."
    return parsed
