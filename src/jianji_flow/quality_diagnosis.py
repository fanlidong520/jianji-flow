from __future__ import annotations

import shutil
import subprocess
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


def _dark_pixel_ratio(image: Image.Image) -> float:
    rgb = image.convert("RGB")
    pixels = list(rgb.get_flattened_data())
    if not pixels:
        return 0.0
    dark = sum(1 for r, g, b in pixels if max(r, g, b) <= 45)
    return dark / len(pixels)


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


def _bright_component_stats(image: Image.Image) -> dict[str, float | int]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    total_pixels = width * height
    if total_pixels <= 0:
        return {
            "bright_component_count": 0,
            "bright_fragment_count": 0,
            "bright_fragment_area_ratio": 0.0,
            "largest_bright_component_ratio": 0.0,
        }

    pixels = rgb.load()
    visited = bytearray(total_pixels)
    component_count = 0
    fragment_count = 0
    fragment_area = 0
    largest_area = 0
    min_fragment_area = max(3, round(total_pixels * 0.00002))
    max_fragment_area = max(64, round(total_pixels * 0.03))
    max_fragment_width = max(18, round(width * 0.6))
    max_fragment_height = max(8, round(height * 0.22))

    def is_bright(x: int, y: int) -> bool:
        r, g, b = pixels[x, y]
        return r >= 220 and g >= 220 and b >= 220

    for y in range(height):
        for x in range(width):
            start_index = y * width + x
            if visited[start_index]:
                continue
            visited[start_index] = 1
            if not is_bright(x, y):
                continue

            component_count += 1
            area = 0
            min_x = max_x = x
            min_y = max_y = y
            stack = [(x, y)]
            while stack:
                cx, cy = stack.pop()
                area += 1
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if nx < 0 or nx >= width or ny < 0 or ny >= height:
                        continue
                    index = ny * width + nx
                    if visited[index]:
                        continue
                    visited[index] = 1
                    if is_bright(nx, ny):
                        stack.append((nx, ny))

            largest_area = max(largest_area, area)
            box_width = max_x - min_x + 1
            box_height = max_y - min_y + 1
            if (
                min_fragment_area <= area <= max_fragment_area
                and box_width <= max_fragment_width
                and box_height <= max_fragment_height
            ):
                fragment_count += 1
                fragment_area += area

    return {
        "bright_component_count": component_count,
        "bright_fragment_count": fragment_count,
        "bright_fragment_area_ratio": fragment_area / total_pixels,
        "largest_bright_component_ratio": largest_area / total_pixels,
    }


