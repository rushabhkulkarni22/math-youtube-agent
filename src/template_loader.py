from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


def load_template(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")
