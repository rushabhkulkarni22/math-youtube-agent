import json
import logging
import re
from pathlib import Path

from config import Settings
from src.database import StateDatabase
from src.llm.base import LLMProvider
from src.manim_generator import generate_manim_code, repair_manim_code
from src.manim_validator import validate_code
from src.models import QualityReview, Status
from src.prompt_manager import PromptManager
from src.quality_checker import review_content
from src.renderer import RenderError, render_scene
from src.scene_planner import generate_scene_plan
from src.script_generator import generate_script
from src.video_validator import validate_video


def slugify(value: str) -> str:
    if "kaprekar" in value.lower() and "6174" in value:
        return "kaprekar_6174"
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug[:60] or "video"


class PhaseOnePipeline:
    def __init__(self, settings: Settings, provider: LLMProvider, logger: logging.Logger):
        self.settings = settings
        self.provider = provider
        self.logger = logger
        self.database = StateDatabase(settings.database_path)
        self.prompts = PromptManager(settings.workbook_path, self.database)

    def process(self, prompt: dict) -> Path:
        prompt_id, topic = int(prompt["id"]), str(prompt["prompt"])
        previous_video = self.database.get_video(prompt_id)
        if prompt["status"] == Status.RENDERED and previous_video:
            existing_path = Path(previous_video["video_path"])
            if existing_path.exists():
                self.logger.info("Prompt %s is already rendered; reusing %s", prompt_id, existing_path)
                return existing_path
        output_dir = self.settings.generated_dir / slugify(topic)
        output_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info("Prompt %s selected: %s", prompt_id, topic)
        try:
            script_path = output_dir / "script.json"
            if not script_path.exists():
                self.logger.info("Generating educational script")
                script = generate_script(self.provider, topic)
                script_path.write_text(script.model_dump_json(indent=2), encoding="utf-8")
            else:
                from src.models import EducationalScript
                script = EducationalScript.model_validate_json(script_path.read_text(encoding="utf-8"))
            self._status(prompt_id, Status.SCRIPT_GENERATED)

            plan_path = output_dir / "scene_plan.json"
            if not plan_path.exists():
                self.logger.info("Generating visual scene plan")
                plan = generate_scene_plan(self.provider, script)
                plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
            else:
                from src.models import ScenePlan
                plan = ScenePlan.model_validate_json(plan_path.read_text(encoding="utf-8"))

            approved_review_path = output_dir / "quality_review.json"
            if approved_review_path.exists():
                review = QualityReview.model_validate_json(
                    approved_review_path.read_text(encoding="utf-8")
                )
            else:
                for review_attempt in range(1, 4):
                    self.logger.info("Checking mathematical and visual quality (%s/3)", review_attempt)
                    review = review_content(self.provider, script, plan)
                    (output_dir / f"quality_review_v{review_attempt}.json").write_text(
                        review.model_dump_json(indent=2), encoding="utf-8"
                    )
                    if review.approved:
                        break
                    if review_attempt == 3:
                        raise ValueError(
                            "Content quality review failed: " + "; ".join(review.serious_issues)
                        )
                    self.logger.info("Regenerating content after quality review")
                    (output_dir / f"rejected_script_review_{review_attempt}.json").write_text(
                        script.model_dump_json(indent=2), encoding="utf-8"
                    )
                    (output_dir / f"rejected_plan_review_{review_attempt}.json").write_text(
                        plan.model_dump_json(indent=2), encoding="utf-8"
                    )
                    notes = "\n".join(review.serious_issues) or review.mathematical_accuracy
                    script = generate_script(self.provider, topic, notes)
                    script_path.write_text(script.model_dump_json(indent=2), encoding="utf-8")
                    plan = generate_scene_plan(self.provider, script)
                    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
                approved_review_path.write_text(
                    review.model_dump_json(indent=2), encoding="utf-8"
                )

            code = generate_manim_code(self.provider, script, plan)
            last_error = ""
            existing_versions = [
                int(path.stem.removeprefix("scene_v"))
                for path in output_dir.glob("scene_v*.py")
                if path.stem.removeprefix("scene_v").isdigit()
            ]
            version_start = max(existing_versions, default=0) + 1
            for attempt in range(1, self.settings.max_render_retries + 1):
                version_path = output_dir / f"scene_v{version_start + attempt - 1}.py"
                version_path.write_text(code, encoding="utf-8")
                try:
                    scene_name = validate_code(code)
                    final_scene = output_dir / "scene.py"
                    final_scene.write_text(code, encoding="utf-8")
                    self._status(prompt_id, Status.MANIM_GENERATED)
                    self.logger.info("Rendering attempt %s/%s", attempt, self.settings.max_render_retries)
                    final_video = render_scene(
                        final_scene, scene_name, output_dir, self.settings.manim_quality
                    )
                    details = validate_video(
                        final_video,
                        self.settings.video_min_duration,
                        self.settings.video_max_duration,
                    )
                    self.database.save_video(
                        prompt_id, Status.RENDERED,
                        script_path=str(script_path), scene_plan_path=str(plan_path),
                        manim_path=str(final_scene), video_path=str(final_video),
                        duration=details["duration"],
                    )
                    self._status(prompt_id, Status.RENDERED, video_file=str(final_video))
                    self.logger.info("Render successful: %s", final_video)
                    return final_video
                except (ValueError, RenderError) as exc:
                    last_error = str(exc)
                    self.database.log_error(prompt_id, "render", last_error, attempt)
                    self.logger.error("Attempt %s failed: %s", attempt, last_error)
                    if attempt < self.settings.max_render_retries:
                        code = repair_manim_code(self.provider, code, last_error)
            raise RuntimeError(f"Render failed after repair attempts: {last_error}")
        except Exception as exc:
            self._status(prompt_id, Status.FAILED, error_message=str(exc)[-1000:])
            raise

    def _status(self, prompt_id: int, status: Status, **values: object) -> None:
        self.database.set_status(prompt_id, status)
        if "error_message" not in values:
            values["error_message"] = ""
        self.prompts.update_excel(prompt_id, status, **values)