def diagnose_frame(image: Image.Image) -> dict:
    band = _lower_band(image)
    upper = _upper_band(image)
    top_chrome = image.crop((0, 0, image.width, round(image.height * 0.16)))
    bottom_chrome = image.crop((0, round(image.height * 0.82), image.width, image.height))
    bright_ratio = _bright_pixel_ratio(band)
    upper_bright_ratio = _bright_pixel_ratio(upper)
    horizontal_coverage = _bright_horizontal_coverage(band)
    component_stats = _bright_component_stats(band)
    top_component_stats = _bright_component_stats(top_chrome)
    bottom_component_stats = _bright_component_stats(bottom_chrome)
    top_bright_ratio = _bright_pixel_ratio(top_chrome)
    top_horizontal_coverage = _bright_horizontal_coverage(top_chrome)
    bottom_bright_ratio = _bright_pixel_ratio(bottom_chrome)
    bottom_dark_ratio = _dark_pixel_ratio(bottom_chrome)
    fragment_count = int(component_stats["bright_fragment_count"])
    fragment_area_ratio = float(component_stats["bright_fragment_area_ratio"])
    warnings: list[str] = []
    severity = "pass"
    has_residue = (
        bright_ratio >= 0.015
        and horizontal_coverage >= 0.08
        and bright_ratio >= upper_bright_ratio + 0.01
        and fragment_count >= 12
        and fragment_area_ratio >= 0.02
    )
    has_top_chrome = (
        top_bright_ratio >= 0.005
        and top_horizontal_coverage >= 0.08
        and int(top_component_stats["bright_fragment_count"]) >= 8
    )
    has_bottom_chrome = (
        bottom_dark_ratio >= 0.65
        and bottom_bright_ratio >= 0.0003
        and int(bottom_component_stats["bright_fragment_count"]) >= 4
    )
    if has_residue:
        is_severe = fragment_count >= 180 or fragment_area_ratio >= 0.18
        severity = "fail" if is_severe else "warning"
        if is_severe:
            warnings.append(
                "severe platform UI or original subtitles in the lower safe area; replace or crop this source clip."
            )
        else:
            warnings.append(
                "Possible platform UI or original subtitles in the lower safe area; captions may overlap and should be reviewed."
            )
    if has_top_chrome:
        severity = "warning" if severity == "pass" else severity
        warnings.append(
            "Possible platform UI or original overlay text in the upper safe area; crop or replace this source clip."
        )
    if has_bottom_chrome:
        severity = "warning" if severity == "pass" else severity
        warnings.append(
            "Possible platform UI in the bottom safe area; crop or replace this source clip."
        )
    return {
        "status": severity,
        "severity": severity,
        "warnings": warnings,
        "metrics": {
            "lower_bright_ratio": round(bright_ratio, 4),
            "upper_bright_ratio": round(upper_bright_ratio, 4),
            "lower_bright_horizontal_coverage": round(horizontal_coverage, 4),
            "lower_bright_component_count": component_stats["bright_component_count"],
            "lower_bright_fragment_count": fragment_count,
            "lower_bright_fragment_area_ratio": round(fragment_area_ratio, 4),
            "lower_largest_bright_component_ratio": round(
                float(component_stats["largest_bright_component_ratio"]), 4
            ),
            "upper_chrome_bright_ratio": round(top_bright_ratio, 4),
            "upper_chrome_bright_horizontal_coverage": round(top_horizontal_coverage, 4),
            "upper_chrome_bright_fragment_count": int(top_component_stats["bright_fragment_count"]),
            "bottom_chrome_dark_ratio": round(bottom_dark_ratio, 4),
            "bottom_chrome_bright_ratio": round(bottom_bright_ratio, 4),
            "bottom_chrome_bright_fragment_count": int(bottom_component_stats["bright_fragment_count"]),
        },
    }


def diagnose_image(path: Path) -> dict:
    with Image.open(path) as image:
        result = diagnose_frame(image.convert("RGB"))
    result["source"] = path.as_posix()
    return result


def build_source_frame_times_ms(start_ms: int, end_ms: int, *, samples: int = 3) -> list[int]:
    if end_ms <= start_ms:
        raise ValueError("source end_ms must be greater than source start_ms")
    if samples <= 0:
        raise ValueError("samples must be positive")
    duration = end_ms - start_ms
    return [round(start_ms + duration * (index + 1) / (samples + 1)) for index in range(samples)]


def _extract_frame(video_path: Path, frame_path: Path, time_ms: int) -> None:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-ss",
        f"{time_ms / 1000:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        str(frame_path),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        detail = result.stderr.strip() or f"frame extraction failed at {time_ms}ms"
        raise RuntimeError(detail)


def _render_safe_area(image: Image.Image) -> Image.Image:
    """Mirror the renderer crop before judging source residue."""
    width, height = image.size
    crop_width = max(1, round(width * 0.76))
    crop_height = max(1, round(height * 0.58))
    left = max(0, round((width - crop_width) / 2))
    top = max(0, round(height * 0.08))
    right = min(width, left + crop_width)
    bottom = min(height, top + crop_height)
    return image.crop((left, top, right, bottom))


def _match_by_id(matches: dict) -> dict[str, dict]:
    return {str(match.get("id")): match for match in matches.get("matches", [])}


