import asyncio
from pathlib import Path

from src.models import ScenePlan
from src.tts.base import TTSProvider


def create_narration(plan: ScenePlan, output_dir: Path, provider: TTSProvider) -> list[Path]:
    lines = [scene.narration.strip() for scene in plan.scenes if scene.narration.strip()]
    (output_dir / "narration.txt").write_text("\n\n".join(lines), encoding="utf-8")

    async def generate() -> list[Path]:
        paths = []
        for index, text in enumerate(lines, 1):
            path = output_dir / "audio_segments" / f"segment_{index:02d}.mp3"
            paths.append(await provider.synthesize(text, path))
        return paths

    return asyncio.run(generate())
