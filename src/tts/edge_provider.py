from pathlib import Path

import edge_tts

from src.tts.base import TTSProvider


class EdgeTTSProvider(TTSProvider):
    def __init__(self, voice: str):
        self.voice = voice

    async def synthesize(self, text: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.stat().st_size > 0:
            return destination
        await edge_tts.Communicate(text=text, voice=self.voice).save(str(destination))
        return destination
