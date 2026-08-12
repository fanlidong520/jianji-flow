from __future__ import annotations

from pathlib import Path

from PIL import Image


def _lower_band(image: Image.Image) -> Image.Image:
    top = round(image.height * 0.72)
    return image.crop((0, top, image.width, image.height))


def _upper_band(image: Image.Image) -> Image.Image:
    bottom = round(image.height * 0.45)
    return image.crop((0, 0, image.width, bottom))


def _bright_pixel_ratio(image: Image.Image) -> float:
    rgb = image.convert("RGB")
    pixels = list(rgb.get_flattened_data())
    if not pixels:
        return 0.0
    bright = sum(1 for r, g, b in pixels if r >= 220 and g >= 220 and b >= 220)
    return bright / len(pixels)


def _bright_horizontal_coverage(image: Image.Image) -> float:
    rgb = image.convert("RGB")
    rows_with_bright_pixels = 0
    for y in range(rgb.height):
        row_bright_columns = 0
        for x in range(rgb.width):
            r, g, b = rgb.getpixel((x, y))
            if r >= 220 and g >= 220 and b >= 220:
                row_bright_columns += 1
        if row_bright_columns >= max(8, round(rgb.width * 0.02)):
            rows_with_bright_pixels += 1
    return rows_with_bright_pixels / rgb.height if rgb.height else 0.0


def diagnose_frame(image: Image.Image) -> dict:
    band = _lower_band(image)
    upper = _upper_band(image)
    bright_ratio = _bright_pixel_ratio(band)
    upper_bright_ratio = _bright_pixel_ratio(upper)
    horizontal_coverage = _bright_horizontal_coverage(band)
    warnings: list[str] = []
    if bright_ratio >= 0.015 and horizontal_coverage >= 0.08 and bright_ratio >= upper_bright_ratio + 0.01:
        warnings.append(
            "Possible platform UI or original subtitles in the lower safe area; captions may overlap and should be reviewed."
        )
    return {
        "status": "warning" if warnings else "pass",
        "warnings": warnings,
        "metrics": {
            "lower_bright_ratio": round(bright_ratio, 4),
            "upper_bright_ratio": round(upper_bright_ratio, 4),
            "lower_bright_horizontal_coverage": round(horizontal_coverage, 4),
        },
    }


def diagnose_image(path: Path) -> dict:
    with Image.open(path) as image:
        result = diagnose_frame(image.convert("RGB"))
    result["source"] = path.as_posix()
    return result


def _segment_tiles(sheet: Image.Image, segment_count: int) -> list[Image.Image]:
    if segment_count <= 0:
        return []
    tile_pitch = sheet.width / segment_count
    tiles: list[Image.Image] = []
    for index in range(segment_count):
        left = round(index * tile_pitch)
        right = round((index + 1) * tile_pitch)
        tiles.append(sheet.crop((left, 0, right, sheet.height)))
    return tiles


def _trim_light_border(image: Image.Image) -> Image.Image:
    rgb = image.convert("RGB")
    mask = rgb.point(lambda value: 0 if value > 245 else 255).convert("L")
    box = mask.getbbox()
    if box is None:
        return rgb
    return rgb.crop(box)


def diagnose_contact_sheet_segments(path: Path, recipe: dict) -> dict:
    segments = list(recipe.get("segments", []))
    warnings: list[str] = []
    metrics: dict[str, dict] = {}
    with Image.open(path) as sheet:
        for segment, tile in zip(segments, _segment_tiles(sheet.convert("RGB"), len(segments))):
            segment_id = str(segment.get("id", "unknown"))
            content_tile = _trim_light_border(tile)
            result = diagnose_frame(content_tile)
            metrics[segment_id] = result.get("metrics", {})
            if result.get("warnings"):
                warnings.append(
                    f"{segment_id}: possible platform UI or original subtitles in the lower safe area; captions may overlap."
                )
            content_tile.close()
            tile.close()
    return {
        "status": "warning" if warnings else "pass",
        "warnings": warnings,
        "metrics": metrics,
        "source": path.as_posix(),
    }
