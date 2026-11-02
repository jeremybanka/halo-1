"""Broad Reach material roles and muted chest/shoulder profile colors."""
TEAM_AMOUNT=80


def team_amount(tri):
    return TEAM_AMOUNT if tri.get('color_family',tri['component']).startswith(('chest-','shoulder-')) else 0


def special_colors(tri,materials):
    if 'corner_color_override' in tri:return tri['corner_color_override'],tri['corner_mask_override']
    if tri.get('color_override'):return [tri['color_override']]*3,[0]*3
    if tri['component']=='helmet-lens':return [[232,163,35]]*3,[0]*3
    return None
