"""Guard the structural renderer extraction against unreviewed numeric/draw changes."""

from pathlib import Path
import re
import subprocess
from test_render_matrix import compact, function

ROOT = Path(__file__).resolve().parents[2]
reference = subprocess.check_output(
    ["git", "show", "b3fba521:port/n64/main.c"], cwd=ROOT, text=True
)
scene = (ROOT / "port/n64/scene.c").read_text()
functions = re.findall(r"^static[ \t]+(?:const[ \t]+)?\w+[ \t*]+(\w+)\([^;{}]*\)\s*\{", scene, re.M)
checked = []
for name in functions:
    old = compact(function(reference, name))
    new = compact(function(scene, name))
    for before, after in [
        ("model_qa_camera", "bg_qa_camera"),
        ("interaction_qa_camera", "bg_qa_interaction_camera"),
        ("model_qa_firstperson", "bg_qa_firstperson"),
    ]:
        old = old.replace(before + "(", after + "(")
    assert old == new, "Renderer arithmetic/commands changed during extraction: " + name
    checked.append(name)
assert len(checked) >= 35, checked
print(
    f"PASS: {len(checked)} renderer functions retain checkpoint arithmetic and GPU command order, with explicit QA interface renames only"
)
