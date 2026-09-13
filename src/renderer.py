import shutil
import subprocess
import sys
from pathlib import Path


QUALITY_FLAGS = {
    "low_quality": "-ql",
    "medium_quality": "-qm",
    "high_quality": "-qh",
    "production_quality": "-qk",
}


class RenderError(RuntimeError):
    pass


def render_scene(scene_file: Path, scene_name: str, output_dir: Path, quality: str) -> Path:
    media_dir = output_dir / "media"
    result = subprocess.run(
        [
            sys.executable, "-m", "manim", QUALITY_FLAGS[quality],
            "--disable_caching", "--media_dir", str(media_dir),
            str(scene_file), scene_name,
        ],
        cwd=output_dir,
        capture_output=True,
        text=True,
        timeout=1200,
    )
    (output_dir / "render.log").write_text(
        result.stdout + "\n" + result.stderr, encoding="utf-8"
    )
    if result.returncode != 0:
        raise RenderError((result.stderr or result.stdout)[-8000:])
    videos = [p for p in media_dir.rglob("*.mp4") if "partial_movie_files" not in p.parts]
    if not videos:
        raise RenderError("Manim exited successfully but produced no MP4")
    rendered = max(videos, key=lambda path: path.stat().st_mtime)
    final_video = output_dir / "final_video.mp4"
    shutil.copy2(rendered, final_video)
    return final_video
