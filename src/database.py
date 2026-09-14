import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS prompts (
    id INTEGER PRIMARY KEY,
    prompt TEXT NOT NULL UNIQUE,
    normalized_prompt TEXT NOT NULL UNIQUE,
    excel_row INTEGER,
    status TEXT NOT NULL DEFAULT 'PENDING',
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_prompts_status ON prompts(status);
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL UNIQUE REFERENCES prompts(id),
    script_path TEXT,
    scene_plan_path TEXT,
    manim_path TEXT,
    video_path TEXT,
    duration REAL,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL REFERENCES prompts(id),
    stage TEXT NOT NULL,
    error TEXT NOT NULL,
    retry_number INTEGER NOT NULL DEFAULT 0,
    timestamp TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL UNIQUE REFERENCES prompts(id),
    youtube_video_id TEXT NOT NULL,
    youtube_url TEXT NOT NULL,
    status TEXT NOT NULL,
    upload_time TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateDatabase:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.executescript(SCHEMA)

    def upsert_prompt(self, prompt_id: int, prompt: str, excel_row: int | None) -> None:
        normalized = " ".join(prompt.lower().split())
        timestamp = now()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                """INSERT INTO prompts
                   (id, prompt, normalized_prompt, excel_row, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET prompt=excluded.prompt,
                   normalized_prompt=excluded.normalized_prompt,
                   excel_row=excluded.excel_row, updated_at=excluded.updated_at""",
                (prompt_id, prompt, normalized, excel_row, timestamp, timestamp),
            )

    def add_topic(self, prompt: str) -> int:
        normalized = " ".join(prompt.lower().split())
        timestamp = now()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            existing = connection.execute(
                "SELECT id FROM prompts WHERE normalized_prompt = ?", (normalized,)
            ).fetchone()
            if existing:
                return int(existing[0])
            next_id = connection.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 FROM prompts"
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO prompts
                   (id, prompt, normalized_prompt, excel_row, created_at, updated_at)
                   VALUES (?, ?, ?, NULL, ?, ?)""",
                (next_id, prompt, normalized, timestamp, timestamp),
            )
            return int(next_id)

    def get_prompt(self, prompt_id: int) -> dict | None:
        with closing(sqlite3.connect(self.path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM prompts WHERE id = ?", (prompt_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_video(self, prompt_id: int) -> dict | None:
        with closing(sqlite3.connect(self.path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM videos WHERE prompt_id = ?", (prompt_id,)
            ).fetchone()
        return dict(row) if row else None

    def next_pending(self) -> dict | None:
        with closing(sqlite3.connect(self.path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM prompts WHERE status = 'PENDING' ORDER BY id LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def next_actionable(self, exclude_ids: set[int] | None = None) -> dict | None:
        exclude_ids = exclude_ids or set()
        exclusion = ""
        parameters: tuple[int, ...] = ()
        if exclude_ids:
            placeholders = ",".join("?" for _ in exclude_ids)
            exclusion = f" AND id NOT IN ({placeholders})"
            parameters = tuple(sorted(exclude_ids))
        with closing(sqlite3.connect(self.path)) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                f"""SELECT * FROM prompts
                   WHERE status IN ('PENDING','SCRIPT_GENERATED','MANIM_GENERATED',
                                    'RENDERED','AUDIO_GENERATED','READY_TO_UPLOAD')
                   {exclusion}
                   ORDER BY CASE status WHEN 'READY_TO_UPLOAD' THEN 0 ELSE 1 END, id
                   LIMIT 1""",
                parameters,
            ).fetchone()
        return dict(row) if row else None

    def reset_failed(self) -> int:
        with closing(sqlite3.connect(self.path)) as connection, connection:
            cursor = connection.execute(
                "UPDATE prompts SET status='PENDING', error_message='', updated_at=? WHERE status LIKE 'FAILED%'",
                (now(),),
            )
            return cursor.rowcount

    def set_status(self, prompt_id: int, status: str, error: str = "") -> None:
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "UPDATE prompts SET status=?, error_message=?, updated_at=? WHERE id=?",
                (status, error, now(), prompt_id),
            )

    def save_video(self, prompt_id: int, status: str, **paths: object) -> None:
        fields = {
            "script_path": paths.get("script_path"),
            "scene_plan_path": paths.get("scene_plan_path"),
            "manim_path": paths.get("manim_path"),
            "video_path": paths.get("video_path"),
            "duration": paths.get("duration"),
        }
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                """INSERT INTO videos
                   (prompt_id, script_path, scene_plan_path, manim_path,
                    video_path, duration, status, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(prompt_id) DO UPDATE SET
                   script_path=COALESCE(excluded.script_path, videos.script_path),
                   scene_plan_path=COALESCE(excluded.scene_plan_path, videos.scene_plan_path),
                   manim_path=COALESCE(excluded.manim_path, videos.manim_path),
                   video_path=COALESCE(excluded.video_path, videos.video_path),
                   duration=COALESCE(excluded.duration, videos.duration),
                   status=excluded.status, updated_at=excluded.updated_at""",
                (prompt_id, *fields.values(), status, now()),
            )

    def log_error(self, prompt_id: int, stage: str, error: str, retry: int) -> None:
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                "INSERT INTO errors(prompt_id,stage,error,retry_number,timestamp) VALUES(?,?,?,?,?)",
                (prompt_id, stage, error[-8000:], retry, now()),
            )
            connection.execute(
                "UPDATE prompts SET retry_count=retry_count+1, updated_at=? WHERE id=?",
                (now(), prompt_id),
            )

    def record_upload(self, prompt_id: int, video_id: str, url: str) -> None:
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute(
                """INSERT INTO uploads(prompt_id,youtube_video_id,youtube_url,status,upload_time)
                   VALUES(?,?,?,'UPLOADED',?)
                   ON CONFLICT(prompt_id) DO UPDATE SET youtube_video_id=excluded.youtube_video_id,
                   youtube_url=excluded.youtube_url,status='UPLOADED',upload_time=excluded.upload_time""",
                (prompt_id, video_id, url, now()),
            )
