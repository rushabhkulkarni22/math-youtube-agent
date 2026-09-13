import json

from src.llm.base import LLMProvider
from src.models import EducationalScript, VideoMetadata
from src.template_loader import load_template


def generate_metadata(provider: LLMProvider, script: EducationalScript) -> VideoMetadata:
    data = provider.generate_json(load_template("metadata.txt"), script.model_dump_json(indent=2))
    metadata = VideoMetadata.model_validate(data)
    metadata.tags = list(dict.fromkeys(tag.strip() for tag in metadata.tags if tag.strip()))
    return metadata
