import json
import logging
import shutil
from pathlib import Path

from config import Settings
from src.audio_manager import combine_audio_video
from src.database import StateDatabase, now
from src.llm.base import LLMProvider
from src.metadata_generator import generate_metadata
from src.models import EducationalScript, ScenePlan, Status, VideoMetadata
from src.narration_generator import create_narration
from src.pipeline import PhaseOnePipeline, slugify
from src.prompt_manager import PromptManager
from src.thumbnail_generator import generate_thumbnail
from src.tts import EdgeTTSProvider
from src.video_validator import validate_video
from src.youtube_uploader import authorize, upload_video


class AutomatedVideoPipeline:
    def __init__(self, settings: Settings, provider: LLMProvider, logger: logging.Logger):
        self.settings = settings
        self.provider = provider
        self.logger = logger
        self.database = StateDatabase(settings.database_path)
        self.prompts = PromptManager(settings.workbook_path, self.database)
        self.phase_one = PhaseOnePipeline(settings, provider, logger)

    def process(self, prompt: dict) -> Path:
        prompt_id, topic = int(prompt["id"]), str(prompt["prompt"])
        output_dir = self.settings.generated_dir / slugify(topic)
        silent_video = output_dir / "rendered_video.mp4"
        final_video = output_dir / "final_video.mp4"
        if prompt["status"] == Status.UPLOADED and final_video.exists():
            self.logger.info("Prompt %s is already uploaded; skipping", prompt_id)
            return final_video
        if not silent_video.exists():
            rendered = self.phase_one.process(prompt)
            shutil.copy2(rendered, silent_video)

        script = EducationalScript.model_validate_json((output_dir / "script.json").read_text(encoding="utf-8"))
        plan = ScenePlan.model_validate_json((output_dir / "scene_plan.json").read_text(encoding="utf-8"))

        narration_file = output_dir / "narration.mp3"
        if not narration_file.exists() or not final_video.exists():
            self.logger.info("Generating narration with %s", self.settings.tts_voice)
            segments = create_narration(plan, output_dir, EdgeTTSProvider(self.settings.tts_voice))
            final_video = combine_audio_video(silent_video, segments, output_dir)
        self._status(prompt_id, Status.AUDIO_GENERATED)

        metadata_path = output_dir / "metadata.json"
        if metadata_path.exists():
            metadata = VideoMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))
        else:
            self.logger.info("Generating YouTube metadata")
            metadata = generate_metadata(self.provider, script)
            metadata_path.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")

        thumbnail = output_dir / "thumbnail.png"
        if not thumbnail.exists():
            self.logger.info("Generating thumbnail")
            generate_thumbnail(topic, thumbnail)

        details = validate_video(final_video, self.settings.video_min_duration, self.settings.video_max_duration)
        self.database.save_video(prompt_id, Status.READY_TO_UPLOAD, video_path=str(final_video), duration=details["duration"])
        self._status(prompt_id, Status.READY_TO_UPLOAD, video_file=str(final_video), thumbnail_file=str(thumbnail))

        if self.settings.dry_run:
            self.logger.info("DRY RUN — YouTube upload skipped.")
            return final_video

        self.logger.info("Uploading video to YouTube as %s", self.settings.youtube_privacy)
        credentials = authorize(self.settings.youtube_client_secret_file, self.settings.youtube_token_file)
        result = upload_video(final_video, thumbnail, metadata, self.settings.youtube_privacy, credentials)
        (output_dir / "upload_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        self.database.record_upload(prompt_id, result["youtube_video_id"], result["youtube_url"])
        self._status(
            prompt_id, Status.UPLOADED, youtube_video_id=result["youtube_video_id"],
            youtube_url=result["youtube_url"], upload_date=now(),
        )
        self.logger.info("Upload successful: %s", result["youtube_url"])
        return final_video

    def _status(self, prompt_id: int, status: Status, **values: object) -> None:
        self.database.set_status(prompt_id, status)
        values.setdefault("error_message", "")
        self.prompts.update_excel(prompt_id, status, **values)
