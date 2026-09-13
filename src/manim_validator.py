import ast
from pathlib import Path


ALLOWED_IMPORTS = {"manim", "math", "numpy"}
BLOCKED_NAMES = {
    "eval", "exec", "compile", "open", "input", "__import__",
    "subprocess", "socket", "requests", "urllib", "shutil",
}


def validate_code(code: str) -> str:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise ValueError(f"Generated code has invalid Python syntax: {exc}") from exc
    scene_classes = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORTS:
                    raise ValueError(f"Blocked import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            if module not in ALLOWED_IMPORTS:
                raise ValueError(f"Blocked import: {node.module}")
        elif isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
            raise ValueError(f"Blocked name: {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in {
            "system", "popen", "remove", "unlink", "rmtree", "getenv", "environ"
        }:
            raise ValueError(f"Blocked operation: {node.attr}")
        elif isinstance(node, ast.ClassDef):
            if any(isinstance(base, ast.Name) and base.id.endswith("Scene") for base in node.bases):
                scene_classes += 1
    if scene_classes != 1:
        raise ValueError("Generated code must define exactly one Scene subclass")
    return next(
        node.name for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any(isinstance(base, ast.Name) and base.id.endswith("Scene") for base in node.bases)
    )


def validate_file(path: Path) -> str:
    return validate_code(path.read_text(encoding="utf-8"))
