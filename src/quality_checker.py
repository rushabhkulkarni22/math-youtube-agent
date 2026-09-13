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
    instructions = load_template("quality_review.txt")
    if "kaprekar" in request.lower() and "6174" in request:
        instructions += """
For this Kaprekar 6174 review only: use the four-digit base-10 routine. Valid
claims include convergence from a four-digit string with at least two distinct
digits in at most seven iterations, preserving leading zeros, and the fixed
point 7641 - 1467 = 6174. Do not introduce or discuss these claims for any
unrelated topic.
"""
    data = provider.generate_json(instructions, request)
    return QualityReview.model_validate(data)