def diagnose_source_matches(
    recipe: dict,
    matches: dict,
    diagnostics_dir: Path,
    *,
    samples_per_segment: int = 3,
) -> dict:
    failures: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, list[dict]] = {}
    clean_segment_ids: list[str] = []
    warning_frame_counts: dict[str, int] = {}
    warning_source_paths: dict[str, set[str]] = {}
    warning_segments: dict[str, set[str]] = {}
    by_id = _match_by_id(matches)
    diagnostics_dir.mkdir(parents=True, exist_ok=True)

    for segment in recipe.get("segments", []):
        segment_id = str(segment.get("id", "unknown"))
        match = by_id.get(str(segment.get("match_id")))
        if not match or match.get("status") not in {"selected", "low_confidence"}:
            continue
        source_path = Path(str(match.get("source_path", "")))
        try:
            start_ms = int(match.get("source_start_ms", 0))
            end_ms = int(match.get("source_end_ms", 0))
            times = build_source_frame_times_ms(start_ms, end_ms, samples=samples_per_segment)
        except (TypeError, ValueError) as exc:
            warnings.append(f"{segment_id}: source preflight skipped because source range is invalid: {exc}")
            continue

        metrics[segment_id] = []
        segment_issue_count = 0
        for index, time_ms in enumerate(times, start=1):
            frame_path = diagnostics_dir / f"{segment_id}-{index:02d}.png"
            try:
                _extract_frame(source_path, frame_path, time_ms)
                with Image.open(frame_path) as image:
                    safe_area = _render_safe_area(image.convert("RGB"))
                safe_area.save(frame_path)
                safe_area.close()
                result = diagnose_image(frame_path)
            except (OSError, RuntimeError, ValueError) as exc:
                warnings.append(f"{segment_id}: source preflight skipped at frame {index}: {exc}")
                segment_issue_count += 1
                continue
            metrics[segment_id].append(result.get("metrics", {}))
            if result.get("severity") == "fail":
                segment_issue_count += 1
                failures.append(
                    f"{segment_id} source frame {index}: severe platform UI or original subtitles before rendering; "
                    "replace this source clip."
                )
            elif result.get("warnings"):
                segment_issue_count += 1
                warning_frame_counts[segment_id] = warning_frame_counts.get(segment_id, 0) + 1
                source_key = source_path.resolve().as_posix().casefold()
                for warning in result.get("warnings", []):
                    warning_key = str(warning).strip().casefold()
                    warning_source_paths.setdefault(warning_key, set()).add(source_key)
                    warning_segments.setdefault(warning_key, set()).add(segment_id)
                warnings.append(
                    f"{segment_id} source frame {index}: possible platform UI or original subtitles before rendering; "
                    "review this source clip."
                )
        if metrics[segment_id] and segment_issue_count == 0:
            clean_segment_ids.append(segment_id)

    repeated_segments = [segment_id for segment_id, count in warning_frame_counts.items() if count >= 2]
    if not failures and repeated_segments:
        affected_segments = list(warning_frame_counts)
        if len(affected_segments) >= 2:
            location = f"across {', '.join(affected_segments)}"
        else:
            location = f"within {affected_segments[0]}"
        failures.append(
            f"Repeated platform UI/original-subtitle warnings {location}; preflight blocked rendering. "
            "Replace or crop these source clips before retrying."
        )

    repeated_warning_families = [
        warning_key
        for warning_key, source_paths in warning_source_paths.items()
        if len(source_paths) >= 2
    ]
    if not failures and repeated_warning_families:
        affected_segments = sorted(
            {
                segment_id
                for warning_key in repeated_warning_families
                for segment_id in warning_segments.get(warning_key, set())
            }
        )
        location = ", ".join(affected_segments) if affected_segments else "multiple segments"
        failures.append(
            f"Repeated platform UI/original-subtitle warnings across {location}; preflight blocked rendering. "
            "Replace or crop these source clips before retrying."
        )

    if not failures and not warnings and diagnostics_dir.exists():
        shutil.rmtree(diagnostics_dir)

    return {
        "status": "fail" if failures else "warning" if warnings else "pass",
        "failures": failures,
        "warnings": warnings,
        "metrics": metrics,
        "clean_segment_ids": clean_segment_ids,
        "diagnostics_dir": diagnostics_dir.as_posix(),
    }


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
    failures: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, dict] = {}
    with Image.open(path) as sheet:
        for segment, tile in zip(segments, _segment_tiles(sheet.convert("RGB"), len(segments))):
            segment_id = str(segment.get("id", "unknown"))
            content_tile = _trim_light_border(tile)
            result = diagnose_frame(content_tile)
            metrics[segment_id] = result.get("metrics", {})
            if result.get("severity") == "fail":
                failures.append(
                    f"{segment_id}: severe platform UI or original subtitles in the lower safe area; replace or crop this source clip."
                )
            elif result.get("warnings"):
                warnings.append(
                    f"{segment_id}: possible platform UI or original subtitles in the lower safe area; captions may overlap."
                )
            content_tile.close()
            tile.close()
    return {
        "status": "fail" if failures else "warning" if warnings else "pass",
        "failures": failures,
        "warnings": warnings,
        "metrics": metrics,
        "source": path.as_posix(),
    }
