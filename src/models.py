from enum import StrEnum

from pydantic import BaseModel, Field


class Status(StrEnum):
    PENDING = "PENDING"
    SCRIPT_GENERATED = "SCRIPT_GENERATED"
    MANIM_GENERATED = "MANIM_GENERATED"
    RENDERED = "RENDERED"
    AUDIO_GENERATED = "AUDIO_GENERATED"
    READY_TO_UPLOAD = "READY_TO_UPLOAD"
    UPLOADED = "UPLOADED"
    FAILED_VALIDATION = "FAILED_VALIDATION"
    FAILED = "FAILED"


class EducationalScript(BaseModel):
    topic: str
    hook: str
    introduction: str
    concept_explanation: str
    derivation_or_proof: str
    example: str
    interesting_fact: str
    conclusion: str


class SceneBeat(BaseModel):
    scene_number: int = Field(ge=1)
    title: str
    visual: str
    narration: str
    estimated_duration: float = Field(gt=0)


class ScenePlan(BaseModel):
    topic: str
    total_estimated_duration: float = Field(gt=0)
    scenes: list[SceneBeat] = Field(min_length=1)


class QualityReview(BaseModel):
    approved: bool
    mathematical_accuracy: str
    formula_check: str
    animation_fit: str
    duration_fit: str
    serious_issues: list[str] = Field(default_factory=list)


class VideoMetadata(BaseModel):
    title: str = Field(min_length=5, max_length=70)
    description: str = Field(min_length=20, max_length=5000)
    tags: list[str] = Field(min_length=3, max_length=30)
    hashtags: list[str] = Field(default_factory=list, max_length=10)
