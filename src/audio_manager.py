import subprocess
from pathlib import Path


def _duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True, timeout=60,
    )
    return float(result.stdout.strip())


def combine_audio_video(video: Path, segments: list[Path], output_dir: Path) -> Path:
    concat_file = output_dir / "audio_segments.txt"
    concat_file.write_text(
        "".join(f"file '{path.resolve().as_posix()}'\n" for path in segments),
        encoding="utf-8",
    )
    narration = output_dir / "narration.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c:a", "libmp3lame", str(narration)],
        check=True, capture_output=True, timeout=300,
    )
    video_duration, audio_duration = _duration(video), _duration(narration)
    ratio = audio_duration / video_duration
    final_video = output_dir / "final_video.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video), "-i", str(narration),
            "-filter:v", f"setpts={ratio:.8f}*PTS",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
            str(final_video),
        ],
        check=True, capture_output=True, timeout=1200,
    )
    return final_video
