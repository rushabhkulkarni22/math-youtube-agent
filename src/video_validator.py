import json
import subprocess
from pathlib import Path


def validate_video(path: Path, minimum: float, maximum: float) -> dict:
    if not path.exists() or path.stat().st_size < 1024:
        raise ValueError("Rendered video is missing or unexpectedly small")
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=60, check=True,
    )
    probe = json.loads(result.stdout)
    duration = float(probe["format"]["duration"])
    video = next((s for s in probe["streams"] if s["codec_type"] == "video"), None)
    if not video:
        raise ValueError("No video stream found")
    if not minimum <= duration <= maximum:
        raise ValueError(f"Duration {duration:.1f}s is outside {minimum}-{maximum}s")
    return {
        "duration": duration,
        "width": int(video["width"]),
        "height": int(video["height"]),
        "size": path.stat().st_size,
    }
