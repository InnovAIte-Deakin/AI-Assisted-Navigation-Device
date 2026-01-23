from llama_cpp import Llama
from .prompts import build_prompt


class SlowLaneLLM:
    """
    Offline LLM wrapper for the Slow Lane.
    """

    def __init__(
        self,
        model_path: str,
        n_ctx: int = 2048,
        n_threads: int = 8,
    ):
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            temperature=0.0,
            top_p=0.9,
            repeat_penalty=1.1,
            verbose=False,
        )

    def answer(self, context_text: str, question: str) -> str:
        prompt = build_prompt(context_text, question)

        out = self.llm(
            prompt,
            max_tokens=256,
            stop=["\n\n"],
        )

        return out["choices"][0]["text"].strip()
