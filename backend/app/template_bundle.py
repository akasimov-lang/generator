"""Shared complete offline template download assets."""
import base64
from app.template_design import PALETTES, art_svg

def assets(row):
    design = row.document["design"]
    accent = PALETTES[design["palette"]][5 if design["hero"] == "feature_billboard" else 4]
    result = {"assets/hero.svg": art_svg(row.document["design"]["visual_style"]).replace("currentColor", accent)}
    from app.template_phones import frame_svg, FRAMES
    media = row.document.get("brand_media") or {}
    for i, screen in enumerate(media.get("screens", [])):
        frame = media.get("frames", [FRAMES[0][0]] * len(media["screens"]))[i]
        result[f"assets/phone-{i+1}.svg"] = frame_svg(frame, screen)
    if media.get("logo"):
        result["assets/brand-logo.png"] = base64.b64decode(media["logo"].split(",", 1)[1])
    from app.template_asset_library import exported_assets
    result.update(exported_assets(row.document))
    from app.template_visual_assets import visual_files
    result.update(visual_files(row.document))
    return result


def downloadable_html(row):
    inline = art_svg(row.document["design"]["visual_style"])
    html = row.html.replace(inline, '<img src="assets/hero.svg" alt="" width="600" height="400" decoding="async">').replace(
        ".art svg{", ".art img{object-fit:contain;").replace(".composition-art svg{", ".composition-art img{")
    if row.document.get("generated_css"):
        html = row.html  # Preserve the generated currentColor instead of a preset palette.
    for path, image in assets(row).items():
        if path.startswith("assets/phone-"):
            encoded = "data:image/svg+xml;base64," + base64.b64encode(image.encode()).decode()
            html = html.replace(encoded, path)
    logo = (row.document.get("brand_media") or {}).get("logo")
    if logo:
        html = html.replace(logo, "assets/brand-logo.png")
    from app.template_asset_library import externalize
    from app.template_visual_assets import externalize as externalize_visuals
    return externalize_visuals(externalize(html, row.document), row.document)


