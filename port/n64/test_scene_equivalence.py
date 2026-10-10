"""Guard the structural renderer extraction against unreviewed numeric/draw changes."""

from pathlib import Path
import re
import subprocess
from test_render_matrix import compact, function
from test_projection_cache import projection_block

ROOT = Path(__file__).resolve().parents[2]
reference = subprocess.check_output(
    ["git", "show", "b3fba521:port/n64/main.c"], cwd=ROOT, text=True
)
scene = (ROOT / "port/n64/scene.c").read_text()
functions = re.findall(r"^static[ \t]+(?:const[ \t]+)?\w+[ \t*]+(\w+)\([^;{}]*\)\s*\{", scene, re.M)
checked = []
for name in functions:
    if name == "record_texture":
        continue  # checked by test_texture_blocks and target RDP validation
    old_body, new_body = function(reference, name), function(scene, name)
    if name == "prepare_view":
        # This CPU-only region now memoizes perspective setup. Its complete
        # world/gun state is compared against the SDK path separately.
        old_body = old_body.replace(projection_block(reference), "PROJECTION_REGION")
        new_body = new_body.replace(projection_block(scene), "PROJECTION_REGION")
    old, new = compact(old_body), compact(new_body)
    if name == "visible_bounds":
        assert "return!bounds->valid||" in new and "bg_frustum_box_cached" in new
        continue  # optional cache path and invalid boxes checked by cull/pose fixtures
    new = new.replace(",cull_selected[p])", ")")

    if name == "init_scene":
        assert new.count("projection_keys[s][p]=0;") == 1
        new = new.replace("projection_keys[s][p]=0;", "")
        assert new.count("texture_blocks[i]=record_texture(i);") == 1
        new = new.replace("texture_blocks[i]=record_texture(i);", "")
    if name == "draw_view":
        binding = "if(paletted)rdpq_tex_upload_tlut((uint16_t*)bg_ground_palette,0,16);rdpq_tex_upload(TILE0,&textures[c->material],&(rdpq_texparms_t){.s.repeats=REPEAT_INFINITE,.t.repeats=REPEAT_INFINITE});"
        assert binding in old
        old = old.replace(binding, "TEXTURE_BIND")
        assert "rspq_block_run(texture_blocks[c->material]);" in new
        new = new.replace("rspq_block_run(texture_blocks[c->material]);", "TEXTURE_BIND")
    if name == "prepare_frame":
        for field, timer in (
            ("body_prepare_us", "begin"),
            ("vehicle_prepare_us", "section_begin"),
            ("pickup_prepare_us", "section_begin"),
        ):
            statement = (
                "#ifdefBG_PROFILEbg_scene_profile." + field + "=get_ticks_us()-" + timer + ";"
            )
            statement += (
                "uint64_tsection_begin=get_ticks_us();#endif"
                if field == "body_prepare_us"
                else "section_begin=get_ticks_us();#endif"
            )
            assert statement in new
            new = new.replace(statement, "")
        new = new.replace("bg_scene_profile.view_prepare_us=get_ticks_us()-section_begin;", "")
    for before, after in [
        ("model_qa_camera", "bg_qa_camera"),
        ("interaction_qa_camera", "bg_qa_interaction_camera"),
        ("model_qa_firstperson", "bg_qa_firstperson"),
    ]:
        old = old.replace(before + "(", after + "(")
    if name in ("visible_bounds", "draw_view"):
        for left, right in (
            (
                "t3d_frustum_vs_aabb_s16(&vp->viewFrustum,bounds->min,bounds->max)",
                "bg_frustum_box((constfloat(*)[4])vp->viewFrustum.planes,bounds->min,bounds->max)",
            ),
            (
                "t3d_frustum_vs_aabb_s16(&vp->viewFrustum,c->bounds,c->bounds+3)",
                "bg_frustum_box_cached((constfloat(*)[4])vp->viewFrustum.planes,cull_selected[p],c->bounds)",
            ),
        ):
            old = old.replace(left, "BOX_CULL")
            new = new.replace(right, "BOX_CULL")
    assert old == new, "Renderer arithmetic/commands changed during extraction: " + name
    checked.append(name)
assert len(checked) >= 35, checked
print(
    f"PASS: {len(checked)} renderer helpers checked against checkpoint; projection region tested separately, remaining arithmetic/GPU command order unchanged"
)
