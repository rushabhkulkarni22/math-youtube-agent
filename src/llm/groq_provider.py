import json
import re
import time

from groq import BadRequestError, Groq, RateLimitError

from src.llm.base import LLMProvider


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, fallback_models: str = ""):
        if not api_key:
            raise ValueError("GROQ_API_KEY is missing. Add it to .env.")
        self.client = Groq(api_key=api_key)
        self.models = list(
            dict.fromkeys(
                [model]
                + [item.strip() for item in fallback_models.split(",") if item.strip()]
            )
        )
        self.unavailable_models: set[str] = set()

    @staticmethod
    def _retry_delay(exc: RateLimitError, attempt: int) -> float:
        match = re.search(
            r"try again in (?:(?P<hours>[0-9.]+)h)?"
            r"(?:(?P<minutes>[0-9.]+)m)?(?P<seconds>[0-9.]+)s",
            str(exc),
            re.I,
        )
        if match:
            return (
                float(match.group("hours") or 0) * 3600
                + float(match.group("minutes") or 0) * 60
                + float(match.group("seconds"))
                + 2
            )
        return min(60, 5 * (2**attempt))

    def _complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_completion_tokens: int = 12000,
        json_mode: bool = False,
    ) -> str:
        last_error: Exception | None = None
        for model in self.models:
            if model in self.unavailable_models:
                continue
            for attempt in range(4):
                try:
                    request = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.2,
                        "max_completion_tokens": max_completion_tokens,
                    }
                    if model.startswith("openai/gpt-oss-"):
                        request["reasoning_effort"] = "low"
                    if json_mode:
                        request["response_format"] = {"type": "json_object"}
                    response = self.client.chat.completions.create(**request)
                    print(f"LLM request completed with {model}.", flush=True)
                    return (response.choices[0].message.content or "").strip()
                except RateLimitError as exc:
                    last_error = exc
                    delay = self._retry_delay(exc, attempt)
                    # A long retry is normally a daily quota. Move immediately
                    # to another model instead of holding the runner idle.
                    if delay > 120:
                        self.unavailable_models.add(model)
                        print(
                            f"{model} is quota-limited for about {delay:.0f}s; "
                            "switching to the next model.",
                            flush=True,
                        )
                        break
                    if attempt == 3:
                        self.unavailable_models.add(model)
                        print(f"{model} remains rate-limited; trying fallback.", flush=True)
                        break
                    print(
                        f"{model} rate-limited; retrying in {delay:.0f}s "
                        f"(attempt {attempt + 2}/4).",
                        flush=True,
                    )
                    time.sleep(delay)
                except BadRequestError as exc:
                    last_error = exc
                    if json_mode and "json_validate_failed" in str(exc):
                        print(
                            f"{model} produced invalid native JSON; "
                            "retrying with a stricter prompt.",
                            flush=True,
                        )
                        user_prompt += (
                            "\nReturn one complete valid JSON object. Use plain-text "
                            "math and do not use LaTeX backslash commands in strings."
                        )
                        if attempt < 3:
                            continue
                        print(
                            f"{model} repeatedly produced invalid JSON; trying fallback.",
                            flush=True,
                        )
                        break
                    raise
        if last_error is not None:
            raise last_error
        raise RuntimeError("No Groq model is available.")

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        parse_error: json.JSONDecodeError | None = None
        for attempt in range(2):
            prompt = user_prompt
            if attempt:
                prompt += (
                    "\n\nReturn strict JSON only. Escape every backslash inside JSON "
                    "strings (for example, write \\\\theta rather than \\theta)."
                )
            content = self._complete(system_prompt, prompt, 4500, json_mode=True)
            fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
            try:
                return json.loads(fenced.group(1) if fenced else content)
            except json.JSONDecodeError as exc:
                parse_error = exc
                print(
                    f"Model returned invalid JSON; retrying ({exc.msg} at character "
                    f"{exc.pos}).",
                    flush=True,
                )
        assert parse_error is not None
        raise parse_error

    def generate_code(self, system_prompt: str, user_prompt: str) -> str:
        # Repairs include the previous complete source file, so reserve a
        # smaller completion budget to remain below Groq's free-tier TPM cap.
        completion_limit = 2500 if system_prompt.lstrip().startswith("Repair") else 7000
        content = self._complete(system_prompt, user_prompt, completion_limit)
        fenced = re.search(r"```(?:python)?\s*(.*?)(?:```|\Z)", content, re.DOTALL)
        return (fenced.group(1) if fenced else content).strip()
