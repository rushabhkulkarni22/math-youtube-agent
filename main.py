import argparse

from config import get_settings
from src.automation import AutomatedVideoPipeline
from src.database import StateDatabase
from src.llm import GroqProvider
from src.logger import configure_logging
from src.prompt_manager import PromptManager
from src.youtube_uploader import authorize


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 1 of the math video agent")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--prompt-id", type=int)
    group.add_argument("--topic")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--authorize-youtube", action="store_true")
    parser.add_argument(
        "--fail-on-item-error",
        action="store_true",
        help="Return a failing exit code if any selected prompt fails.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    logger = configure_logging(settings.logs_dir)
    database = StateDatabase(settings.database_path)
    manager = PromptManager(settings.workbook_path, database)
    imported = manager.import_prompts()
    logger.info("Imported/synchronized %s Excel prompts", imported)

    if args.authorize_youtube:
        authorize(settings.youtube_client_secret_file, settings.youtube_token_file)
        logger.info("YouTube authorization saved securely")
        return 0

    if args.retry_failed:
        logger.info("Reset %s failed prompts", database.reset_failed())

    if args.topic:
        prompt_id = database.add_topic(args.topic)
        prompt = database.get_prompt(prompt_id)
    elif args.prompt_id:
        prompt = database.get_prompt(args.prompt_id)
    provider = GroqProvider(settings.groq_api_key, settings.llm_model)
    pipeline = AutomatedVideoPipeline(settings, provider, logger)
    if args.topic or args.prompt_id:
        if not prompt:
            raise SystemExit("No matching prompt was found")
        pipeline.process(prompt)
        return 0

    limit = min(args.limit, settings.videos_per_day)
    had_failure = False
    for _ in range(limit):
        prompt = database.next_actionable()
        if not prompt:
            logger.info("No actionable prompts remain")
            break
        try:
            pipeline.process(prompt)
        except Exception:
            logger.exception("Prompt %s failed; continuing batch", prompt["id"])
            had_failure = True
    return 1 if had_failure and args.fail_on_item_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
