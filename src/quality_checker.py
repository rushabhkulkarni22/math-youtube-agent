import json

from src.llm.base import LLMProvider
from src.models import EducationalScript, QualityReview, ScenePlan
from src.template_loader import load_template


def review_content(
    provider: LLMProvider, script: EducationalScript, plan: ScenePlan
) -> QualityReview:
    request = json.dumps(
        {"script": script.model_dump(), "scene_plan": plan.model_dump()}, indent=2
    )
    data = provider.generate_json(load_template("quality_review.txt"), request)
    return QualityReview.model_validate(data)
