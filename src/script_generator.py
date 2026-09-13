from src.llm.base import LLMProvider
from src.models import EducationalScript
from src.template_loader import load_template


def generate_script(
    provider: LLMProvider, topic: str, repair_notes: str = ""
) -> EducationalScript:
    request = topic
    if repair_notes:
        request += f"\n\nCorrect these review issues in the new script:\n{repair_notes}"
    data = provider.generate_json(load_template("educational_script.txt"), request)
    return EducationalScript.model_validate(data)
