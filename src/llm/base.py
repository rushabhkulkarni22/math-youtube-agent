from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def generate_json(self, system_prompt: str, user_prompt: str) -> dict: ...

    @abstractmethod
    def generate_code(self, system_prompt: str, user_prompt: str) -> str: ...
