import json

from src.llm.base import LLMProvider
from src.models import EducationalScript, ScenePlan
from src.template_loader import load_template


def generate_scene_plan(
    provider: LLMProvider, script: EducationalScript
) -> ScenePlan:
    data = provider.generate_json(
        load_template("scene_plan.txt"), script.model_dump_json(indent=2)
    )
    return ScenePlan.model_validate(data)
