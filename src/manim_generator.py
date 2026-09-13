from src.llm.base import LLMProvider
from src.models import EducationalScript, ScenePlan
from src.template_loader import load_template


def generate_manim_code(
    provider: LLMProvider, script: EducationalScript, plan: ScenePlan
) -> str:
    request = f"EDUCATIONAL SCRIPT:\n{script.model_dump_json(indent=2)}\n\nSCENE PLAN:\n{plan.model_dump_json(indent=2)}"
    return provider.generate_code(load_template("manim_generation.txt"), request)


def repair_manim_code(provider: LLMProvider, code: str, error: str) -> str:
    request = f"FAILING CODE:\n{code}\n\nERROR:\n{error[-6000:]}"
    return provider.generate_code(load_template("manim_repair.txt"), request)
