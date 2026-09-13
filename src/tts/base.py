from abc import ABC, abstractmethod
from pathlib import Path


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, destination: Path) -> Path: ...
