import json
import re
import time

from groq import Groq, RateLimitError

from src.llm.base import LLMProvider


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("GROQ_API_KEY is missing. Add it to .env.")
        self.client = Groq(api_key=api_key)
        self.model = model

    def _complete(
        self, system_prompt: str, user_prompt: str, max_completion_tokens: int = 12000
    ) -> str:
        for attempt in range(5):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    max_completion_tokens=max_completion_tokens,
                )
                break
            except RateLimitError as exc:
                if attempt == 4:
                    raise
                match = re.search(r"try again in ([0-9.]+)s", str(exc), re.I)
                delay = float(match.group(1)) + 1 if match else min(30, 5 * (2**attempt))
                time.sleep(delay)
        return (response.choices[0].message.content or "").strip()

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        content = self._complete(system_prompt, user_prompt)
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
        return json.loads(fenced.group(1) if fenced else content)

    def generate_code(self, system_prompt: str, user_prompt: str) -> str:
        # Repairs include the previous complete source file, so reserve a
        # smaller completion budget to remain below Groq's free-tier TPM cap.
        completion_limit = 2500 if system_prompt.lstrip().startswith("Repair") else 12000
        content = self._complete(system_prompt, user_prompt, completion_limit)
        fenced = re.search(r"```(?:python)?\s*(.*?)(?:```|\Z)", content, re.DOTALL)
        return (fenced.group(1) if fenced else content).strip()
