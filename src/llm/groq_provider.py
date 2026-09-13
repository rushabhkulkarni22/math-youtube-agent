import json
import re

from groq import Groq

from src.llm.base import LLMProvider


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError("GROQ_API_KEY is missing. Add it to .env.")
        self.client = Groq(api_key=api_key)
        self.model = model

    def _complete(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_completion_tokens=12000,
        )
        return (response.choices[0].message.content or "").strip()

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        content = self._complete(system_prompt, user_prompt)
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
        return json.loads(fenced.group(1) if fenced else content)

    def generate_code(self, system_prompt: str, user_prompt: str) -> str:
        content = self._complete(system_prompt, user_prompt)
        fenced = re.search(r"```(?:python)?\s*(.*?)(?:```|\Z)", content, re.DOTALL)
        return (fenced.group(1) if fenced else content).strip()
