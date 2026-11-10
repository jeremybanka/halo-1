"""Shared ODST material roles for authoring exports and the N64 packer."""
TEAM_AMOUNT=80  # 31% of the existing profile-color multiplier; deliberately muted.

def team_amount(tri):
    component=tri.get('source_component',tri['component'])
    return TEAM_AMOUNT if component.startswith(('chest-','l_shoulder-','r_shoulder-')) else 0

def special_colors(tri,materials):
    if tri.get('color_override'):return [tri['color_override']]*3,[0]*3
    role=materials[tri['material']]['path'].split('\\')[-1]
    if role=='odst_visor':return [[24,230,255]]*3,[0]*3
    if tri.get('corner_color_override'):return tri['corner_color_override'],[team_amount(tri)]*3
    if role=='odst_crown_stripe':return [[135,135,135]]*3,[0]*3
    return None
