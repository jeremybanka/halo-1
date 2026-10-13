"""Source-contract tests inspect the actual runtime modules after extraction."""

from pathlib import Path
import os
import re

RUNTIME_UNITS = ("runtime_config.h", "scene.c", "presentation.c", "runtime_qa.c", "main.c")


def read_runtime(path):
    path = Path(path)
    if path.name == "main.c" and (path.parent / "scene.c").exists():
        return "\n".join((path.parent / name).read_text() for name in RUNTIME_UNITS)
    return path.read_text()


def without_experiments(source):
    """Inspect the accepted path with explicitly opt-in research flags off.

    Other preprocessor directives stay untouched. This is not a C preprocessor;
    it only selects the two reviewed #ifdef experiment blocks and their else
    paths. Their active behavior needs separate renderer/PVS/target checks.
    """
    disabled={'BG_CHIRON_PVS','BG_WORLD_PVS','BG_GEOMETRY_CENSUS'}
    stack=[];active=True;out=[]
    for line in source.splitlines(keepends=True):
        directive=line.strip()
        match=re.match(r'#\s*(if|ifdef|ifndef)\b',directive)
        if match:
            selected=directive in {'#ifdef '+name for name in disabled}
            stack.append((selected,active))
            if selected:active=False
            elif active:out.append(line)
        elif re.match(r'#\s*(else|elif)\b',directive):
            assert stack,'Unmatched conditional'
            selected,parent=stack[-1]
            if selected:
                assert directive=='#else','Experimental elif needs explicit review'
                active=parent
            elif active:out.append(line)
        elif re.match(r'#\s*endif\b',directive):
            assert stack,'Unmatched endif'
            selected,parent=stack.pop()
            if not selected and active:out.append(line)
            active=parent
        elif active:out.append(line)
    assert not stack,'Unclosed conditional'
    return ''.join(out)


def validation_output(name):
    """Write harness artifacts outside the immutable/shared asset bank."""
    root = Path(
        os.environ.get(
            "HALO64_VALIDATION_OUTPUT",
            Path(__file__).resolve().parents[2] / "build/n64-validation/contracts",
        )
    )
    return root / name
