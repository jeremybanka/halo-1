"""Source-contract tests inspect the actual runtime modules after extraction."""

from pathlib import Path
import os

RUNTIME_UNITS = ("runtime_config.h", "scene.c", "presentation.c", "runtime_qa.c", "main.c")


def read_runtime(path):
    path = Path(path)
    if path.name == "main.c" and (path.parent / "scene.c").exists():
        return "\n".join((path.parent / name).read_text() for name in RUNTIME_UNITS)
    return path.read_text()


def validation_output(name):
    """Write harness artifacts outside the immutable/shared asset bank."""
    root = Path(
        os.environ.get(
            "HALO64_VALIDATION_OUTPUT",
            Path(__file__).resolve().parents[2] / "build/n64-validation/contracts",
        )
    )
    return root / name
